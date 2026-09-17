from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from guanchen_v2.router.contracts import IntentType, RequiredDataType
from guanchen_v2.router.core import (
    HighPrecisionRuleRouter,
    RouterDecision,
    TwoLayerIntentRouter,
)


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    # 默认兜底 mock，确保走 LLM 时的基础返回类型
    llm.generate_structured.return_value = RouterDecision(primary_intent=IntentType.OUT_OF_SCOPE, confidence=0.8, reason="Mock fallback")
    return llm


@pytest.fixture
def router(mock_llm):
    return TwoLayerIntentRouter(
        rule_router=HighPrecisionRuleRouter(),
        llm_client=mock_llm,
    )


@pytest.mark.asyncio
async def test_router_bazi_rule_hit(router, mock_llm):
    """Case: 帮我看看我的八字事业 -> BAZI, LLM call=0"""
    res = await router.route("帮我看看我的八字事业")

    assert res.primary_intent == IntentType.BAZI
    assert RequiredDataType.BIRTH_PROFILE in res.required_data
    assert mock_llm.generate_structured.call_count == 0


@pytest.mark.asyncio
async def test_router_dream_rule_hit(router, mock_llm):
    """Case: 昨晚梦到一条蛇，帮我解释一下 -> DREAM, LLM call=0"""
    res = await router.route("昨晚梦到一条蛇，帮我解释一下")

    assert res.primary_intent == IntentType.DREAM
    assert RequiredDataType.DREAM_CONTENT in res.required_data
    assert mock_llm.generate_structured.call_count == 0


@pytest.mark.asyncio
async def test_router_liuyao_rule_hit(router, mock_llm):
    """Case: 帮我起一卦看看要不要离职 -> LIUYAO, LLM call=0"""
    res = await router.route("帮我起一卦看看要不要离职")

    assert res.primary_intent == IntentType.LIUYAO
    assert RequiredDataType.DECISION_QUESTION in res.required_data
    assert mock_llm.generate_structured.call_count == 0


@pytest.mark.asyncio
async def test_router_knowledge_rule_hit(router, mock_llm):
    """Case: 正官是什么意思？ -> KNOWLEDGE, LLM call=0"""
    res = await router.route("正官是什么意思？")

    assert res.primary_intent == IntentType.KNOWLEDGE
    assert res.required_data == ()  # Knowledge 绝不能请求其他资料
    assert mock_llm.generate_structured.call_count == 0


@pytest.mark.asyncio
async def test_router_chitchat_rule_hit(router, mock_llm):
    """Case: 你好 -> CHITCHAT, LLM call=0"""
    res = await router.route("你好")

    assert res.primary_intent == IntentType.CHITCHAT
    assert mock_llm.generate_structured.call_count == 0


@pytest.mark.asyncio
async def test_router_out_of_scope_rule_hit(router, mock_llm):
    """Case: 帮我写一段Python代码 -> OOS, LLM call=0"""
    res = await router.route("帮我写一段Python代码")

    assert res.primary_intent == IntentType.OUT_OF_SCOPE
    assert mock_llm.generate_structured.call_count == 0


@pytest.mark.asyncio
async def test_router_llm_fallback_enrichment(router, mock_llm):
    """Case: 规则未命中，进入 LLM Fallback 消歧 -> LLM call=1"""
    # 模拟大模型判定为 LIUYAO
    mock_llm.generate_structured.return_value = RouterDecision(
        primary_intent=IntentType.LIUYAO, confidence=0.85, reason="用户围绕具体工作选择请求传统占卜式决策参考"
    )

    # 采用真正需要 LLM 语义消歧，且业务意图高度贴合六爻的表达
    res = await router.route("最近有两个工作机会拿不定主意，想用传统占卜方式参考一下")

    assert res.primary_intent == IntentType.LIUYAO
    assert RequiredDataType.DECISION_QUESTION in res.required_data
    assert mock_llm.generate_structured.call_count == 1


@pytest.mark.asyncio
async def test_router_dual_domain_rule_hit(router, mock_llm):
    """Case: 显式结合规则 -> Dual Domain, LLM call=0"""
    res = await router.route("结合我的八字和昨晚的梦一起看看")

    assert res.primary_intent == IntentType.BAZI
    assert IntentType.DREAM in res.secondary_intents
    # 双重 requirement 自动化拼装
    assert set(res.required_data) == {RequiredDataType.BIRTH_PROFILE, RequiredDataType.DREAM_CONTENT}
    assert mock_llm.generate_structured.call_count == 0


@pytest.mark.asyncio
async def test_router_mention_does_not_trigger_dual(router, mock_llm):
    """Case: 我梦见有人给我算八字 -> LLM Fallback (DREAM), LLM call=1"""
    # 规则无法命中，交给大模型
    # 模拟大模型遵从 Prompt 契约，仅判定为 DREAM，而没有附加 BAZI
    mock_llm.generate_structured.return_value = RouterDecision(primary_intent=IntentType.DREAM, confidence=0.88, reason="提及算命，但本身是一个梦境")

    res = await router.route("昨天睡觉的时候，梦里有个道士帮我排八字，这是啥意思？")

    assert res.primary_intent == IntentType.DREAM
    assert res.secondary_intents == ()  # 大模型只输出了 DREAM

    # Python 代码自动基于 Intent 计算 Requirement，安全可信，DREAM 绝对不含 BirthProfile
    assert res.required_data == (RequiredDataType.DREAM_CONTENT,)
    assert mock_llm.generate_structured.call_count == 1


@pytest.mark.asyncio
async def test_router_domain_comparison_is_knowledge(router, mock_llm):
    """验证包含领域词的概念对比请求会被优先分发给 Knowledge"""
    res = await router.route("看看八字和六爻有什么区别？")

    assert res.primary_intent == IntentType.KNOWLEDGE
    assert res.secondary_intents == ()
    assert res.required_data == ()
    assert mock_llm.generate_structured.call_count == 0


@pytest.mark.asyncio
async def test_router_personal_dream_meaning_not_knowledge(router, mock_llm):
    """验证带有明确个人暗示特征的解梦不会被 Knowledge 抢走，并能命中增强后的 Dream 规则"""
    mock_llm.generate_structured.return_value = RouterDecision(
        primary_intent=IntentType.DREAM,
        confidence=0.9,
        reason="用户请求解释自己的具体梦境",
    )

    res = await router.route("我昨晚梦到蛇是什么意思？")

    assert res.primary_intent == IntentType.DREAM
    assert res.secondary_intents == ()
    # 命中扩充后的 DREAM 规则，不需要耗费一次 LLM 调用
    assert mock_llm.generate_structured.call_count == 0


def test_router_decision_rejects_non_combinable_secondary():
    """验证 RouterDecision schema 自身能够死守非法组合"""
    with pytest.raises(ValidationError, match="secondary_intents 只能包含专业领域"):
        RouterDecision(
            primary_intent=IntentType.BAZI,
            secondary_intents=(IntentType.CHITCHAT,),
            confidence=0.9,
            reason="非法组合",
        )
