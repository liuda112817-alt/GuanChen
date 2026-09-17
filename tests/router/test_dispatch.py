from unittest.mock import AsyncMock

import pytest

from guanchen_v2.router.contracts import IntentType, RequiredDataType, RoutingResult
from guanchen_v2.router.dispatch import SingleAgentDispatcher
from guanchen_v2.router.errors import RouterDispatchError
from guanchen_v2.router.requirements import RequirementCheckResult, RequirementContext, RequirementStatus


@pytest.fixture
def mock_adapters():
    return {
        IntentType.BAZI: AsyncMock(),
        IntentType.DREAM: AsyncMock(),
        IntentType.KNOWLEDGE: AsyncMock(),
        IntentType.LIUYAO: AsyncMock(),
    }


@pytest.fixture
def dispatcher(mock_adapters):
    return SingleAgentDispatcher(mock_adapters)


def test_dispatcher_rejects_non_professional_registry():
    """Case 1: 注册表禁止注册闲聊与 OOS"""
    with pytest.raises(RouterDispatchError, match="不能包含非专业 Agent"):
        SingleAgentDispatcher({IntentType.CHITCHAT: AsyncMock()})


@pytest.mark.asyncio
async def test_dispatch_ready_calls_target(dispatcher, mock_adapters):
    """Case 2: 准备妥当 -> 精准调用 1 次目标，其他不唤起"""
    routing = RoutingResult(primary_intent=IntentType.BAZI, confidence=1.0, required_data=(RequiredDataType.BIRTH_PROFILE,), reason="测试")
    req_result = RequirementCheckResult(intent=IntentType.BAZI, status=RequirementStatus.READY, required_data=(RequiredDataType.BIRTH_PROFILE,))
    context = RequirementContext(available_data={RequiredDataType.BIRTH_PROFILE: "Dummy"})

    await dispatcher.dispatch(routing, req_result, "测八字", context)

    assert mock_adapters[IntentType.BAZI].invoke.call_count == 1
    assert mock_adapters[IntentType.DREAM].invoke.call_count == 0
    assert mock_adapters[IntentType.KNOWLEDGE].invoke.call_count == 0


@pytest.mark.asyncio
async def test_dispatch_needs_input_bypasses_agents(dispatcher, mock_adapters):
    """Case 3: 缺少资料 (NEEDS_INPUT) -> 所有 Agent 调次数均为 0"""
    routing = RoutingResult(primary_intent=IntentType.DREAM, confidence=1.0, required_data=(RequiredDataType.DREAM_CONTENT,), reason="测试")
    req_result = RequirementCheckResult(
        intent=IntentType.DREAM,
        status=RequirementStatus.NEEDS_INPUT,
        required_data=(RequiredDataType.DREAM_CONTENT,),
        missing_data=(RequiredDataType.DREAM_CONTENT,),
    )

    res = await dispatcher.dispatch(routing, req_result, "解梦", RequirementContext())

    assert res is req_result  # 返回 orchestration 信息以供前端处理追问
    for adapter in mock_adapters.values():
        assert adapter.invoke.call_count == 0


@pytest.mark.asyncio
async def test_dispatch_chitchat_bypass(dispatcher, mock_adapters):
    """Case 4: BYPASS (如寒暄) -> 所有 Agent 调用次数均为 0"""
    routing = RoutingResult(primary_intent=IntentType.CHITCHAT, confidence=1.0, reason="hi")
    req_result = RequirementCheckResult(intent=IntentType.CHITCHAT, status=RequirementStatus.BYPASS)

    res = await dispatcher.dispatch(routing, req_result, "你好", RequirementContext())

    assert res is req_result
    for adapter in mock_adapters.values():
        assert adapter.invoke.call_count == 0


@pytest.mark.asyncio
async def test_dispatch_mismatch_intent_fails(dispatcher):
    """Case 5: 防御脏数据：如果路由结果与核对结果 Intent 发生漂移，立即阻断"""
    routing = RoutingResult(primary_intent=IntentType.BAZI, confidence=1.0, required_data=(RequiredDataType.BIRTH_PROFILE,), reason="测试")
    # 模拟外部意外传入了不匹配的 DREAM 的 CheckResult
    req_result = RequirementCheckResult(intent=IntentType.DREAM, status=RequirementStatus.READY, required_data=(RequiredDataType.DREAM_CONTENT,))

    with pytest.raises(RouterDispatchError, match="与 RequirementCheckResult intent 不一致"):
        await dispatcher.dispatch(routing, req_result, "问题", RequirementContext())


