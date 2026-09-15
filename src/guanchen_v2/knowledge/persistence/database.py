from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from guanchen_v2.config.settings import (
    DatabaseSettings,
)
from guanchen_v2.knowledge.errors import (
    KnowledgePersistenceError,
)
from guanchen_v2.knowledge.persistence.models import (
    Base,
)


class DatabaseRuntime:
    """
    GuanChen Knowledge DB runtime。

    一个 runtime 明确绑定：
    - 一个 database_url
    - 一个 AsyncEngine
    - 一个 async_sessionmaker

    DatabaseRuntime 的创建本身不会发生在模块 import 阶段。
    """

    def __init__(
        self,
        *,
        database_url: str,
        echo: bool = False,
    ) -> None:
        if not database_url.strip():
            raise KnowledgePersistenceError("数据库连接地址不能为空。")

        try:
            self._engine = create_async_engine(
                database_url,
                echo=echo,
            )

            self._session_factory = async_sessionmaker[AsyncSession](
                self._engine,
                expire_on_commit=False,
            )

        except Exception as exc:
            raise KnowledgePersistenceError("数据库运行时初始化失败。") from exc

    @property
    def engine(
        self,
    ) -> AsyncEngine:
        return self._engine

    @property
    def session_factory(
        self,
    ) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    def create_session(
        self,
    ) -> AsyncSession:
        return self._session_factory()

    async def init_schema(
        self,
    ) -> None:
        """
        初始化 pgvector extension 与 ORM schema。
        """
        try:
            async with self._engine.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

                await conn.run_sync(Base.metadata.create_all)

        except Exception as exc:
            raise KnowledgePersistenceError("知识库数据库初始化失败。") from exc

    async def dispose(
        self,
    ) -> None:
        """
        释放 SQLAlchemy connection pool。
        """
        try:
            await self._engine.dispose()

        except Exception as exc:
            raise KnowledgePersistenceError("数据库连接池释放失败。") from exc


_default_runtime: DatabaseRuntime | None = None


def create_database_runtime(
    *,
    database_url: str,
    echo: bool = False,
) -> DatabaseRuntime:
    """
    显式创建独立 DatabaseRuntime。

    适用于：
    - tests
    - scripts
    - future dependency injection
    - 独立数据库任务

    不修改模块级 default runtime。
    """
    return DatabaseRuntime(
        database_url=database_url,
        echo=echo,
    )


def get_database_runtime(
    *,
    settings: DatabaseSettings | None = None,
) -> DatabaseRuntime:
    """
    获取进程级默认 DatabaseRuntime。

    首次调用时才：
    1. 创建 DatabaseSettings；
    2. 读取数据库配置；
    3. 创建 AsyncEngine；
    4. 创建 Session Factory。

    import 本模块本身没有数据库配置读取或 Engine side effect。
    """
    global _default_runtime

    if _default_runtime is not None:
        return _default_runtime

    database_settings = settings if settings is not None else DatabaseSettings()

    _default_runtime = create_database_runtime(database_url=(database_settings.database_url))

    return _default_runtime


def get_engine() -> AsyncEngine:
    """
    获取默认 lazy AsyncEngine。
    """
    return get_database_runtime().engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    获取默认 lazy async_sessionmaker。
    """
    return get_database_runtime().session_factory


def async_session() -> AsyncSession:
    """
    创建默认数据库 AsyncSession。

    保持现有调用方式：

        async with async_session() as session:
            ...

    同时避免模块 import 时创建 Engine。
    """
    return get_database_runtime().create_session()


async def init_db() -> None:
    """
    初始化默认 Knowledge DB schema。
    """
    await get_database_runtime().init_schema()


async def dispose_db() -> None:
    """
    释放默认数据库 runtime。

    主要用于：
    - application shutdown
    - integration tests
    - scripts teardown

    dispose 后下一次访问数据库会重新 lazy 创建 runtime。
    """
    global _default_runtime

    runtime = _default_runtime

    if runtime is None:
        return

    await runtime.dispose()

    _default_runtime = None
