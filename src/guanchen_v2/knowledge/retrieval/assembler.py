from typing import Sequence

from guanchen_v2.knowledge.errors import KnowledgeRetrievalError
from guanchen_v2.knowledge.models import RerankedSearchHit, RetrievalResult, RrfSearchHit


class RetrievalResultAssembler:
    """
    无状态的纯内存组装器。
    职责：
    1. 为 Knowledge Agent 屏蔽 RRF 与 Reranker 的结构差异。
    2. 基于传入序列强行加冕 1-based 最终 Rank。绝不重新做任何数值排序。
    3. 严厉打击重复的 chunk_id，守护物证溯源的唯一性。
    """

    def _ensure_no_duplicates(self, hits: Sequence[RrfSearchHit] | Sequence[RerankedSearchHit], source_name: str) -> None:
        seen = set()
        for hit in hits:
            if hit.chunk_id in seen:
                raise KnowledgeRetrievalError(f"最终检索组装崩溃：在 {source_name} 的结果中发现了重复的 chunk_id [{hit.chunk_id}]。")
            seen.add(hit.chunk_id)

    def from_rrf(self, hits: Sequence[RrfSearchHit]) -> list[RetrievalResult]:
        """将仅经过 RRF 融合 (未开启重排) 的结果转化为最终态。"""
        self._ensure_no_duplicates(hits, "RRF 队列")

        results = []
        for rank, hit in enumerate(hits, start=1):
            res = RetrievalResult(
                rank=rank,
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                domain=hit.domain,
                source_title=hit.source_title,
                source_type=hit.source_type,
                section=hit.section,
                text=hit.text,
                rrf_score=hit.score,  # RRF Hit 的 score 本身就是 rrf_score
                rrf_rank=rank,  # 在未重排时，RRF 名次等同于最终名次
                reranker_score=None,  # 明确留空
                dense_rank=hit.dense_rank,
                sparse_rank=hit.sparse_rank,
            )
            results.append(res)

        return results

    def from_reranked(self, hits: Sequence[RerankedSearchHit]) -> list[RetrievalResult]:
        """将经过交叉编码重排 (Cross-Encoder) 彻底洗牌后的结果转化为最终态。"""
        self._ensure_no_duplicates(hits, "重排 (Reranker) 队列")

        results = []
        for rank, hit in enumerate(hits, start=1):
            res = RetrievalResult(
                rank=rank,
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                domain=hit.domain,
                source_title=hit.source_title,
                source_type=hit.source_type,
                section=hit.section,
                text=hit.text,
                rrf_score=hit.rrf_score,
                rrf_rank=hit.rrf_rank,  # 忠实保留重排前原本的名次探针
                reranker_score=hit.score,  # 真实的大模型 logit
                dense_rank=hit.dense_rank,
                sparse_rank=hit.sparse_rank,
            )
            results.append(res)

        return results
