from unittest.mock import AsyncMock

import pytest

from guanchen_v2.router.contracts import IntentType, RequiredDataType, RoutingResult
from guanchen_v2.router.dual_dispatch import AgentExecutionResult, DualDomainDispatcher
from guanchen_v2.router.errors import RouterDispatchError
from guanchen_v2.router.requirements import RequirementContext


@pytest.fixture
def mock_adapters():
    def create_adapter(return_val: str):
        adapter = AsyncMock()
        adapter.invoke.return_value = return_val
        return adapter

    return {
        IntentType.BAZI: create_adapter("bazi_result"),
        IntentType.DREAM: create_adapter("dream_result"),
        IntentType.LIUYAO: create_adapter("liuyao_result"),
    }


@pytest.fixture
def dispatcher(mock_adapters):
    return DualDomainDispatcher(mock_adapters)


def test_dual_dispatcher_rejects_non_professional_registry():
    """验证注册表合法性：禁止闲聊进入双领域配置"""
    with pytest.raises(RouterDispatchError, match="不能包含非专业 Agent"):
        DualDomainDispatcher({IntentType.CHITCHAT: AsyncMock()})


@pytest.mark.asyncio
async def test_dual_dispatcher_rejects_single_domain(dispatcher):
    """验证路由契约：坚决拒绝单领域请求挤进双领域 Dispatcher"""
    routing = RoutingResult(primary_intent=IntentType.BAZI, confidence=1.0, required_data=(RequiredDataType.BIRTH_PROFILE,), reason="单领域")

    with pytest.raises(RouterDispatchError, match="仅接受双领域请求"):
        await dispatcher.dispatch(routing, "测试", RequirementContext())


@pytest.mark.asyncio
async def test_dual_dispatcher_rejects_missing_adapters(mock_adapters):
    """验证防御机制：如果要求的 Agent 没注册，必须 Fail-fast"""
    # 故意剔除 DREAM adapter
    partial_registry = {IntentType.BAZI: mock_adapters[IntentType.BAZI]}
    bad_dispatcher = DualDomainDispatcher(partial_registry)

    routing = RoutingResult(
        primary_intent=IntentType.BAZI,
        secondary_intents=(IntentType.DREAM,),
        confidence=1.0,
        required_data=(RequiredDataType.BIRTH_PROFILE, RequiredDataType.DREAM_CONTENT),
        reason="双领域",
    )

    with pytest.raises(RouterDispatchError, match="缺少处理 dream 的 AgentAdapter"):
        await bad_dispatcher.dispatch(routing, "测试", RequirementContext())


@pytest.mark.asyncio
async def test_dual_dispatcher_executes_sequentially(dispatcher, mock_adapters):
    """验证 Happy Path：串行调用，结果被正确包装进 AgentExecutionResult"""
    routing = RoutingResult(
        primary_intent=IntentType.BAZI,
        secondary_intents=(IntentType.DREAM,),
        confidence=1.0,
        required_data=(RequiredDataType.BIRTH_PROFILE, RequiredDataType.DREAM_CONTENT),
        reason="结合八字和梦境",
    )
    context = RequirementContext(available_data={RequiredDataType.BIRTH_PROFILE: "profile", RequiredDataType.DREAM_CONTENT: "content"})

    results = await dispatcher.dispatch(routing, "联合分析", context)

    # 验证底层被精确调用
    mock_adapters[IntentType.BAZI].invoke.assert_awaited_once_with("联合分析", context)
    mock_adapters[IntentType.DREAM].invoke.assert_awaited_once_with("联合分析", context)
    # 不相干的 Agent 绝对不会被唤起
    mock_adapters[IntentType.LIUYAO].invoke.assert_not_called()

    # 验证返回契约
    assert len(results) == 2

    assert isinstance(results[0], AgentExecutionResult)
    assert results[0].intent == IntentType.BAZI
    assert results[0].output == "bazi_result"

    assert isinstance(results[1], AgentExecutionResult)
    assert results[1].intent == IntentType.DREAM
    assert results[1].output == "dream_result"
