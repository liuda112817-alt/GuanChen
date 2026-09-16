import json
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from guanchen_v2.core.errors import ProjectError
from guanchen_v2.dream.context import (
    DreamContextService,
    DreamContextStatus,
)
from guanchen_v2.dream.dream_merge import mark_interpreted
from guanchen_v2.dream.exceptions import (
    DreamInterpretationError,
)
from guanchen_v2.dream.retrieval import (
    DreamRetrievalService,
    dedupe_retrieval_results,
)
from guanchen_v2.knowledge.models import (
    Citation,
    RetrievalResult,
)
from guanchen_v2.llm.client import LLMClient
from guanchen_v2.models.dream import (
    DreamRecord,
    InterpretationStatus,
    NonBlankText,
)
from guanchen_v2.prompts.dream_agent import (
    DREAM_INTERPRETATION_SYSTEM_PROMPT,
    DREAM_INTERPRETATION_USER_TEMPLATE,
)


class DreamResponseMode(StrEnum):
    INITIAL = "initial"
    UPDATE = "update"
    CONTINUE = "continue"


class DreamInterpretationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    traditional_view: NonBlankText | None = Field(
        default=None,
        description=("仅基于提供的传统知识 evidence 形成的文化象征解释；证据不足或未使用传统证据时为 null"),
    )

    psychological_context_view: NonBlankText = Field(
        description=("非诊断性的心理 / 现实情境反思，只基于用户明确提供的梦境、情绪和现实背景"),
    )

    used_chunk_ids: list[str] = Field(
        default_factory=list,
        description=("traditional_view 实际使用的 TRADITIONAL EVIDENCE chunk_id，按首次使用顺序返回。"),
    )

    @model_validator(mode="after")
    def validate_evidence_contract(
        self,
    ) -> "DreamInterpretationDraft":
        for chunk_id in self.used_chunk_ids:
            if not chunk_id.strip():
                raise ValueError("used_chunk_ids 不能包含空值。")

        if self.traditional_view is None and self.used_chunk_ids:
            raise ValueError("traditional_view 为空时，used_chunk_ids 必须为空。")

        if self.traditional_view is not None and not self.used_chunk_ids:
            raise ValueError("traditional_view 非空时，必须至少引用一个实际使用的 chunk_id。")

        return self


class DreamInterpretationResponse(BaseModel):
    traditional_view: NonBlankText
    psychological_context_view: NonBlankText


class DreamAgentStatus(StrEnum):
    NEEDS_CLARIFICATION = "needs_clarification"
    ANSWERED = "answered"


class DreamAgentResult(BaseModel):
    status: DreamAgentStatus
    record: DreamRecord
    clarification_question: str | None = None
    response: DreamInterpretationResponse | None = None
    citations: list[Citation] = Field(default_factory=list)


def select_response_mode(
    record: DreamRecord,
) -> DreamResponseMode:
    """确定性决定本轮 Dream 回复模式。"""
    if record.interpretation_state.status == InterpretationStatus.NOT_STARTED:
        return DreamResponseMode.INITIAL

    if record.interpretation_state.status == InterpretationStatus.STALE:
        return DreamResponseMode.UPDATE

    return DreamResponseMode.CONTINUE


def _format_evidence(
    results: list[RetrievalResult],
) -> str:
    """
    将 RetrievalResult 转换为 LLM 可使用的 evidence。

    只暴露 citation 所需 identity 与正文，
    不暴露 Dense/Sparse/RRF/Reranker 分数。
    """
    if not results:
        return "[]"

    formatted: list[str] = []

    for index, result in enumerate(
        results,
        start=1,
    ):
        formatted.append(
            f"[Evidence {index}]\nchunk_id: {result.chunk_id}\nsource_title: {result.source_title}\nsection: {result.section}\ntext: {result.text}\n"
        )

    return "\n".join(formatted)


