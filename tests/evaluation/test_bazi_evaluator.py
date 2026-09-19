import pytest

from guanchen_v2.bazi.adapter import LunarPythonBaziAdapter
from guanchen_v2.bazi.service import BaziService
from guanchen_v2.evaluation.evaluators.bazi import BaziEvaluator
from guanchen_v2.evaluation.models import EvaluationCase


@pytest.mark.asyncio
async def test_bazi_evaluator_valid_case():
    service = BaziService(LunarPythonBaziAdapter())
    evaluator = BaziEvaluator(service)

    case = EvaluationCase(
        id="test_001",
        capability="bazi.calculate",
        input={"year": 1990, "month": 1, "day": 1, "hour": 12, "minute": 30, "gender": "male"},
        expected={"required_fields": ["year_pillar", "day_master"]},
    )

    result = await evaluator.evaluate_case(case)
    assert result.success is True
    assert result.error is None
    assert result.latency_ms > 0
