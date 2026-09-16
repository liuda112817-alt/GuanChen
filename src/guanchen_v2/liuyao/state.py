from typing import TypedDict

from guanchen_v2.knowledge.models import Citation, RetrievalResult
from guanchen_v2.models.liuyao import CastingMethod, DecisionQuestion, DecisionReflection, HexagramResult, LineValue


class LiuyaoState(TypedDict):
    """
    LangGraph 工作流的运行时状态 (Orchestration State)。
    """

    # 业务侧的 Source of Truth
    question: DecisionQuestion

    # 当前等待用户回答的系统澄清提示语（不需要保留历史）
    clarification: str | None

    # Transient Field：用于搭载 MODIFY 后用户修改/补充的内容，供下轮 clarify 消费
    pending_user_input: str | None

    # Routing 投影，必须始终保持与 question.status == CONFIRMED 同步
    confirmed: bool

    # 起卦策略，连接 Task 2 的确定性执行
    casting_method: CastingMethod
    manual_lines: tuple[LineValue, LineValue, LineValue, LineValue, LineValue, LineValue] | None

    # 确定性代码产生的排盘事实
    hexagram: HexagramResult | None

    # Transient: 传递给 Interpretation 节点的完整证据原文
    retrieved_context: list[RetrievalResult]

    # Transient: LLM 生成的结构化反思草稿
    reflection: DecisionReflection | None

    # 标准的引文溯源
    citations: list[Citation]

    # 最终发送给用户的决策反思文本
    final_response: str | None


def create_initial_liuyao_state(original_question: str) -> LiuyaoState:
    """
    纯函数：创建初始的六爻工作流状态。
    """
    question = DecisionQuestion(
        original_question=original_question,
    )

    return {
        "question": question,
        "clarification": None,
        "pending_user_input": None,
        "confirmed": False,
        "casting_method": CastingMethod.SYSTEM_THREE_COIN,
        "manual_lines": None,
        "hexagram": None,
        "retrieved_context": [],
        "reflection": None,
        "citations": [],
        "final_response": None,
    }
