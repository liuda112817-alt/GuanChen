from typing import Sequence

from guanchen_v2.knowledge.errors import KnowledgeRetrievalError
from guanchen_v2.knowledge.models import DenseSearchHit, RrfSearchHit, SparseSearchHit

# RRF 平滑常数
RRF_K = 60


class ReciprocalRankFusion:
    """
    倒数秩融合器。
    职责：
    1. 不碰数据库，不读 Query，完全隔离 I/O。
    2. 基于 1-based 排名计算 RRF，彻底摒弃原生底层的 Score (0 分或无限大皆不受影响)。
    3. - 单一阵营内绝对不允许重复 chunk_id。
       - 跨阵营对齐：同一 chunk_id 必须拥有绝对一致的 Metadata，否则立即触发崩溃以暴露快照脏数据。
    4. 执行 Deterministic 的 Tie-break (score DESC, chunk_id ASC)。
    """

    def _verify_metadata_consistency(self, hit_a: DenseSearchHit, hit_b: SparseSearchHit) -> None:
        """断言同一个 Chunk_ID 在不同阵营提交上来的数据必须如出一辙。"""
        if (
            hit_a.document_id != hit_b.document_id
            or hit_a.domain != hit_b.domain
            or hit_a.source_title != hit_b.source_title
            or hit_a.source_type != hit_b.source_type
            or hit_a.section != hit_b.section
            or hit_a.text != hit_b.text
        ):
            raise KnowledgeRetrievalError(f"RRF 数据校验崩溃：来自两路的 chunk_id [{hit_a.chunk_id}] 元数据出现脏乱分歧！")

    def fuse(
        self,
        dense_hits: Sequence[DenseSearchHit],
        sparse_hits: Sequence[SparseSearchHit],
        limit: int,
    ) -> list[RrfSearchHit]:
        """执行名次聚合、校验与截断。"""
        if limit <= 0:
            raise KnowledgeRetrievalError("RRF 融合后的检索数量必须大于 0。")

        # 以 chunk_id 为唯一识别枢纽构建聚合站
        # 结构: chunk_id -> dict(hit_obj, dense_rank, sparse_rank, score)
        fusion_map: dict[str, dict] = {}

        # -----------------------------------------------
        # 处理 Dense  (强转为 1-based rank)
        # -----------------------------------------------
        for rank, hit in enumerate(dense_hits, start=1):
            if hit.chunk_id in fusion_map:
                raise KnowledgeRetrievalError(f"RRF 数据校验崩溃：Dense 内出现了重复提交的 chunk_id [{hit.chunk_id}]。")

            fusion_map[hit.chunk_id] = {
                "base_obj": hit,
                "dense_rank": rank,
                "sparse_rank": None,
                "rrf_score": 1.0 / (RRF_K + rank),
            }

        # -----------------------------------------------
        # 处理 Sparse  (并接管与 Dense 的跨阵营核对)
        # -----------------------------------------------
        for rank, hit in enumerate(sparse_hits, start=1):
            record = fusion_map.get(hit.chunk_id)

            if record:
                if record["sparse_rank"] is not None:
                    raise KnowledgeRetrievalError(f"RRF 数据校验崩溃：Sparse 内出现了重复交卷的 chunk_id [{hit.chunk_id}]。")

                self._verify_metadata_consistency(record["base_obj"], hit)
                record["sparse_rank"] = rank
                record["rrf_score"] += 1.0 / (RRF_K + rank)
            else:
                fusion_map[hit.chunk_id] = {
                    "base_obj": hit,
                    "dense_rank": None,
                    "sparse_rank": rank,
                    "rrf_score": 1.0 / (RRF_K + rank),
                }

        # 根据 RRF_score 降序，发生平局则按 chunk_id 升序进行强制打断
        fused_records = sorted(fusion_map.items(), key=lambda x: (-x[1]["rrf_score"], x[0]))

        final_hits = []
        for chunk_id, data in fused_records[:limit]:
            obj = data["base_obj"]
            hit = RrfSearchHit(
                chunk_id=chunk_id,
                document_id=obj.document_id,
                domain=obj.domain,
                source_title=obj.source_title,
                source_type=obj.source_type,
                section=obj.section,
                text=obj.text,
                score=data["rrf_score"],
                dense_rank=data["dense_rank"],
                sparse_rank=data["sparse_rank"],
            )
            final_hits.append(hit)

        return final_hits