def _resolve_used_evidence(
    results: list[RetrievalResult],
    used_chunk_ids: list[str],
) -> list[RetrievalResult]:
    """
    将 LLM 声明实际使用的 chunk_id 映射回本轮合法 evidence。

    - 禁止引用未检索到的 chunk；
    - 按 LLM 第一次使用顺序返回；
    - 重复 chunk_id 只保留一次。
    """
    result_map = {result.chunk_id: result for result in results}

    resolved: list[RetrievalResult] = []
    seen: set[str] = set()

    for raw_chunk_id in used_chunk_ids:
        chunk_id = raw_chunk_id.strip()

        if chunk_id in seen:
            continue

        if chunk_id not in result_map:
            raise DreamInterpretationError("模型返回了未授权的传统知识证据编号。")

        seen.add(chunk_id)
        resolved.append(result_map[chunk_id])

    return resolved


def _map_citations(
    results: list[RetrievalResult],
) -> list[Citation]:
    """只为已经确认实际使用的 evidence 生成 Citation。"""
    return [Citation.from_retrieval_result(result) for result in results]


class DreamAgentRuntime:
    def __init__(
        self,
        context_service: DreamContextService,
        retrieval_service: DreamRetrievalService,
        llm_client: LLMClient,
    ) -> None:
        self._context_service = context_service
        self._retrieval_service = retrieval_service
        self._llm_client = llm_client

        self._current_record: DreamRecord | None = None

    async def handle_turn(
        self,
        user_text: str,
    ) -> DreamAgentResult:
        # 1. 更新 Dream 状态
        context_result = await self._context_service.apply_turn(
            user_text,
            current_record=self._current_record,
        )

        # Merge 成功后，新状态立即成为当前状态。
        self._current_record = context_result.record

        # 2. 需要澄清时短路
        if context_result.status == DreamContextStatus.NEEDS_CLARIFICATION:
            return DreamAgentResult(
                status=DreamAgentStatus.NEEDS_CLARIFICATION,
                record=self._current_record,
                clarification_question=(context_result.clarification_question),
            )

        # 3. 回复模式由状态机决定
        mode = select_response_mode(self._current_record)

        # 4. DreamRetrievalService 内部强制 DREAM domain
        evidence_groups = await self._retrieval_service.retrieve(self._current_record)

        deduped_results = dedupe_retrieval_results(evidence_groups)

        # 5. 构建最小化解释上下文
        state_str = json.dumps(
            {
                "elements": (self._current_record.elements.model_dump()),
                "reality_background": (self._current_record.reality_background.model_dump()),
            },
            ensure_ascii=False,
        )

        if context_result.patch is None:
            delta_str = "{}"
        else:
            delta_str = context_result.patch.model_dump_json(exclude_unset=True)

        evidence_str = _format_evidence(deduped_results)

        user_prompt = DREAM_INTERPRETATION_USER_TEMPLATE.format(
            response_mode=mode.value,
            current_state=state_str,
            current_delta=delta_str,
            traditional_evidence=evidence_str,
        )

        # 6. LLM 结构化解释
        try:
            draft = await self._llm_client.generate_structured(
                system_prompt=(DREAM_INTERPRETATION_SYSTEM_PROMPT),
                user_prompt=user_prompt,
                schema=DreamInterpretationDraft,
            )
        except ProjectError as exc:
            raise DreamInterpretationError("梦境解释生成失败") from exc

        # 7. 验证 LLM 声明使用的 evidence
        used_results = _resolve_used_evidence(
            results=deduped_results,
            used_chunk_ids=draft.used_chunk_ids,
        )

        fallback_traditional_view = "当前共享知识库没有检索到足够可追溯的传统资料，因此本轮暂不作具体的传统象征判断。"

        # 8. traditional_view 必须与真实 evidence lineage 对齐
        if draft.traditional_view is None or not used_results:
            final_traditional_view = fallback_traditional_view
            citations: list[Citation] = []
        else:
            final_traditional_view = draft.traditional_view
            citations = _map_citations(used_results)

        response = DreamInterpretationResponse(
            traditional_view=final_traditional_view,
            psychological_context_view=(draft.psychological_context_view),
        )

        # 9. 解释成功后才将 interpretation 标为 CURRENT
        self._current_record = mark_interpreted(self._current_record)

        return DreamAgentResult(
            status=DreamAgentStatus.ANSWERED,
            record=self._current_record,
            response=response,
            citations=citations,
        )
