import pytest
from pydantic import ValidationError

from guanchen_v2.router.contracts import (
    IntentType,
    RequiredDataType,
    RoutingResult,
)


def test_valid_single_domain_bazi():
    """1. 单领域 BAZI -> BIRTH_PROFILE 合法"""
    result = RoutingResult(
        primary_intent=IntentType.BAZI,
        confidence=0.9,
        required_data=(RequiredDataType.BIRTH_PROFILE,),
        reason="用户明确要求排八字",
    )
    assert result.primary_intent == IntentType.BAZI
    assert result.secondary_intents == ()


def test_invalid_requirement_for_knowledge():
    """2. KNOWLEDGE + BIRTH_PROFILE 被拒绝。大模型不能凭空给 Knowledge 塞入出生要求"""
    with pytest.raises(ValidationError, match="必须严格匹配意图所要求的数据集合"):
        RoutingResult(
            primary_intent=IntentType.KNOWLEDGE,
            confidence=0.8,
            required_data=(RequiredDataType.BIRTH_PROFILE,),  # 非法多余
            reason="用户问什么是十神",
        )


def test_valid_dual_domain():
    """3. 显式 contract BAZI + DREAM -> BirthProfile + DreamContent 合法"""
    result = RoutingResult(
        primary_intent=IntentType.BAZI,
        secondary_intents=(IntentType.DREAM,),
        confidence=0.85,
        required_data=(RequiredDataType.BIRTH_PROFILE, RequiredDataType.DREAM_CONTENT),
        reason="用户希望结合八字来解梦",
    )
    assert result.primary_intent == IntentType.BAZI
    assert result.secondary_intents == (IntentType.DREAM,)
    assert set(result.required_data) == {RequiredDataType.BIRTH_PROFILE, RequiredDataType.DREAM_CONTENT}


def test_invalid_secondary_counts_and_overlap():
    """4. secondary 超过 1 个或与 primary 重复被拒绝"""
    with pytest.raises(ValidationError, match="Tuple should have at most 1 item"):
        RoutingResult(
            primary_intent=IntentType.BAZI,
            secondary_intents=(IntentType.DREAM, IntentType.LIUYAO),
            confidence=0.8,
            required_data=(RequiredDataType.BIRTH_PROFILE, RequiredDataType.DREAM_CONTENT, RequiredDataType.DECISION_QUESTION),
            reason="太多领域了",
        )

    with pytest.raises(ValidationError, match="primary_intent 不能出现在 secondary_intents 中"):
        RoutingResult(
            primary_intent=IntentType.BAZI,
            secondary_intents=(IntentType.BAZI,),
            confidence=0.9,
            required_data=(RequiredDataType.BIRTH_PROFILE,),
            reason="重复领域",
        )


def test_invalid_isolation_mixing():
    """5. CHITCHAT / OUT_OF_SCOPE 与专业 Intent 混搭被拒绝"""
    with pytest.raises(ValidationError, match="secondary_intents 不能包含 chitchat"):
        RoutingResult(
            primary_intent=IntentType.BAZI,
            secondary_intents=(IntentType.CHITCHAT,),
            confidence=0.9,
            required_data=(RequiredDataType.BIRTH_PROFILE,),
            reason="不能在八字时闲聊",
        )

    with pytest.raises(ValidationError, match="当 primary_intent 为 out_of_scope 时，secondary_intents 必须为空"):
        RoutingResult(
            primary_intent=IntentType.OUT_OF_SCOPE,
            secondary_intents=(IntentType.DREAM,),
            confidence=0.9,
            required_data=(RequiredDataType.DREAM_CONTENT,),
            reason="出界了不能再挂个解梦",
        )


def test_confidence_out_of_bounds():
    """6. confidence 越界被拒绝"""
    with pytest.raises(ValidationError, match="Input should be less than or equal to 1"):
        RoutingResult(
            primary_intent=IntentType.KNOWLEDGE,
            confidence=1.1,
            reason="过于自信",
        )

    with pytest.raises(ValidationError, match="Input should be greater than or equal to 0"):
        RoutingResult(
            primary_intent=IntentType.CHITCHAT,
            confidence=-0.5,
            reason="不够自信",
        )


def test_duplicate_required_data_rejected():
    """7. required_data 存在重复项被拒绝"""
    with pytest.raises(ValidationError, match="不允许包含重复项"):
        RoutingResult(
            primary_intent=IntentType.BAZI,
            confidence=0.8,
            required_data=(RequiredDataType.BIRTH_PROFILE, RequiredDataType.BIRTH_PROFILE),
            reason="重复提供出生要求",
        )
