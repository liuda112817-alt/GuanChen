from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from guanchen_v2.config.settings import DatabaseSettings


def create_async_engine_and_factory(
    database_url: str | None = None,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """
    创建独立的 AsyncEngine + sessionmaker。

    每个调用都会得到一套全新的 Engine / Factory：
    - 长时间运行的进程（scripts / FastAPI）在启动时创建一次即可；
    - 测试必须为每个测试函数创建独立实例，并在测试结束前 dispose，
      避免 asyncpg 连接池跨 event loop 复用导致
      "another operation is in progress" / "Event loop is closed" 类错误。
    """
    url = database_url or DatabaseSettings().database_url

    engine = create_async_engine(
        url,
        echo=False,
    )

    factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    return engine, factory


database_settings = DatabaseSettings()

# 进程级默认实例：供 scripts / 应用运行期使用。
engine, async_session_factory = create_async_engine_and_factory(
    database_settings.database_url
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI / 业务代码依赖注入入口。

    注意：依赖本生成器的请求必须运行在同一个 event loop 内。
    """
    async with async_session_factory() as session:
        yield session
