import re

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import ValidationError

from guanchen_v2.knowledge.models import Citation
from guanchen_v2.liuyao.casting import HexagramCastingService, ManualCastingInput
from guanchen_v2.liuyao.exceptions import LiuyaoPolicyError
from guanchen_v2.liuyao.formatter import format_evidence_for_prompt, format_hexagram_facts_for_prompt
from guanchen_v2.liuyao.policy import (
    ClarificationAssessment,
    ConfirmationResponse,
    apply_clarification_assessment,
    apply_confirmation_response,
    can_cast,
)
from guanchen_v2.liuyao.retrieval import LiuyaoRetrievalBuilder
from guanchen_v2.liuyao.state import LiuyaoState
from guanchen_v2.llm.client import LLMClient
from guanchen_v2.models.liuyao import CastingMethod, DecisionQuestionStatus, DecisionReflection
from guanchen_v2.prompts.liuyao_agent import (
    LIUYAO_CLARIFICATION_SYSTEM_PROMPT,
    LIUYAO_CLARIFICATION_USER_TEMPLATE,
    LIUYAO_INTERPRETATION_SYSTEM_PROMPT,
    LIUYAO_INTERPRETATION_USER_TEMPLATE,
)

_EVIDENCE_REF_PATTERN = re.compile(r"\[Evidence\s+(\d+)\]")


def validate_evidence_references(reflection: DecisionReflection, citations: list[Citation]) -> None:
    """验证 DecisionReflection 中 [Evidence N] 的引用是否真实存在"""
    refs = {int(match) for match in _EVIDENCE_REF_PATTERN.findall(reflection.traditional_reflection)}

    max_index = len(citations)
    invalid_refs = sorted(ref for ref in refs if ref < 1 or ref > max_index)

    if invalid_refs:
        raise LiuyaoPolicyError("DecisionReflection 包含不存在的 Evidence 引用")


