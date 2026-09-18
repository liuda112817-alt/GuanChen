from unittest.mock import AsyncMock

import pytest

from guanchen_v2.application.exceptions import ConversationExecutionError
from guanchen_v2.application.orchestrator import ConversationOrchestrator
from guanchen_v2.memory.implementations.inmemory import InMemoryMemoryStore
from guanchen_v2.router.contracts import IntentType, RoutingResult
from guanchen_v2.router.synthesis import SynthesizedResponse


@pytest.fixture
def memory_store():
    return InMemoryMemoryStore()

@pytest.fixture
def mocks():
    router = AsyncMock()
    single_disp = AsyncMock()
    dual_disp = AsyncMock()
    synth = AsyncMock()
    
    # Setup Default happy path: CHITCHAT bypassing
    router.route.return_value = RoutingResult(
        primary_intent=IntentType.CHITCHAT,
        secondary_intents=(),
        confidence=1.0,
        required_data=(),
        reason="Test Routing"
    )
    synth.synthesize.return_value = SynthesizedResponse(
        content="Test Synth Content",
        used_intents=(IntentType.CHITCHAT,)
    )
    
    return router, single_disp, dual_disp, synth

@pytest.fixture
def orchestrator(memory_store, mocks):
    router, single_disp, dual_disp, synth = mocks
    return ConversationOrchestrator(
        memory_store=memory_store,
        router=router,
        single_dispatcher=single_disp,
        dual_dispatcher=dual_disp,
        synthesizer=synth
    )

@pytest.mark.asyncio
async def test_1_new_session_flow(orchestrator, memory_store):
    """Test 1: New Session Flow (无 session_id 初始化并正常走完流程)"""
    resp = await orchestrator.execute(session_id=None, user_query="Hello")
    
    assert resp.content == "Test Synth Content"
    
    # 验证底层的 Store 确实增加了一条状态
    assert len(memory_store._data) == 1
    session_id = list(memory_store._data.keys())[0]
    
    state = await memory_store.load(session_id)
    assert len(state.messages) == 2  # user + assistant
    assert state.messages[0].content == "Hello"
    assert state.messages[1].content == "Test Synth Content"

@pytest.mark.asyncio
async def test_2_existing_session_recovery(orchestrator, memory_store):
    """Test 2: Existing Session Recovery (使用已有 session_id 拉起)"""
    # 提前跑一次创造 session
    await orchestrator.execute(session_id="known-id", user_query="1")
    
    # 复用已知 ID
    await orchestrator.execute(session_id="known-id", user_query="2")
    
    state = await memory_store.load("known-id")
    assert len(state.messages) == 4 # (User + Assistant) x 2 轮
    assert state.messages[-2].content == "2"

@pytest.mark.asyncio
async def test_3_router_integration(orchestrator, mocks):
    """Test 3: Router Integration 确保 Orchestrator 调用了底层路由"""
    router, _, _, _ = mocks
    await orchestrator.execute(session_id="abc", user_query="请帮我解梦")
    
    router.route.assert_awaited_once_with("请帮我解梦")

@pytest.mark.asyncio
async def test_4_agent_failure_boundary(orchestrator, mocks, memory_store):
    """Test 4: Agent Failure 边界，不应污染 State 持久化记录"""
    router, single_disp, _, _ = mocks
    
    # 模拟一个实际会触发 Dispatch 的 Intent: KNOWLEDGE
    router.route.return_value = RoutingResult(
        primary_intent=IntentType.KNOWLEDGE,
        secondary_intents=(),
        confidence=1.0,
        required_data=(),
        reason="Knowledge Check"
    )
    
    # 模拟 Dispatch 过程突然崩溃
    single_disp.dispatch.side_effect = ValueError("Agent Runtime crashed")
    
    with pytest.raises(ConversationExecutionError):
        await orchestrator.execute(session_id="fail-test", user_query="什么是易经")
        
    state = await memory_store.load("fail-test")
    # 确保保存的依然是最初始状态（仅包含 UUID 拉起时的初始状态），不应被半成品的 user_message 污染覆盖
    assert len(state.messages) == 0

@pytest.mark.asyncio
async def test_6_session_isolation(orchestrator, memory_store):
    """Test 6: Session 物理隔离，互不干涉"""
    await orchestrator.execute(session_id="session-A", user_query="A 的问题")
    await orchestrator.execute(session_id="session-B", user_query="B 的问题")
    
    state_a = await memory_store.load("session-A")
    state_b = await memory_store.load("session-B")
    
    assert state_a.current_query == "A 的问题"
    assert state_b.current_query == "B 的问题"

