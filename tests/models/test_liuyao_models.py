import pytest
from pydantic import ValidationError

from guanchen_v2.liuyao.state import create_initial_liuyao_state
from guanchen_v2.models.liuyao import DecisionQuestion, DecisionQuestionStatus


def test_decision_question_draft_allows_empty_clarified():
    """DRAFT 和 NEEDS_CLARIFICATION 状态下允许 clarified_question 为空"""
    dq = DecisionQuestion(original_question="我要不要辞职？")
    assert dq.status == DecisionQuestionStatus.DRAFT
    assert dq.clarified_question is None

    dq.status = DecisionQuestionStatus.NEEDS_CLARIFICATION
    assert dq.clarified_question is None


def test_decision_question_pending_confirmation_requires_clarified():
    """防线测试：如果标记为待确认，决不能拿着一个空问题去问用户"""
    with pytest.raises(ValidationError, match="必须存在 clarified_question"):
        DecisionQuestion(
            original_question="我要不要辞职？",
            status=DecisionQuestionStatus.PENDING_CONFIRMATION,
        )


def test_decision_question_confirmed_requires_clarified():
    """防线测试：如果标记为已确认，问题实体必须实质存在"""
    with pytest.raises(ValidationError, match="必须存在 clarified_question"):
        DecisionQuestion(
            original_question="我要不要辞职？",
            status=DecisionQuestionStatus.CONFIRMED,
        )


def test_decision_question_valid_confirmation():
    """合法的完整确认状态应被 Pydantic 顺利放行"""
    dq = DecisionQuestion(
        original_question="我要辞职吗？近期房贷压力大。",
        clarified_question="是否应该在未来三个月内离职？",
        reality_constraints=["近期有房贷压力，不能断供"],
        status=DecisionQuestionStatus.CONFIRMED,
    )
    assert dq.status == DecisionQuestionStatus.CONFIRMED
    assert len(dq.reality_constraints) == 1


def test_create_initial_liuyao_state():
    """验证工作流入口必须产出纯净的、未被污染的初始基线状态"""
    state = create_initial_liuyao_state("工作太累了，算一卦")

    assert state["question"].original_question == "工作太累了，算一卦"
    assert state["question"].status == DecisionQuestionStatus.DRAFT
    assert state["question"].clarified_question is None

    assert state["clarification"] is None
    assert state["confirmed"] is False
    assert state["hexagram"] is None
    assert state["citations"] == []
    assert state["final_response"] is None


def test_cannot_assign_confirmed_without_clarified():
    """防线测试：严格拦截在实例化之后，被违规赋值为 CONFIRMED 状态"""
    dq = DecisionQuestion(original_question="我要不要辞职？")

    with pytest.raises(
        ValidationError,
        match="必须存在 clarified_question",
    ):
        # 如果 validate_assignment=False，这行代码将无视验证规则强制修改成功
        dq.status = DecisionQuestionStatus.CONFIRMED
