import pytest

from guanchen_v2.memory.implementations.postgres import (
    PostgresMemoryStore,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_postgres_memory_save_load(
    postgres_session_factory,
    sample_state,
):

    store = PostgresMemoryStore(
        postgres_session_factory
    )

    await store.save(sample_state)

    loaded = await store.load(
        sample_state.session_id
    )

    assert loaded is not None

    assert (
        loaded.session_id
        ==
        sample_state.session_id
    )


@pytest.mark.asyncio
async def test_postgres_memory_save_existing_raises(
    postgres_session_factory,
    sample_state,
):
    """save 重复 session 必须拒绝覆盖。"""
    from guanchen_v2.memory.exceptions import MemoryAlreadyExistsError

    store = PostgresMemoryStore(postgres_session_factory)
    await store.save(sample_state)

    with pytest.raises(MemoryAlreadyExistsError):
        await store.save(sample_state)


@pytest.mark.asyncio
async def test_postgres_memory_update_and_delete(
    postgres_session_factory,
    sample_state,
):
    """update / delete 生命周期：不存在时 update 必须报错，delete 幂等。"""
    from guanchen_v2.core.session.models import MessageState
    from guanchen_v2.memory.exceptions import MemoryNotFoundError

    store = PostgresMemoryStore(postgres_session_factory)

    with pytest.raises(MemoryNotFoundError):
        await store.update(sample_state)

    await store.save(sample_state)

    sample_state.messages.append(MessageState(role="user", content="你好"))
    await store.update(sample_state)

    loaded = await store.load(sample_state.session_id)
    assert loaded is not None
    assert len(loaded.messages) == 1

    await store.delete(sample_state.session_id)
    assert await store.load(sample_state.session_id) is None

    # delete 幂等
    await store.delete(sample_state.session_id)
