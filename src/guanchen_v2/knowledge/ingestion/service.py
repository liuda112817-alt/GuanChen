from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from guanchen_v2.knowledge.embeddings import (
    BgeEmbeddingAdapter,
)
from guanchen_v2.knowledge.errors import (
    KnowledgeTransactionError,
)
from guanchen_v2.knowledge.ingestion.chunker import (
    KnowledgeDocumentChunker,
)
from guanchen_v2.knowledge.ingestion.errors import (
    KnowledgeChunkingError,
)
from guanchen_v2.knowledge.models import (
    KnowledgeDocument,
)
from guanchen_v2.knowledge.persistence.database import (
    async_session,
)
from guanchen_v2.knowledge.persistence.models import (
    KnowledgeChunkRow,
    KnowledgeDocumentRow,
)


class KnowledgeIngestionService:
    """
    Document-level Knowledge Ingestion Service。

    Pipeline:
        KnowledgeDocument
        -> Chunk
        -> Embedding
        -> document-level transactional replace

    约束：
    1. Chunking / Embedding 在 DB transaction 外完成。
    2. Document 使用 UPSERT。
    3. Chunk 使用 DELETE + INSERT 整体替换。
    4. Vector 与 embedding_model 必须同时持久化。
    5. DB transaction 要么全部成功，要么全部回滚。
    """

    def __init__(
        self,
        chunker: KnowledgeDocumentChunker,
        embedding_adapter: BgeEmbeddingAdapter,
    ) -> None:
        self._chunker = chunker
        self._embedding_adapter = embedding_adapter

    async def ingest_document(
        self,
        document: KnowledgeDocument,
    ) -> None:
        # ---------------------------------------------------------
        # Phase 1
        # Transaction 外完成 Chunking + Embedding
        # ---------------------------------------------------------

        chunks = self._chunker.chunk_document(document=document)

        if not chunks:
            raise KnowledgeChunkingError(f"文档 {document.document_id} 未产生任何 Chunk，拒绝入库。")

        vectors = self._embedding_adapter.embed_documents(chunks=chunks)

        embedding_model = self._embedding_adapter.model_name

        document_values = {
            "document_id": document.document_id,
            "domain": document.domain.value,
            "source_title": document.source_title,
            "source_type": document.source_type.value,
            "section": document.section,
            "text": document.text,
        }

        document_update_values = {key: value for key, value in document_values.items() if key != "document_id"}

        chunk_rows: list[KnowledgeChunkRow] = []

        for chunk, vector in zip(
            chunks,
            vectors,
            strict=True,
        ):
            chunk_rows.append(
                KnowledgeChunkRow(
                    chunk_id=chunk.chunk_id,
                    document_id=(chunk.document_id),
                    domain=chunk.domain.value,
                    source_title=(chunk.source_title),
                    source_type=(chunk.source_type.value),
                    section=chunk.section,
                    text=chunk.text,
                    embedding=vector,
                    embedding_model=(embedding_model),
                )
            )

        # ---------------------------------------------------------
        # Phase 2
        # Document-level atomic replace
        # ---------------------------------------------------------

        try:
            async with async_session() as session:
                async with session.begin():
                    insert_statement = insert(KnowledgeDocumentRow).values(**document_values)

                    upsert_statement = insert_statement.on_conflict_do_update(
                        index_elements=["document_id"],
                        set_=(document_update_values),
                    )

                    await session.execute(upsert_statement)

                    delete_statement = delete(KnowledgeChunkRow).where(KnowledgeChunkRow.document_id == document.document_id)

                    await session.execute(delete_statement)

                    session.add_all(chunk_rows)

        except Exception as exc:
            raise KnowledgeTransactionError("知识文档幂等替换失败。") from exc