@pytest.mark.asyncio
async def test_dispatch_dual_domain_fails(dispatcher):
    """Case 6: 双领域试图挤名单领域 Dispatcher -> 立刻拒绝"""
    routing = RoutingResult(
        primary_intent=IntentType.BAZI,
        secondary_intents=(IntentType.DREAM,),
        confidence=1.0,
        required_data=(RequiredDataType.BIRTH_PROFILE, RequiredDataType.DREAM_CONTENT),
        reason="测试",
    )
    req_result = RequirementCheckResult(intent=IntentType.BAZI, status=RequirementStatus.READY, required_data=(RequiredDataType.BIRTH_PROFILE,))

    with pytest.raises(RouterDispatchError, match="不接受双领域"):
        await dispatcher.dispatch(routing, req_result, "问题", RequirementContext())


@pytest.mark.asyncio
async def test_dispatch_mismatch_context_fails(dispatcher):
    """验证防伪防线：当 RequirementCheckResult 合法，但它与传来的 Context 的重新计算不符合时报错"""
    routing = RoutingResult(primary_intent=IntentType.BAZI, confidence=1.0, required_data=(RequiredDataType.BIRTH_PROFILE,), reason="测试")
    # 这个 Requirement 是合法的，表明准备就绪
    req_result = RequirementCheckResult(intent=IntentType.BAZI, status=RequirementStatus.READY, required_data=(RequiredDataType.BIRTH_PROFILE,))
    # 但实际投递的上下文是空的！
    context = RequirementContext(available_data={})

    with pytest.raises(RouterDispatchError, match="RequirementCheckResult 与当前 RoutingResult / Context 不一致"):
        await dispatcher.dispatch(routing, req_result, "八字", context)


@pytest.mark.asyncio
async def test_knowledge_dispatch_never_requires_bazi(dispatcher, mock_adapters):
    """端到端拦截测试 1：知识查询就算上下文里什么都没有，也只会触发 Knowledge Adapter 而不会牵连八字检查"""
    routing = RoutingResult(
        primary_intent=IntentType.KNOWLEDGE,
        confidence=1.0,
        required_data=(),
        reason="知识问答",
    )
    # 这里也可以故意在 Context 里丢一个假出生数据看看会不会出错，但根据契约，不要求就不会检查
    context = RequirementContext(available_data={RequiredDataType.BIRTH_PROFILE: "干扰数据"})

    # 手动算一遍期待的 Requirement
    from guanchen_v2.router.requirements import check_requirements

    req = check_requirements(routing, context)
    assert req.status == RequirementStatus.READY

    await dispatcher.dispatch(routing, req, "什么是正官", context)

    assert mock_adapters[IntentType.KNOWLEDGE].invoke.call_count == 1
    assert mock_adapters[IntentType.BAZI].invoke.call_count == 0


@pytest.mark.asyncio
async def test_dream_dispatch_never_triggers_others(dispatcher, mock_adapters):
    """端到端拦截测试 2：解梦请求哪怕满足条件了，也绝不能连累别的 Agent"""
    routing = RoutingResult(primary_intent=IntentType.DREAM, confidence=1.0, required_data=(RequiredDataType.DREAM_CONTENT,), reason="测试梦")
    context = RequirementContext(available_data={RequiredDataType.DREAM_CONTENT: "昨晚梦见蛇"})

    from guanchen_v2.router.requirements import check_requirements

    req = check_requirements(routing, context)
    assert req.status == RequirementStatus.READY

    await dispatcher.dispatch(routing, req, "解梦蛇", context)

    assert mock_adapters[IntentType.DREAM].invoke.call_count == 1
    assert mock_adapters[IntentType.BAZI].invoke.call_count == 0
    assert mock_adapters[IntentType.LIUYAO].invoke.call_count == 0
    assert mock_adapters[IntentType.KNOWLEDGE].invoke.call_count == 0
