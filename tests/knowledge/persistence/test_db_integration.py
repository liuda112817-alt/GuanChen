import numpy as np
import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError

from guanchen_v2.knowledge.persistence.database import async_session, engine, init_db
from guanchen_v2.knowledge.persistence.models import KnowledgeChunkRow, KnowledgeDocumentRow

# 注意：运行此测试需要本地真实的 PostgreSQL 服务（支持 pgvector）且配置了正确的 database_url
# 隔离标记，防止普通单元测试阻断
pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def setup_database():
    """每个测试前后重建 Schema 以保证干净的事务环境"""
    await init_db()
    yield
    from guanchen_v2.knowledge.persistence.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_document_round_trip():
    """验证 Document 的元数据无损存取"""
    doc_row = KnowledgeDocumentRow(
        document_id="doc_test_1",
        domain="bazi",
        source_title="《渊海子平》",
        source_type="public_domain_classic",
        section="卷一",
        text="天干地支...",
    )

    async with async_session() as session:
        session.add(doc_row)
        await session.commit()

    async with async_session() as session:
        result = await session.execute(
            select(KnowledgeDocumentRow).where(KnowledgeDocumentRow.document_id == "doc_test_1")
        )
        fetched = result.scalar_one_or_none()

        assert fetched is not None
        assert fetched.source_title == "《渊海子平》"
        assert fetched.text == "天干地支..."


@pytest.mark.asyncio
async def test_chunk_embedding_round_trip_and_fk_lineage():
    """验证 Chunk 向量存取及外键血缘 (FK) 不可断裂"""

    # 1. 制造孤立的 Chunk，期望外键拦截（因为没有插入对应的 Document）
    isolated_chunk = KnowledgeChunkRow(
        chunk_id="chunk_test_1",
        document_id="doc_test_1",  # 数据库中还不存在
        domain="bazi",
        source_title="《渊海子平》",
        source_type="public_domain_classic",
        section="卷一",
        text="甲乙丙丁",
        embedding=[0.1] * 512,
    )

    async with async_session() as session:
        session.add(isolated_chunk)
        with pytest.raises(IntegrityError):
            await session.commit()

    # 2. 正常流程：先有 Document，再有 Chunk
    doc_row = KnowledgeDocumentRow(
        document_id="doc_test_1",
        domain="bazi",
        source_title="《渊海子平》",
        source_type="public_domain_classic",
        section="卷一",
        text="天干地支...",
    )
    valid_chunk = KnowledgeChunkRow(
        chunk_id="chunk_test_1",
        document_id="doc_test_1",
        domain="bazi",
        source_title="《渊海子平》",
        source_type="public_domain_classic",
        section="卷一",
        text="甲乙丙丁",
        embedding=np.random.rand(512).tolist(),
    )

    async with async_session() as session:
        session.add(doc_row)
        session.add(valid_chunk)
        await session.commit()

    # 验证提取
    async with async_session() as session:
        result = await session.execute(
            select(KnowledgeChunkRow).where(KnowledgeChunkRow.chunk_id == "chunk_test_1")
        )
        fetched_chunk = result.scalar_one()
        assert len(fetched_chunk.embedding) == 512


@pytest.mark.asyncio
async def test_database_rejects_wrong_dimension():
    """【绝对核心】维度铁幕验证：数据库底层必须物理拒绝非 512 维向量"""
    doc_row = KnowledgeDocumentRow(
        document_id="doc_test_2",
        domain="bazi",
        source_title="《测试》",
        source_type="project_note",
        section="章一",
        text="正文",
    )

    # 强行混入 768 维向量
    bad_chunk = KnowledgeChunkRow(
        chunk_id="chunk_test_bad_dim",
        document_id="doc_test_2",
        domain="bazi",
        source_title="《测试》",
        source_type="project_note",
        section="章一",
        text="正文",
        embedding=[0.1] * 768,
    )

    async with async_session() as session:
        session.add(doc_row)
        session.add(bad_chunk)

        with pytest.raises(DBAPIError):
            await session.commit()
