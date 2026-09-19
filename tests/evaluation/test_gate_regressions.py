import pytest

from guanchen_v2.evaluation.models import EvaluationCase
from guanchen_v2.evaluation.registry import EvaluationRegistry
from guanchen_v2.evaluation.runner import EvaluationRunner
from guanchen_v2.evaluation.suite import verdict


def test_missing_evidence_cannot_pass():
    assert not all(verdict([], {}, {}, {}, {}).values())


@pytest.mark.asyncio
async def test_unknown_evaluator_cannot_silently_skip_case():
    with pytest.raises(ValueError, match="No evaluator"):
        await EvaluationRunner(EvaluationRegistry()).run([EvaluationCase(id="missing", capability="unknown", input={})])


def test_stale_pass_field_cannot_override_failed_command():
    checks = verdict([{"returncode": 1}], {"passed": True, "mode": "full_chain"}, {}, {}, {})
    assert checks["all_commands_completed"] is False


def test_retrieval_gate_uses_frozen_three_domain_golden_set():
    data = {"query_count": 45, "rrf": {"recall_at_5": 0.9}, "domain_metrics": {d: {"rrf": {"recall_at_5": 0.9}} for d in ("bazi", "dream", "yijing")}}
    assert verdict([], {}, data, {}, {})["retrieval"]
    del data["domain_metrics"]["dream"]
    assert not verdict([], {}, data, {}, {})["retrieval"]
