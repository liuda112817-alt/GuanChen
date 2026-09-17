import pytest
from pydantic import ValidationError

from guanchen_v2.router.contracts import IntentType, RequiredDataType, RoutingResult
from guanchen_v2.router.errors import RouterDispatchError
from guanchen_v2.router.requirements import (
    RequirementCheckResult,
    RequirementContext,
    RequirementStatus,
    check_requirements,
)


def test_check_requirements_bazi_ready():
    """Case 1: BAZI + BirthProfile available -> READY"""
    routing = RoutingResult(primary_intent=IntentType.BAZI, confidence=1.0, required_data=(RequiredDataType.BIRTH_PROFILE,), reason="测试")
    context = RequirementContext(available_data={RequiredDataType.BIRTH_PROFILE: "DummyProfile"})

    result = check_requirements(routing, context)

    assert result.status == RequirementStatus.READY
    assert result.missing_data == ()


def test_check_requirements_bazi_needs_input():
    """Case 2: BAZI missing BirthProfile -> NEEDS_INPUT"""
    routing = RoutingResult(primary_intent=IntentType.BAZI, confidence=1.0, required_data=(RequiredDataType.BIRTH_PROFILE,), reason="测试")
    context = RequirementContext()  # 空上下文

    result = check_requirements(routing, context)

    assert result.status == RequirementStatus.NEEDS_INPUT
    assert result.missing_data == (RequiredDataType.BIRTH_PROFILE,)


def test_check_requirements_knowledge_ready():
    """Case 3: KNOWLEDGE + empty context -> READY (因为知识域不要上下文)"""
    routing = RoutingResult(primary_intent=IntentType.KNOWLEDGE, confidence=1.0, required_data=(), reason="测试")
    context = RequirementContext()

    result = check_requirements(routing, context)

    assert result.status == RequirementStatus.READY
    assert result.missing_data == ()


def test_check_requirements_bypass():
    """Case 4: CHITCHAT / OOS -> BYPASS"""
    routing1 = RoutingResult(primary_intent=IntentType.CHITCHAT, confidence=1.0, reason="hi")
    result1 = check_requirements(routing1, RequirementContext())
    assert result1.status == RequirementStatus.BYPASS

    routing2 = RoutingResult(primary_intent=IntentType.OUT_OF_SCOPE, confidence=1.0, reason="code")
    result2 = check_requirements(routing2, RequirementContext())
    assert result2.status == RequirementStatus.BYPASS


def test_check_requirements_rejects_dual_domain():
    """Case 5: 双领域直接 Fail-fast 拒绝进入单领域 Checker"""
    routing = RoutingResult(
        primary_intent=IntentType.BAZI,
        secondary_intents=(IntentType.DREAM,),
        confidence=1.0,
        required_data=(RequiredDataType.BIRTH_PROFILE, RequiredDataType.DREAM_CONTENT),
        reason="测试",
    )

    with pytest.raises(RouterDispatchError, match="不接受双领域"):
        check_requirements(routing, RequirementContext())


def test_requirement_result_rejects_missing_data_on_ready():
    """验证非法状态构造：READY 不能带有 missing_data"""
    with pytest.raises(ValidationError, match="READY 状态不能包含 missing_data"):
        RequirementCheckResult(
            intent=IntentType.BAZI,
            status=RequirementStatus.READY,
            required_data=(RequiredDataType.BIRTH_PROFILE,),
            missing_data=(RequiredDataType.BIRTH_PROFILE,),  # 非法！
        )


def test_requirement_result_rejects_empty_missing_on_needs_input():
    """验证非法状态构造：NEEDS_INPUT 不能没有 missing_data"""
    with pytest.raises(ValidationError, match="NEEDS_INPUT 必须包含 missing_data"):
        RequirementCheckResult(
            intent=IntentType.DREAM,
            status=RequirementStatus.NEEDS_INPUT,
            required_data=(RequiredDataType.DREAM_CONTENT,),
            missing_data=(),  # 非法！
        )


def test_requirement_result_rejects_bypass_for_professional_intent():
    """验证非法状态构造：专业能力不能乱挂 BYPASS"""
    with pytest.raises(ValidationError, match="专业 Intent 不能使用 BYPASS 状态"):
        RequirementCheckResult(
            intent=IntentType.LIUYAO, status=RequirementStatus.BYPASS, required_data=(RequiredDataType.DECISION_QUESTION,), missing_data=()
        )


def test_liuyao_question_seed_is_enough_to_start():
    """验证：六爻意图只要有最基本的用户问题输入 (Seed) 就可以过 READY 进入它的 workflow，不需要提前确认好"""
    routing = RoutingResult(primary_intent=IntentType.LIUYAO, confidence=1.0, required_data=(RequiredDataType.DECISION_QUESTION,), reason="测试")
    context = RequirementContext(available_data={RequiredDataType.DECISION_QUESTION: "我今年能脱单吗"})

    result = check_requirements(routing, context)
    assert result.status == RequirementStatus.READY
    assert result.missing_data == ()


def test_requirement_context_rejects_none_value():
    """验证非法状态构造：available_data 中声称拥有的数据不能是虚假的 None"""
    with pytest.raises(
        ValidationError,
        match="不能为 None",
    ):
        RequirementContext(
            available_data={
                RequiredDataType.BIRTH_PROFILE: None,
            }
        )
