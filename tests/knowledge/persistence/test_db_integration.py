import pytest
from sqlalchemy import select
from sqlalchemy.exc import (
    DBAPIError,
    IntegrityError,
)

from guanchen_v2.knowledge.persistence.database import (
    async_session,
    dispose_db,
    get_engine,
    init_db,
)
from guanchen_v2.knowledge.persistence.models import (
    Base,
    KnowledgeChunkRow,
    KnowledgeDocumentRow,
)

pytestmark = pytest.mark.integration


EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"


@pytest.fixture(autouse=True)
async def setup_database():
    """
    每个 integration test 使用独立 DB runtime。

    pytest-asyncio 默认给每个 test function 创建独立 event loop，
    因此必须在当前 loop 关闭前 dispose AsyncEngine，
    避免 asyncpg pool connection 被带入下一个 event loop。
    """
    await init_db()

    try:
        yield
    finally:
        try:
            async with get_engine().begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
        finally:
            await dispose_db()


@pytest.mark.asyncio
async def test_document_round_trip():
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
        result = await session.execute(select(KnowledgeDocumentRow).where(KnowledgeDocumentRow.document_id == "doc_test_1"))

        fetched = result.scalar_one_or_none()

    assert fetched is not None
    assert fetched.source_title == "《渊海子平》"
    assert fetched.text == "天干地支..."


@pytest.mark.asyncio
async def test_chunk_embedding_round_trip_and_fk_lineage():
    """
    验证：
    - Chunk FK lineage
    - vector(512)
    - embedding_model persistence
    """

    isolated_chunk = KnowledgeChunkRow(
        chunk_id="chunk_test_1",
        document_id="doc_test_1",
        domain="bazi",
        source_title="《渊海子平》",
        source_type="public_domain_classic",
        section="卷一",
        text="甲乙丙丁",
        embedding=[0.1] * 512,
        embedding_model=EMBEDDING_MODEL,
    )

    async with async_session() as session:
        session.add(isolated_chunk)

        with pytest.raises(IntegrityError):
            await session.commit()

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
        embedding=[0.1] * 512,
        embedding_model=EMBEDDING_MODEL,
    )

    async with async_session() as session:
        session.add(doc_row)
        await session.flush()
        session.add(valid_chunk)
        await session.commit()

    async with async_session() as session:
        result = await session.execute(select(KnowledgeChunkRow).where(KnowledgeChunkRow.chunk_id == "chunk_test_1"))

        fetched_chunk = result.scalar_one()

    assert len(fetched_chunk.embedding) == 512

    assert fetched_chunk.embedding_model == EMBEDDING_MODEL


@pytest.mark.asyncio
async def test_database_rejects_wrong_dimension():
    """
    PostgreSQL pgvector 必须拒绝非 512 维向量。
    """

    doc_row = KnowledgeDocumentRow(
        document_id="doc_test_2",
        domain="bazi",
        source_title="《测试》",
        source_type="project_note",
        section="章一",
        text="正文",
    )

    bad_chunk = KnowledgeChunkRow(
        chunk_id="chunk_test_bad_dim",
        document_id="doc_test_2",
        domain="bazi",
        source_title="《测试》",
        source_type="project_note",
        section="章一",
        text="正文",
        embedding=[0.1] * 768,
        embedding_model=EMBEDDING_MODEL,
    )

    async with async_session() as session:
        session.add(doc_row)
        session.add(bad_chunk)

        with pytest.raises(DBAPIError):
            await session.commit()
