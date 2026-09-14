from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from guanchen_v2.knowledge.embeddings import BgeEmbeddingAdapter
from guanchen_v2.knowledge.errors import KnowledgeTransactionError
from guanchen_v2.knowledge.ingestion.chunker import KnowledgeDocumentChunker
from guanchen_v2.knowledge.ingestion.errors import KnowledgeChunkingError
from guanchen_v2.knowledge.ingestion.service import KnowledgeIngestionService
from guanchen_v2.knowledge.models import KnowledgeDocument, KnowledgeDomain, SourceType
from guanchen_v2.knowledge.persistence.database import async_session, engine, init_db
from guanchen_v2.knowledge.persistence.models import KnowledgeChunkRow, KnowledgeDocumentRow

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def setup_database():
    """每次运行测试前清空环境，重建立 PGVector 架构表。"""
    await init_db()
    yield
    from guanchen_v2.knowledge.persistence.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def _create_mock_adapter():
    """造一个假的大模型，返回确定性、数量相等的纯假 512 维列表。"""
    adapter = MagicMock(spec=BgeEmbeddingAdapter)
    adapter.embed_documents.side_effect = lambda chunks: [[0.5] * 512 for _ in chunks]
    return adapter


def _create_test_doc(text: str) -> KnowledgeDocument:
    return KnowledgeDocument.from_parser(
        domain=KnowledgeDomain.BAZI,
        source_title="《渊海子平》",
        source_type=SourceType.PUBLIC_DOMAIN_CLASSIC,
        section="卷一 / 测试",
        text=text,
    )


@pytest.mark.asyncio
async def test_empty_chunks_fails_fast():
    """S0 异常防线：不能悄无声息地跳过未产生 Chunk 的残破文档。"""
    chunker = MagicMock()
    chunker.chunk_document.return_value = []
    service = KnowledgeIngestionService(chunker, _create_mock_adapter())

    doc = _create_test_doc("将被 Mock 掉的文本")
    with pytest.raises(KnowledgeChunkingError, match="未产生任何 Chunk"):
        await service.ingest_document(doc)


@pytest.mark.asyncio
async def test_idempotent_ingestion_success_happy_path():
    """S1 首次完美摄入验证。确认 Document 和衍生 Chunk 被无损保存。"""
    doc = _create_test_doc("一段非常普通的初版测试文字，用于基础查验。")
    chunker = KnowledgeDocumentChunker(max_chars=800, chunk_overlap=80)
    service = KnowledgeIngestionService(chunker, _create_mock_adapter())

    await service.ingest_document(doc)

    async with async_session() as session:
        res_doc = await session.execute(
            select(KnowledgeDocumentRow).where(KnowledgeDocumentRow.document_id == doc.document_id)
        )
        assert res_doc.scalar_one().text == "一段非常普通的初版测试文字，用于基础查验。"

        res_chunks = await session.execute(
            select(KnowledgeChunkRow).where(KnowledgeChunkRow.document_id == doc.document_id)
        )
        saved_chunks = res_chunks.scalars().all()
        assert len(saved_chunks) == 1
        assert len(saved_chunks[0].embedding) == 512


@pytest.mark.asyncio
async def test_idempotent_ingestion_identical_repeat_no_extra_rows():
    """S2 完全重复输入测试。必须维持稳定的一行记录和原样 Chunk，严禁行数膨胀！"""
    doc = _create_test_doc("不会变化的千古真理。")
    chunker = KnowledgeDocumentChunker(max_chars=800, chunk_overlap=80)
    service = KnowledgeIngestionService(chunker, _create_mock_adapter())

    await service.ingest_document(doc)
    await service.ingest_document(doc)

    async with async_session() as session:
        docs = (await session.execute(select(KnowledgeDocumentRow))).scalars().all()
        assert len(docs) == 1
        chunks = (await session.execute(select(KnowledgeChunkRow))).scalars().all()
        assert len(chunks) == 1


