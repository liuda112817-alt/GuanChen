import pytest

from guanchen_v2.liuyao.exceptions import LiuyaoPolicyError
from guanchen_v2.liuyao.policy import (
    ClarificationAssessment,
    ConfirmationAction,
    ConfirmationResponse,
    apply_clarification_assessment,
    apply_confirmation_response,
    can_cast,
)
from guanchen_v2.liuyao.state import create_initial_liuyao_state
from guanchen_v2.models.liuyao import DecisionQuestion, DecisionQuestionStatus


def test_clarification_needed_transition():
    """1. 测试 needs_clarification=True 时转为 NEEDS_CLARIFICATION 且 confirmed=false"""
    q = DecisionQuestion(original_question="我该辞职吗？")
    state = {"question": q, "clarification": None, "confirmed": False, "hexagram": None, "citations": [], "final_response": None}

    assessment = ClarificationAssessment(
        needs_clarification=True,
        clarification_prompt="请问你的主要考量是什么？",
    )
    new_state = apply_clarification_assessment(state, assessment)

    assert new_state["question"].status == DecisionQuestionStatus.NEEDS_CLARIFICATION
    assert new_state["question"].clarified_question is None
    assert new_state["clarification"] == "请问你的主要考量是什么？"
    assert new_state["confirmed"] is False
    assert can_cast(new_state) is False


def test_candidate_ready_transition():
    """2. 测试 candidate ready 时转为 PENDING_CONFIRMATION"""
    q = DecisionQuestion(original_question="我该辞职吗？")
    state = {"question": q, "clarification": None, "confirmed": False, "hexagram": None, "citations": [], "final_response": None}

    assessment = ClarificationAssessment(
        needs_clarification=False,
        clarified_question="未来三个月内是否应当辞职并转向自由职业？",
        reality_constraints=["有房贷", "无其他被动收入"],
    )
    new_state = apply_clarification_assessment(state, assessment)

    assert new_state["question"].status == DecisionQuestionStatus.PENDING_CONFIRMATION
    assert new_state["question"].clarified_question == "未来三个月内是否应当辞职并转向自由职业？"
    assert new_state["question"].reality_constraints == ["有房贷", "无其他被动收入"]
    assert new_state["clarification"] is None
    assert new_state["confirmed"] is False
    assert can_cast(new_state) is False


def test_explicit_confirm_transition():
    """3. 测试只有 PENDING_CONFIRMATION 状态下才能显式 CONFIRM 转为 CONFIRMED"""
    q = DecisionQuestion(
        original_question="我该辞职吗？",
        clarified_question="未来三个月内是否应当辞职？",
        status=DecisionQuestionStatus.PENDING_CONFIRMATION,
    )
    state = {"question": q, "clarification": None, "confirmed": False, "hexagram": None, "citations": [], "final_response": None}

    response = ConfirmationResponse(action=ConfirmationAction.CONFIRM)
    new_state = apply_confirmation_response(state, response)

    assert new_state["question"].status == DecisionQuestionStatus.CONFIRMED
    assert new_state["confirmed"] is True
    assert can_cast(new_state) is True

    # 验证幂等性（再次 CONFIRM 应当是安全 no-op）
    idempotent_state = apply_confirmation_response(new_state, response)
    assert idempotent_state["question"].status == DecisionQuestionStatus.CONFIRMED
    assert can_cast(idempotent_state) is True


def test_modify_invalidates_downstream():
    """4. 测试 MODIFY 导致确认失效，下游结果全清，并退回 NEEDS_CLARIFICATION"""
    q = DecisionQuestion(
        original_question="我该辞职吗？",
        clarified_question="未来三个月内是否应当辞职？",
        status=DecisionQuestionStatus.CONFIRMED,
    )
    state = {
        "question": q,
        "clarification": None,
        "confirmed": True,
        "hexagram": "mock_hexagram_obj",
        "citations": ["some_citation"],
        "final_response": "some_response",
    }

    response = ConfirmationResponse(
        action=ConfirmationAction.MODIFY,
        modification="我其实能接受两个月没有收入",
    )
    new_state = apply_confirmation_response(state, response)

    assert new_state["question"].status == DecisionQuestionStatus.NEEDS_CLARIFICATION
    assert new_state["question"].clarified_question is None
    assert new_state["confirmed"] is False
    assert new_state["hexagram"] is None
    assert new_state["citations"] == []
    assert new_state["final_response"] is None
    assert can_cast(new_state) is False
    assert new_state["clarification"] is None  # 带有实际修正意图时，无需等待进一步用户澄清提示


