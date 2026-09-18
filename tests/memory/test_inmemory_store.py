import pytest

from guanchen_v2.core.session.models import ConversationState
from guanchen_v2.memory.exceptions import (
    MemoryAlreadyExistsError,
    MemoryNotFoundError,
)
from guanchen_v2.memory.implementations.inmemory import InMemoryMemoryStore


@pytest.fixture
def store() -> InMemoryMemoryStore:
    return InMemoryMemoryStore()


@pytest.mark.asyncio
async def test_1_save_and_load(store: InMemoryMemoryStore):
    """Test 1: 验证 Session 保存与加载，且必须切断 Object Identity"""
    original_state = ConversationState(session_id="session-1")
    await store.save(original_state)
    
    loaded_state = await store.load("session-1")
    
    assert loaded_state is not None
    assert loaded_state.session_id == "session-1"
    # 【核心验证】: 不能是同一个内存对象（模拟 DB 序列化边界）
    assert loaded_state is not original_state 
    # 数据等价
    assert loaded_state.model_dump() == original_state.model_dump()


@pytest.mark.asyncio
async def test_2_duplicate_save(store: InMemoryMemoryStore):
    """Test 2: 验证重复 Save 必须失败，保护现有数据"""
    state = ConversationState(session_id="session-2")
    await store.save(state)
    
    with pytest.raises(MemoryAlreadyExistsError):
        await store.save(state)


@pytest.mark.asyncio
async def test_3_update_existing(store: InMemoryMemoryStore):
    """Test 3: 验证存在的 Session 可以被正常 Update"""
    state = ConversationState(session_id="session-3", current_query="旧问题")
    await store.save(state)
    
    state.current_query = "新问题"
    await store.update(state)
    
    loaded_state = await store.load("session-3")
    assert loaded_state is not None
    assert loaded_state.current_query == "新问题"


@pytest.mark.asyncio
async def test_4_update_missing(store: InMemoryMemoryStore):
    """Test 4: 验证 Update 不存在的 Session 必须抛错"""
    non_exist_state = ConversationState(session_id="missing-4")
    
    with pytest.raises(MemoryNotFoundError):
        await store.update(non_exist_state)


@pytest.mark.asyncio
async def test_5_delete_idempotent(store: InMemoryMemoryStore):
    """Test 5: 验证删除功能，并确保其具备幂等性 (Idempotent)"""
    state = ConversationState(session_id="session-5")
    await store.save(state)
    
    # 第一次删除
    await store.delete("session-5")
    assert await store.load("session-5") is None
    
    # 第二次删除不存在的 ID，必须静默成功，不报错
    await store.delete("session-5") 
    await store.delete("never-existed")


@pytest.mark.asyncio
async def test_6_session_isolation(store: InMemoryMemoryStore):
    """Test 6: 验证不同的 Session ID 之间绝对隔离"""
    state_a = ConversationState(session_id="A", current_query="Query A")
    state_b = ConversationState(session_id="B", current_query="Query B")
    
    await store.save(state_a)
    await store.save(state_b)
    
    loaded_a = await store.load("A")
    loaded_b = await store.load("B")
    
    assert loaded_a is not None and loaded_b is not None
    assert loaded_a.current_query == "Query A"
    assert loaded_b.current_query == "Query B"