@pytest.mark.asyncio
async def test_idempotent_ingestion_text_update_replaces_chunks():
    """S3 高级幂等：旧历史必须全被物理除名，绝不留痕。"""
    # 故意设积极短的切割长度，迫使长文本产生大量的碎片 (Chunk)
    chunker = KnowledgeDocumentChunker(max_chars=50, chunk_overlap=5)
    service = KnowledgeIngestionService(chunker, _create_mock_adapter())

    # 模拟初版入库产生了多个切片
    doc_v1 = _create_test_doc("旧版文本一。" * 20)
    await service.ingest_document(doc_v1)

    async with async_session() as session:
        chunks_v1 = (await session.execute(select(KnowledgeChunkRow))).scalars().all()
        old_chunk_ids = {c.chunk_id for c in chunks_v1}
        assert len(old_chunk_ids) > 1

    # 同一个 document_id，但文案全部更新
    doc_v2 = _create_test_doc("全新的颠覆性文本二号，旧版全部作废！" * 15)
    await service.ingest_document(doc_v2)

    async with async_session() as session:
        docs = (await session.execute(select(KnowledgeDocumentRow))).scalars().all()
        assert len(docs) == 1
        assert "全新的颠覆性文本二号" in docs[0].text

        chunks_v2 = (await session.execute(select(KnowledgeChunkRow))).scalars().all()
        new_chunk_ids = {c.chunk_id for c in chunks_v2}

        # 绝大部分旧 ID 必须全部被物理删除，绝不能出现新老交织的混合态
        assert len(new_chunk_ids) > 1
        assert not old_chunk_ids.intersection(new_chunk_ids)


@pytest.mark.asyncio
async def test_idempotent_ingestion_rollback_on_partial_failure():
    """S4 终极战役：基于 PostgreSQL 底层报错触发的物理级大回滚。"""
    chunker = KnowledgeDocumentChunker(max_chars=800, chunk_overlap=80)
    adapter = MagicMock(spec=BgeEmbeddingAdapter)

    # 设局：只要碰到含有特定词汇的 Chunk，就向数据库返回 PostgreSQL pgvector 无法忍受的 768 维瞎编向量！
    def fake_embed(chunks):
        if "造反" in chunks[0].text:
            return [[0.5] * 768 for _ in chunks]
        return [[0.5] * 512 for _ in chunks]

    adapter.embed_documents.side_effect = fake_embed
    service = KnowledgeIngestionService(chunker, adapter)

    # Phase A：初版入库
    doc_v1 = _create_test_doc("绝不容篡改的正确初版。")
    await service.ingest_document(doc_v1)

    async with async_session() as session:
        old_chunks = (await session.execute(select(KnowledgeChunkRow))).scalars().all()
        old_chunk_ids = {c.chunk_id for c in old_chunks}

    # Phase B：模拟灾难现场
    # 此时：1. UPSERT 已完成; 2. DELETE 旧 Chunk 已完成; 3. INSERT 768维新 Chunk 惨遭 PostgreSQL 拒绝！
    doc_v2 = _create_test_doc("这版文本很正常，但我要在数据写入环节造反。")
    with pytest.raises(KnowledgeTransactionError, match="知识文档幂等替换失败"):
        await service.ingest_document(doc_v2)

    # Phase C：探查战后现场（验证数据库原子性保障）
    async with async_session() as session:
        # Document 回退如初
        saved_doc = (
            await session.execute(
                select(KnowledgeDocumentRow).where(
                    KnowledgeDocumentRow.document_id == doc_v1.document_id
                )
            )
        ).scalar_one()
        assert saved_doc.text == "绝不容篡改的正确初版。"

        # 那些在事务中曾被 DELETE 的 Chunk 又满血复活了！
        saved_chunks = (
            (
                await session.execute(
                    select(KnowledgeChunkRow).where(
                        KnowledgeChunkRow.document_id == doc_v1.document_id
                    )
                )
            )
            .scalars()
            .all()
        )
        saved_chunk_ids = {c.chunk_id for c in saved_chunks}
        assert saved_chunk_ids == old_chunk_ids
