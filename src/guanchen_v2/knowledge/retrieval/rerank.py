from typing import Sequence

from guanchen_v2.knowledge.errors import KnowledgeRetrievalError
from guanchen_v2.knowledge.models import RerankedSearchHit, RrfSearchHit
from guanchen_v2.knowledge.rerank_adapter import BgeRerankerAdapter


class KnowledgeReranker:
    """
    GuanChen 语义重排服务。
    职责：
    1. 不做额外召回。将已通过海选 (RRF) 的序列进行最终把关。
    2. 严格按 source_title + section + text 构建 Passage 以供大模型查阅。
    3. 保留此前 RRF 排名，并在打分平局时用作最高优先级的打破依据 (Prior Evidence)。
    4. 确保 Limit (最终截断) 一定发生在大模型全员审阅并重新洗牌之后。
    """

    def __init__(self, adapter: BgeRerankerAdapter) -> None:
        self._adapter = adapter

    def rerank(
        self, query: str, hits: Sequence[RrfSearchHit], limit: int
    ) -> list[RerankedSearchHit]:
        """
        结合原 Query，对候选名单进行最后的审判与截取。
        """
        if limit <= 0:
            raise KnowledgeRetrievalError("重排后的输出数量 (limit) 必须大于 0。")

        if not query.strip():
            raise KnowledgeRetrievalError("执行重排必须提供合法的自然语言 Query。")

        if not hits:
            return []

        pairs = []
        for hit in hits:
            passage = f"{hit.source_title}\n{hit.section}\n{hit.text}"
            pairs.append((query, passage))

        scores = self._adapter.score_pairs(pairs)

        candidates = []
        for rrf_rank, (hit, score) in enumerate(zip(hits, scores, strict=True), start=1):
            record = {"base_obj": hit, "score": score, "rrf_rank": rrf_rank}
            candidates.append(record)

        candidates.sort(key=lambda x: (-x["score"], x["rrf_rank"], x["base_obj"].chunk_id))

        final_hits = []
        for data in candidates[:limit]:
            obj = data["base_obj"]
            r_hit = RerankedSearchHit(
                chunk_id=obj.chunk_id,
                document_id=obj.document_id,
                domain=obj.domain,
                source_title=obj.source_title,
                source_type=obj.source_type,
                section=obj.section,
                text=obj.text,
                score=data["score"],
                rrf_score=obj.score,
                rrf_rank=data["rrf_rank"],
                dense_rank=obj.dense_rank,
                sparse_rank=obj.sparse_rank,
            )
            final_hits.append(r_hit)
        return final_hits
