from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from guanchen_v2.knowledge.embeddings import BgeEmbeddingAdapter
from guanchen_v2.knowledge.errors import KnowledgeTransactionError
from guanchen_v2.knowledge.ingestion.chunker import KnowledgeDocumentChunker
from guanchen_v2.knowledge.ingestion.errors import KnowledgeChunkingError
from guanchen_v2.knowledge.models import KnowledgeDocument
from guanchen_v2.knowledge.persistence.database import async_session
from guanchen_v2.knowledge.persistence.models import KnowledgeChunkRow, KnowledgeDocumentRow


class KnowledgeIngestionService:
    """
    文档级摄取服务，负责统筹切分、向量化并安全持久化至 pgvector 数据库。
    契约与防御：
    1. 坚守 CPU密集与I/O密集解耦：在获取了全部稳定的 Chunk 与 Embedding 之后才开启短命 DB 事务。
    2. 严格的文档级幂等 (Document-Level Idempotency)：
       - Document 表：通过 PostgreSQL UPSERT 进行状态刷新。
       - Chunk 表：采用全量兜底替换 (Delete + Insert)，防范脏数据沉积。
    3. 只抓取底层 DB 问题进行转化，上游项目异常原样抛出。
    """

    def __init__(self, chunker: KnowledgeDocumentChunker, embedding_adapter: BgeEmbeddingAdapter):
        self._chunker = chunker
        self._embedding_adapter = embedding_adapter

    async def ingest_document(self, document: KnowledgeDocument) -> None:
        """
        全量摄取一个 KnowledgeDocument。
        此过程要么全成功得到最终最新版本，要么回滚。绝不会在库中留下孤儿 Chunk 或残片。
        """
        # ====================================================
        # Phase 1：事务外，安全稳定的内存计算与大模型推理
        # ====================================================
        # 本地领域规则如果抛错，会被原样放行上抛
        chunks = self._chunker.chunk_document(document=document)

        if not chunks:
            raise KnowledgeChunkingError(
                f"文档 {document.document_id} 未产生任何 Chunk，拒绝入库。"
            )

        vectors = self._embedding_adapter.embed_documents(chunks=chunks)

        doc_values = {
            "document_id": document.document_id,
            "domain": document.domain.value,
            "source_title": document.source_title,
            "source_type": document.source_type.value,
            "section": document.section,
            "text": document.text,
        }
        update_values = {k: v for k, v in doc_values.items() if k != "document_id"}

        chunk_rows = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk_rows.append(
                KnowledgeChunkRow(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    domain=chunk.domain.value,
                    source_title=chunk.source_title,
                    source_type=chunk.source_type.value,
                    section=chunk.section,
                    text=chunk.text,
                    embedding=vector,
                )
            )

        # ====================================================
        # Phase 2：事务内，持久化重写
        # ====================================================
        try:
            async with async_session() as session:
                async with session.begin():
                    insert_stmt = insert(KnowledgeDocumentRow).values(**doc_values)
                    upsert_stmt = insert_stmt.on_conflict_do_update(
                        index_elements=["document_id"], set_=update_values
                    )
                    await session.execute(upsert_stmt)

                    delete_stmt = delete(KnowledgeChunkRow).where(
                        KnowledgeChunkRow.document_id == document.document_id
                    )
                    await session.execute(delete_stmt)
                    session.add_all(chunk_rows)
        except Exception as exc:
            raise KnowledgeTransactionError("知识文档幂等替换失败。") from exc