def test_cancel_transition():
    """5. 测试 CANCEL 转换为 CANCELLED，保留审计上下文且绝对不可起卦"""
    q = DecisionQuestion(
        original_question="我该辞职吗？",
        clarified_question="未来三个月内是否应当辞职？",
        status=DecisionQuestionStatus.PENDING_CONFIRMATION,
    )
    state = {"question": q, "clarification": None, "confirmed": False, "hexagram": "some_data", "citations": [1]}

    response = ConfirmationResponse(action=ConfirmationAction.CANCEL)
    new_state = apply_confirmation_response(state, response)

    assert new_state["question"].status == DecisionQuestionStatus.CANCELLED
    assert new_state["question"].original_question == "我该辞职吗？"
    assert new_state["question"].clarified_question == "未来三个月内是否应当辞职？"
    assert new_state["confirmed"] is False
    assert new_state["hexagram"] is None
    assert can_cast(new_state) is False

    # 验证 CANCEL 幂等
    idempotent_state = apply_confirmation_response(new_state, response)
    assert idempotent_state["question"].status == DecisionQuestionStatus.CANCELLED


def test_cast_guard_projection():
    """6. 验证 state consistency guard：只有一致的 confirmed state 才允许 can_cast=True"""
    q_confirmed = DecisionQuestion(
        original_question="测试",
        clarified_question="测试澄清",
        status=DecisionQuestionStatus.CONFIRMED,
    )

    # 正常一致状态
    valid_state = {"question": q_confirmed, "confirmed": True}
    assert can_cast(valid_state) is True

    # 异常不一致状态：状态是 CONFIRMED 但 confirmed 投影标志被错误伪造成 False
    invalid_state_1 = {"question": q_confirmed, "confirmed": False}
    with pytest.raises(LiuyaoPolicyError, match="六爻确认状态不一致"):
        can_cast(invalid_state_1)

    # 异常不一致状态：状态是 PENDING_CONFIRMATION 但 confirmed 被错误置为 True
    q_pending = DecisionQuestion(
        original_question="测试",
        clarified_question="测试澄清",
        status=DecisionQuestionStatus.PENDING_CONFIRMATION,
    )
    invalid_state_2 = {"question": q_pending, "confirmed": True}
    with pytest.raises(LiuyaoPolicyError, match="六爻确认状态不一致"):
        can_cast(invalid_state_2)


def test_confirm_rejects_non_pending_state():
    """7. 验证 DRAFT 状态直接确认会被拒绝"""
    state = create_initial_liuyao_state("测试")

    with pytest.raises(
        LiuyaoPolicyError,
        match="不允许直接确认",
    ):
        apply_confirmation_response(
            state,
            ConfirmationResponse(
                action=ConfirmationAction.CONFIRM,
            ),
        )


def test_clarification_rejects_confirmed_state():
    """8. 验证不可直接向 CONFIRMED 等已收敛状态应用澄清结果"""
    q = DecisionQuestion(
        original_question="测试",
        clarified_question="未来三个月是否辞职？",
        status=DecisionQuestionStatus.CONFIRMED,
    )

    state = {
        "question": q,
        "clarification": None,
        "confirmed": True,
        "hexagram": None,
        "citations": [],
        "final_response": None,
    }

    assessment = ClarificationAssessment(
        needs_clarification=False,
        clarified_question="另一个问题",
    )

    with pytest.raises(
        LiuyaoPolicyError,
        match="不允许直接应用澄清结果",
    ):
        apply_clarification_assessment(
            state,
            assessment,
        )


def test_constraints_preserved_while_still_clarifying():
    """9. 验证如果尚未形成最终候选，reality_constraints 也绝不会被静默丢失"""
    state = create_initial_liuyao_state("我有房贷，想考虑辞职")

    assessment = ClarificationAssessment(
        needs_clarification=True,
        reality_constraints=["有房贷"],
        clarification_prompt="你希望考虑多长的时间范围？",
    )

    new_state = apply_clarification_assessment(
        state,
        assessment,
    )

    assert new_state["question"].reality_constraints == ["有房贷"]
