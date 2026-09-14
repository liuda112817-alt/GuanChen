import math

import pytest

from guanchen_v2.knowledge.eval_metrics import (
    calculate_mrr_at_k,
    calculate_percentile,
    calculate_recall_at_k,
    calculate_relative_mrr_gain,
)


def test_recall_at_k_logic():
    gt = {"A", "B", "C"}
    assert calculate_recall_at_k(gt, ["X", "A", "Y", "C", "Z"], k=5) == 2 / 3
    assert calculate_recall_at_k(gt, ["X", "A", "Y", "C", "Z"], k=2) == 1 / 3
    assert calculate_recall_at_k(gt, ["X", "Y", "Z"], k=5) == 0.0

    with pytest.raises(ValueError, match="K 必须大于 0"):
        calculate_recall_at_k(gt, ["A"], k=0)
    with pytest.raises(ValueError, match="不能为空集"):
        calculate_recall_at_k(set(), ["A"], k=5)


def test_mrr_at_k_logic():
    gt = {"A", "B"}
    assert calculate_mrr_at_k(gt, ["X", "Y", "A", "B"], k=5) == 1 / 3
    assert calculate_mrr_at_k(gt, ["B", "Y", "X", "A"], k=5) == 1.0
    assert calculate_mrr_at_k(gt, ["X", "Y", "A", "B"], k=2) == 0.0

    with pytest.raises(ValueError, match="K 必须大于 0"):
        calculate_mrr_at_k(gt, ["A"], k=-1)


def test_relative_mrr_gain():
    assert math.isclose(calculate_relative_mrr_gain(0.70, 0.735), 0.05, rel_tol=1e-5)
    with pytest.raises(ValueError, match="不可判定"):
        calculate_relative_mrr_gain(0.0, 0.5)


def test_percentile_logic():
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert calculate_percentile(latencies, 50) == 30.0
    assert calculate_percentile(latencies, 95) > 45.0

    with pytest.raises(ValueError, match="不可判定"):
        calculate_percentile([], 95)
    with pytest.raises(ValueError, match="0 到 100"):
        calculate_percentile([10.0], 105)
