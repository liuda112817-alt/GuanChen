"""Stage 8 LangGraph PostgreSQL Checkpointer 封装。

设计约束（冻结规划）：
- 直接使用官方 langgraph-checkpoint-postgres，不手写 checkpoint engine；
- checkpointer 只负责 LangGraph thread state，与长期用户资料（SQLAlchemy）严格分层。
"""
import re

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from guanchen_v2.config.settings import DatabaseSettings

_ASYNC_PREFIX = re.compile(r"^postgresql\+asyncpg://")


def to_psycopg_conninfo(database_url: str) -> str:
    """asyncpg URL 转换为 psycopg 可用的连接串（去掉 +asyncpg 方言前缀）。"""
    return _ASYNC_PREFIX.sub("postgresql://", database_url)


class PostgresCheckpointerFactory:
    """创建官方 AsyncPostgresSaver 的唯一入口。"""

    @staticmethod
    async def create(
        database_url: str | None = None,
    ) -> tuple[AsyncPostgresSaver, AsyncConnectionPool]:
        """
        创建并初始化（setup）一个连接 PostgreSQL 的 AsyncPostgresSaver。

        返回 (saver, pool)：pool 必须由调用方在进程结束时负责 close。
        """
        url = database_url or DatabaseSettings().database_url

        pool = AsyncConnectionPool(
            conninfo=to_psycopg_conninfo(url),
            kwargs={"autocommit": True},
            open=False,
        )
        await pool.open()

        saver = AsyncPostgresSaver(pool)
        await saver.setup()

        return saver, pool

    @staticmethod
    async def close(pool: AsyncConnectionPool) -> None:
        await pool.close()
