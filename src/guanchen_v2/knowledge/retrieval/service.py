from typing import Optional

from guanchen_v2.knowledge.errors import KnowledgeRetrievalError
from guanchen_v2.knowledge.models import RetrievalFilter, RetrievalResult
from guanchen_v2.knowledge.retrieval.assembler import RetrievalResultAssembler
from guanchen_v2.knowledge.retrieval.dense import DenseRetriever
from guanchen_v2.knowledge.retrieval.rerank import KnowledgeReranker
from guanchen_v2.knowledge.retrieval.rrf import ReciprocalRankFusion
from guanchen_v2.knowledge.retrieval.sparse import SparseRetriever


class RetrievalService:
    """
    GuanChen 统一知识检索底座。
    职责：
    1. 固化检索流水线：Dense + Sparse -> RRF -> (Optional) Reranker -> Assembler。
    2. 对外隐藏一切内部策略参数（海选池大小、是否开启重排等）。
    3. 绝不做智能化包装（如改写 Query、揣测 Filter、二次检索）。
    """

    def __init__(
        self,
        dense_retriever: DenseRetriever,
        sparse_retriever: SparseRetriever,
        rrf: ReciprocalRankFusion,
        reranker: KnowledgeReranker,
        assembler: RetrievalResultAssembler,
        candidate_limit: int = 20,
        result_limit: int = 5,
        reranker_enabled: bool = False,
    ):
        self._dense = dense_retriever
        self._sparse = sparse_retriever
        self._rrf = rrf
        self._reranker = reranker
        self._assembler = assembler

        if candidate_limit <= 0 or result_limit <= 0:
            raise KnowledgeRetrievalError("候选项数量与结果数量必须大于 0。")
        if candidate_limit < result_limit:
            raise KnowledgeRetrievalError(
                "海选数量 (candidate_limit) 必须大于等于最终结果数量 (result_limit)。"
            )

        self._candidate_limit = candidate_limit
        self._result_limit = result_limit
        self._reranker_enabled = reranker_enabled

    async def retrieve(
        self,
        query: str,
        filters: Optional[RetrievalFilter] = None,
    ) -> list[RetrievalResult]:
        if not query.strip():
            raise KnowledgeRetrievalError("检索查询 (Query) 不能为空。")

        # Sparse 为同步内存操作，Dense 为异步 DB 操作
        dense_hits = await self._dense.search(query, limit=self._candidate_limit, filters=filters)
        sparse_hits = self._sparse.search(query, limit=self._candidate_limit, filters=filters)

        rrf_hits = self._rrf.fuse(dense_hits, sparse_hits, limit=self._candidate_limit)
        if not rrf_hits:
            return []

        if self._reranker_enabled:
            reranked_hits = self._reranker.rerank(query, rrf_hits, limit=self._result_limit)
            return self._assembler.from_reranked(reranked_hits)
        else:
            final_rrf_hits = rrf_hits[: self._result_limit]
            return self._assembler.from_rrf(final_rrf_hits)
