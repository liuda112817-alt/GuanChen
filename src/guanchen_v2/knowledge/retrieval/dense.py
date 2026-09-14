from typing import Optional

from sqlalchemy import select

from guanchen_v2.knowledge.embeddings import BgeEmbeddingAdapter
from guanchen_v2.knowledge.errors import KnowledgeRetrievalError
from guanchen_v2.knowledge.models import (
    DenseSearchHit,
    KnowledgeDomain,
    RetrievalFilter,
    SourceType,
)
from guanchen_v2.knowledge.persistence.database import async_session
from guanchen_v2.knowledge.persistence.models import KnowledgeChunkRow


class DenseRetriever:
    """
    GuanChen Dense 检索器 (Exact Search)。
    职责：
    1. 负责查询的向量化 (通过 BgeEmbeddingAdapter)。
    2. 基于 PostgreSQL pgvector 的余弦距离进行 K 近邻搜索。
    3. 保证确定性的平局打破规则 (Tie-Breaking)。
    4. 统一分数契约：Score 越大越相关。
    """

    def __init__(self, embedding_adapter: BgeEmbeddingAdapter):
        self._embedding_adapter = embedding_adapter

    async def search(
        self, query: str, limit: int, filters: Optional[RetrievalFilter] = None
    ) -> list[DenseSearchHit]:
        if limit <= 0:
            raise KnowledgeRetrievalError("检索数量必须大于 0。")

        query_vector = self._embedding_adapter.embed_query(query=query)
        try:
            async with async_session() as session:
                # 使用 pgvector 原生的余弦距离算子: <=>
                distance = KnowledgeChunkRow.embedding.cosine_distance(query_vector)
                stmt = select(
                    KnowledgeChunkRow,
                    distance.label("distance"),
                )

                if filters:
                    if filters.domains:
                        stmt = stmt.where(
                            KnowledgeChunkRow.domain.in_(sorted(d.value for d in filters.domains))
                        )
                    if filters.source_types:
                        stmt = stmt.where(
                            KnowledgeChunkRow.source_type.in_(
                                sorted(st.value for st in filters.source_types)
                            )
                        )
                    if filters.source_titles:
                        stmt = stmt.where(
                            KnowledgeChunkRow.source_title.in_(sorted(filters.source_titles))
                        )
                    if filters.sections:
                        stmt = stmt.where(KnowledgeChunkRow.section.in_(sorted(filters.sections)))

                stmt = stmt.order_by(distance.asc(), KnowledgeChunkRow.chunk_id.asc()).limit(limit)

                result = await session.execute(stmt)

                hits = []
                for row, dist in result:
                    # 分数倒置：让后续的 BM25 / Reranker 享有统一心智，越大越好
                    score = 1.0 - float(dist)

                    hit = DenseSearchHit(
                        chunk_id=row.chunk_id,
                        document_id=row.document_id,
                        domain=KnowledgeDomain(row.domain),
                        source_title=row.source_title,
                        source_type=SourceType(row.source_type),
                        section=row.section,
                        text=row.text,
                        score=score,
                    )
                    hits.append(hit)
                return hits
        except Exception as exc:
            raise KnowledgeRetrievalError("知识向量检索失败。") from exc
