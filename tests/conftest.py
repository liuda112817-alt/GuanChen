"""全局测试基础设施。

约定（与 tests/knowledge 保持一致）：
- 所有依赖 PostgreSQL 的测试统一指向独立测试数据库 guanchen_test；
- DB 测试通过 `pytest -m integration` 运行；
- 每个 DB 测试使用独立 AsyncEngine（绑定到当前 event loop），
  并在 teardown 时 dispose，避免 asyncpg 连接池跨 loop 复用。
"""
import asyncio
import sys
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
)

from guanchen_v2.core.session.models import ConversationState
from guanchen_v2.memory.database import create_async_engine_and_factory
from guanchen_v2.memory.models import MemoryBase

# psycopg（langgraph-checkpoint-postgres 依赖）不支持 Windows ProactorEventLoop，
# 全局切换到 SelectorEventLoopPolicy，保证 checkpointer 集成测试可用。
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/guanchen_test"


@pytest.fixture
async def db_env() -> AsyncGenerator[tuple[AsyncEngine, async_sessionmaker], None]:
    """
    每个测试独立的数据库环境：全新表 + teardown 清空。

    覆盖 MemoryBase 全部表以及 langgraph-checkpoint-postgres 官方表。
    """
    engine, factory = create_async_engine_and_factory(TEST_DATABASE_URL)

    async with engine.begin() as conn:
        await conn.run_sync(MemoryBase.metadata.create_all)

    try:
        yield engine, factory
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(MemoryBase.metadata.drop_all)
            # langgraph-checkpoint-postgres 官方表：必须连同迁移追踪表一并清理，
            # 否则 setup() 会因 checkpoint_migrations 记录版本号而跳过真实建表。
            await conn.execute(text("DROP TABLE IF EXISTS checkpoints CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS checkpoint_blobs CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS checkpoint_writes CASCADE"))
            await conn.execute(text("DROP TABLE IF EXISTS checkpoint_migrations CASCADE"))
        await engine.dispose()


@pytest.fixture
async def postgres_session_factory(
    db_env: tuple[AsyncEngine, async_sessionmaker],
) -> async_sessionmaker:
    return db_env[1]


@pytest.fixture
def sample_state() -> ConversationState:
    return ConversationState(session_id="sample-session")