class LiuyaoAgentRuntime:
    def __init__(
        self,
        casting_service: HexagramCastingService,
        llm_client: LLMClient,
        retrieval_builder: LiuyaoRetrievalBuilder,
        checkpointer: BaseCheckpointSaver | None = None
    ):
        self._casting_service = casting_service
        self._llm_client = llm_client
        self._retrieval_builder = retrieval_builder
        self._checkpointer = checkpointer or InMemorySaver()

    async def clarify_node(self, state: LiuyaoState) -> dict:
        q = state["question"]
        pending = state.get("pending_user_input", "")

        user_prompt = LIUYAO_CLARIFICATION_USER_TEMPLATE.format(
            original_question=q.original_question,
            reality_constraints="、".join(q.reality_constraints) if q.reality_constraints else "无",
            pending_user_input=pending if pending else "无",
        )

        assessment = await self._llm_client.generate_structured(
            system_prompt=LIUYAO_CLARIFICATION_SYSTEM_PROMPT, user_prompt=user_prompt, schema=ClarificationAssessment
        )

        return apply_clarification_assessment(state, assessment)

    def confirmation_node(self, state: LiuyaoState) -> dict:
        q = state["question"]
        resume_payload = interrupt(
            {
                "type": "liuyao_confirmation",
                "question": q.clarified_question,
                "reality_constraints": q.reality_constraints,
                "allowed_actions": ["confirm", "modify", "cancel"],
            }
        )
        try:
            response = ConfirmationResponse.model_validate(resume_payload)
        except ValidationError as exc:
            raise LiuyaoPolicyError("无效的六爻确认响应") from exc
        return apply_confirmation_response(state, response)

    def cast_node(self, state: LiuyaoState) -> dict:
        if not can_cast(state):
            raise LiuyaoPolicyError("状态机未就绪或未通过用户确认，拒绝执行起卦操作")

        method = state.get("casting_method")
        if method == CastingMethod.MANUAL_SIX_LINES:
            manual_lines = state.get("manual_lines")
            if manual_lines is None or len(manual_lines) != 6:
                raise LiuyaoPolicyError("手工起卦必须提供完整 manual_lines")
            hexagram = self._casting_service.cast_manual(ManualCastingInput(lines=manual_lines))
        elif method == CastingMethod.SYSTEM_THREE_COIN:
            hexagram = self._casting_service.cast_random()
        else:
            raise LiuyaoPolicyError(f"不支持的起卦方式: {method}")

        return {"hexagram": hexagram}

    async def retrieve_node(self, state: LiuyaoState) -> dict:
        if not can_cast(state):
            raise LiuyaoPolicyError("未通过确认检查，禁止检索")

        hexagram = state.get("hexagram")
        if not hexagram:
            raise LiuyaoPolicyError("缺少 HexagramResult，无法执行六爻知识检索")

        q = state["question"]
        if q.clarified_question is None:
            raise LiuyaoPolicyError("缺少已确认的 clarified_question，无法执行六爻知识检索")

        results = await self._retrieval_builder.retrieve(q.clarified_question, hexagram)
        citations = [Citation.from_retrieval_result(r) for r in results]

        return {"retrieved_context": results, "citations": citations}

    async def interpret_node(self, state: LiuyaoState) -> dict:
        if not can_cast(state):
            raise LiuyaoPolicyError("未通过确认检查，禁止生成六爻决策反思")

        q = state["question"]
        hexagram = state.get("hexagram")

        if hexagram is None:
            raise LiuyaoPolicyError("缺少 HexagramResult，无法生成六爻决策反思")
        if q.clarified_question is None:
            raise LiuyaoPolicyError("缺少已确认的 clarified_question")

        evidence_results = state.get("retrieved_context", [])

        facts_str = format_hexagram_facts_for_prompt(hexagram)
        evidence_str = format_evidence_for_prompt(evidence_results)
        constraints_str = "、".join(q.reality_constraints) if q.reality_constraints else "无"

        user_prompt = LIUYAO_INTERPRETATION_USER_TEMPLATE.format(
            question=q.clarified_question,
            reality_constraints=constraints_str,
            hexagram_facts=facts_str,
            evidence=evidence_str,
        )

        reflection = await self._llm_client.generate_structured(
            system_prompt=LIUYAO_INTERPRETATION_SYSTEM_PROMPT, user_prompt=user_prompt, schema=DecisionReflection
        )
        return {"reflection": reflection}

    def finalize_node(self, state: LiuyaoState) -> dict:
        reflection = state.get("reflection")
        if not reflection:
            raise LiuyaoPolicyError("缺失 DecisionReflection，无法渲染最终回复")

        citations = state.get("citations", [])

        # 确定性防伪造校验
        validate_evidence_references(reflection, citations)

        parts = [
            f"### 【现状评估】\n{reflection.situation_summary}\n",
            f"### 【文化推演】\n{reflection.traditional_reflection}\n",
            f"### 【现实校验】\n{reflection.reality_check}\n",
            "### 【决策参考】",
        ]

        for opt in reflection.decision_options:
            parts.append(f"- {opt}")

        parts.append(f"\n> *注：{reflection.uncertainty_note}*")

        if citations:
            parts.append("\n### 【参考来源】")
            for idx, cite in enumerate(citations, start=1):
                parts.append(f"[Evidence {idx}] {cite.source_title} - {cite.section}")

        return {"final_response": "\n".join(parts)}

    def route_after_clarify(self, state: LiuyaoState) -> str:
        status = state["question"].status
        if status == DecisionQuestionStatus.NEEDS_CLARIFICATION:
            return END
        elif status == DecisionQuestionStatus.PENDING_CONFIRMATION:
            return "confirmation"

        raise LiuyaoPolicyError(f"clarify 后出现非法状态 (状态机断裂): {status}")

    def route_after_confirmation(self, state: LiuyaoState) -> str:
        status = state["question"].status
        if status == DecisionQuestionStatus.CONFIRMED:
            return "cast"
        elif status == DecisionQuestionStatus.NEEDS_CLARIFICATION:
            return "clarify"
        elif status == DecisionQuestionStatus.CANCELLED:
            return END

        raise LiuyaoPolicyError(f"confirmation 后出现非法状态 (状态机断裂): {status}")

    def build_graph(self) -> StateGraph:
        builder = StateGraph(LiuyaoState)

        builder.add_node("clarify", self.clarify_node)
        builder.add_node("confirmation", self.confirmation_node)
        builder.add_node("cast", self.cast_node)
        builder.add_node("retrieve", self.retrieve_node)
        builder.add_node("interpret", self.interpret_node)
        builder.add_node("finalize", self.finalize_node)

        builder.add_edge(START, "clarify")

        builder.add_conditional_edges("clarify", self.route_after_clarify)
        builder.add_conditional_edges("confirmation", self.route_after_confirmation)

        builder.add_edge("cast", "retrieve")
        builder.add_edge("retrieve", "interpret")
        builder.add_edge("interpret", "finalize")
        builder.add_edge("finalize", END)

        return builder.compile(checkpointer=self._checkpointer)


