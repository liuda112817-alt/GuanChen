from typing import Optional

from sqlalchemy import select

from guanchen_v2.knowledge.embeddings import (
    BgeEmbeddingAdapter,
)
from guanchen_v2.knowledge.errors import (
    KnowledgeRetrievalError,
)
from guanchen_v2.knowledge.models import (
    DenseSearchHit,
    KnowledgeDomain,
    RetrievalFilter,
    SourceType,
)
from guanchen_v2.knowledge.persistence.database import (
    async_session,
)
from guanchen_v2.knowledge.persistence.models import (
    KnowledgeChunkRow,
)


class DenseRetriever:
    """
    GuanChen Dense Retriever。

    契约：
    1. Query Embedding 由统一 EmbeddingAdapter 生成。
    2. 只允许检索与当前 Adapter 相同 embedding_model 的向量。
    3. metadata filter 必须在 LIMIT 前执行。
    4. 使用 pgvector cosine distance。
    5. score 越大表示越相关。
    6. 相同距离通过 chunk_id 保证 deterministic ordering。
    """

    def __init__(
        self,
        embedding_adapter: BgeEmbeddingAdapter,
    ) -> None:
        self._embedding_adapter = embedding_adapter

    async def search(
        self,
        query: str,
        limit: int,
        filters: Optional[RetrievalFilter] = None,
    ) -> list[DenseSearchHit]:
        if limit <= 0:
            raise KnowledgeRetrievalError("检索数量必须大于 0。")

        query_vector = self._embedding_adapter.embed_query(query=query)

        try:
            async with async_session() as session:
                distance = KnowledgeChunkRow.embedding.cosine_distance(query_vector)

                stmt = select(
                    KnowledgeChunkRow,
                    distance.label("distance"),
                )

                # -------------------------------------------------
                # Embedding compatibility boundary
                # -------------------------------------------------
                #
                # 即使两个模型都输出 512 维向量，
                # 不同 Embedding space 也不能直接比较。
                #
                # 必须在 LIMIT 前过滤。
                stmt = stmt.where(KnowledgeChunkRow.embedding_model == self._embedding_adapter.model_name)

                # -------------------------------------------------
                # Domain / source metadata filters
                # -------------------------------------------------

                if filters:
                    if filters.domains:
                        stmt = stmt.where(
                            KnowledgeChunkRow.domain.in_(sorted(domain.value for domain in filters.domains))
                        )

                    if filters.source_types:
                        stmt = stmt.where(
                            KnowledgeChunkRow.source_type.in_(
                                sorted(source_type.value for source_type in filters.source_types)
                            )
                        )

                    if filters.source_titles:
                        stmt = stmt.where(KnowledgeChunkRow.source_title.in_(sorted(filters.source_titles)))

                    if filters.sections:
                        stmt = stmt.where(KnowledgeChunkRow.section.in_(sorted(filters.sections)))

                stmt = stmt.order_by(
                    distance.asc(),
                    KnowledgeChunkRow.chunk_id.asc(),
                ).limit(limit)

                result = await session.execute(stmt)

                hits: list[DenseSearchHit] = []

                for row, dist in result:
                    score = 1.0 - float(dist)

                    hits.append(
                        DenseSearchHit(
                            chunk_id=(row.chunk_id),
                            document_id=(row.document_id),
                            domain=(KnowledgeDomain(row.domain)),
                            source_title=(row.source_title),
                            source_type=(SourceType(row.source_type)),
                            section=row.section,
                            text=row.text,
                            score=score,
                        )
                    )

                return hits

        except Exception as exc:
            raise KnowledgeRetrievalError("知识向量检索失败。") from exc
