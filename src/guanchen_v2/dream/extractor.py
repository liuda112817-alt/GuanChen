import json

from guanchen_v2.dream.exceptions import DreamExtractionError
from guanchen_v2.llm.client import LLMClient
from guanchen_v2.llm.exceptions import LLMError
from guanchen_v2.models.dream import (
    DreamElements,
    DreamPatch,
    DreamRecord,
    RealityBackground,
)
from guanchen_v2.prompts.dream_agent import (
    DREAM_EXTRACTION_SYSTEM_PROMPT,
    DREAM_EXTRACTION_USER_TEMPLATE,
)


class DreamExtractor:
    """
    Dream Agent 的结构化增量信息抽取器。

    职责：
    - 只抽取用户本轮明确提供的 DreamPatch；
    - 只向 LLM 暴露当前有效 Dream 状态；
    - 不负责状态 merge；
    - 不负责梦境解释；
    - 所有 LLM 调用统一通过 LLMClient。
    """

    def __init__(
        self,
        llm_client: LLMClient,
    ) -> None:
        self._llm_client = llm_client

    def _build_context(
        self,
        current_record: DreamRecord | None,
    ) -> str:
        """
        构建抽取任务所需的最小当前状态。

        不传递：
        - raw_descriptions
        - interpretation_state
        - revision
        - 其他历史运行时信息
        """
        if current_record is None:
            elements = DreamElements()
            reality_background = RealityBackground()
        else:
            elements = current_record.elements
            reality_background = current_record.reality_background

        context = {
            "elements": elements.model_dump(),
            "reality_background": (reality_background.model_dump()),
        }

        return json.dumps(
            context,
            ensure_ascii=False,
        )

    async def extract(
        self,
        user_text: str,
        current_record: DreamRecord | None = None,
    ) -> DreamPatch:
        if not user_text.strip():
            raise DreamExtractionError("梦境信息抽取输入不能为空")

        current_context = self._build_context(current_record=current_record)

        user_prompt = DREAM_EXTRACTION_USER_TEMPLATE.format(
            current_context=current_context,
            user_text=user_text,
        )

        try:
            result = await self._llm_client.generate_structured(
                system_prompt=(DREAM_EXTRACTION_SYSTEM_PROMPT),
                user_prompt=user_prompt,
                schema=DreamPatch,
            )
        except LLMError as exc:
            raise DreamExtractionError("梦境信息结构化抽取失败") from exc

        if not isinstance(
            result,
            DreamPatch,
        ):
            raise DreamExtractionError("模型未返回合法的 DreamPatch 结构化输出")

        return result
