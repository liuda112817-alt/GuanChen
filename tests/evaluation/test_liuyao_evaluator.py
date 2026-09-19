import pytest
from guanchen_v2.evaluation.models import EvaluationCase
from guanchen_v2.evaluation.evaluators.liuyao import LiuyaoEvaluator
from guanchen_v2.liuyao.casting import HexagramCastingService, SystemRandomCoinSource
from guanchen_v2.liuyao.iching_adapter import IChingPyAdapter

@pytest.mark.asyncio
async def test_liuyao_evaluator_invalid_manual():
    service = HexagramCastingService(IChingPyAdapter(), SystemRandomCoinSource())
    evaluator = LiuyaoEvaluator(service)
    
    # Invalid records length (only 2 lines provided)
    case = EvaluationCase(
        id="test_003",
        capability="liuyao.cast_hexagram",
        input={"question": "Test", "method": "manual", "manual_records": [1, 2]},
        expected={"error_expected": True}
    )
    
    result = await evaluator.evaluate_case(case)
    # The evaluation is considered "successful" because the error was expected
    assert result.success is True
    assert result.error is not None
    assert "exactly 6 line values" in result.error
