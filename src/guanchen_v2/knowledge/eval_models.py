from dataclasses import dataclass
from typing import FrozenSet, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from guanchen_v2.knowledge.models import RetrievalFilter


class RetrievalEvalCase(BaseModel):
    """
    单条 Retrieval Ground Truth。

    relevant_chunk_ids 的职责：
    1. 作为人工标注 anchor，保证标注能追溯到真实 corpus chunk；
    2. Preflight 时从数据库反查 source_title + section；
    3. source_title + section 才是 Stage 4 正式 Retrieval Gate 的 relevance unit；
    4. exact chunk_id 仅保留为诊断指标。
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    relevant_chunk_ids: FrozenSet[str] = Field(min_length=1)
    filters: Optional[RetrievalFilter] = None
    note: Optional[str] = None

    @field_validator("case_id", "query")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("字段不能为空或纯空格")
        return normalized

    @field_validator("relevant_chunk_ids")
    @classmethod
    def validate_chunk_ids(
        cls,
        value: FrozenSet[str],
    ) -> FrozenSet[str]:
        normalized = frozenset(chunk_id.strip() for chunk_id in value)

        if not normalized:
            raise ValueError("relevant_chunk_ids 不能为空")

        if any(not chunk_id for chunk_id in normalized):
            raise ValueError("relevant_chunk_ids 不能包含纯空格 ID")

        return normalized


@dataclass(frozen=True)
class RetrievalEvalMetrics:
    """单条 Retrieval Pipeline 的汇总指标。"""

    recall_at_5: float
    mrr_at_10: float
    query_count: int


@dataclass(frozen=True)
class RetrievalEvalReport:
    """
    Stage 4 Retrieval Eval 总报告。

    dense / sparse / rrf / reranked：
        正式 Stage 4 指标，relevance unit 为 source_title + section。

    *_exact_chunk_diagnostic：
        精确 chunk_id 诊断指标，不参与 Stage 4 Core Retrieval Gate。

    reranker 字段允许为 None：
        None 表示该 benchmark 没有执行 reranker，
        不能与实际测得的 0.0 混淆。
    """

    query_count: int

    dense: RetrievalEvalMetrics
    sparse: RetrievalEvalMetrics
    rrf: RetrievalEvalMetrics

    dense_exact_chunk_diagnostic: RetrievalEvalMetrics
    sparse_exact_chunk_diagnostic: RetrievalEvalMetrics
    rrf_exact_chunk_diagnostic: RetrievalEvalMetrics

    reranked: RetrievalEvalMetrics | None = None
    reranked_exact_chunk_diagnostic: RetrievalEvalMetrics | None = None

    reranker_relative_mrr_gain: float | None = None
    reranker_added_p50_ms: float | None = None
    reranker_added_p95_ms: float | None = None
