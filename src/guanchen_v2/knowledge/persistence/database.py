from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from guanchen_v2.config.settings import Settings
from guanchen_v2.knowledge.errors import KnowledgePersistenceError
from guanchen_v2.knowledge.persistence.models import Base

settings = Settings()
engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    """
    启动数据库表结构。
    注意：必须在建表前创建 Vector 扩展，否则 ChunkRow 的 Vector(512) 会报错。
    """
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        raise KnowledgePersistenceError("知识库数据库初始化失败。") from exc
