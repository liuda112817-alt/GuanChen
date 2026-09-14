from collections.abc import Collection, Hashable, Sequence
from typing import TypeVar

T = TypeVar("T", bound=Hashable)


def calculate_recall_at_k(
    relevant_items: Collection[T],
    ranked_items: Sequence[T],
    k: int,
) -> float:
    """
    Recall@K

        | relevant ∩ top_k | / | relevant |

    relevance unit 由调用方决定：
    - 正式 Stage 4 Eval：source_title + section
    - Diagnostic：exact chunk_id
    """
    if k <= 0:
        raise ValueError("k 必须大于 0")

    if not relevant_items:
        raise ValueError("Ground Truth 不能为空")

    top_k = ranked_items[:k]
    hits = set(top_k).intersection(relevant_items)

    return len(hits) / len(relevant_items)


def calculate_mrr_at_k(
    relevant_items: Collection[T],
    ranked_items: Sequence[T],
    k: int,
) -> float:
    """
    单个 query 的 Reciprocal Rank@K。

    整个数据集对结果取平均后得到 MRR@K。
    """
    if k <= 0:
        raise ValueError("k 必须大于 0")

    if not relevant_items:
        raise ValueError("Ground Truth 不能为空")

    for rank, item in enumerate(
        ranked_items[:k],
        start=1,
    ):
        if item in relevant_items:
            return 1.0 / rank

    return 0.0


def calculate_percentile(
    latencies_ms: Sequence[float],
    percentile: float,
) -> float:
    """使用线性插值计算百分位数。"""
    if not latencies_ms:
        raise ValueError("没有 latency observation，无法计算 percentile")

    if not 0.0 <= percentile <= 100.0:
        raise ValueError("percentile 必须位于 [0, 100]")

    sorted_latencies = sorted(latencies_ms)

    position = (len(sorted_latencies) - 1) * (percentile / 100.0)

    lower = int(position)
    upper = lower + 1

    if upper >= len(sorted_latencies):
        return sorted_latencies[lower]

    lower_weight = upper - position
    upper_weight = position - lower

    return sorted_latencies[lower] * lower_weight + sorted_latencies[upper] * upper_weight


def calculate_relative_mrr_gain(
    baseline_mrr: float,
    candidate_mrr: float,
) -> float:
    """
    Reranker 相对于 RRF baseline 的 MRR 相对增益：

        (candidate - baseline) / baseline
    """
    if baseline_mrr <= 0.0:
        raise ValueError("baseline MRR 必须大于 0，才能计算 relative MRR gain")

    return (candidate_mrr - baseline_mrr) / baseline_mrr
