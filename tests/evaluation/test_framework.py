import pytest
from guanchen_v2.evaluation.models import EvaluationCase, EvaluationResult
from guanchen_v2.evaluation.metrics import Metric
from guanchen_v2.evaluation.evaluator import CapabilityEvaluator
from guanchen_v2.evaluation.registry import EvaluationRegistry
from guanchen_v2.evaluation.runner import EvaluationRunner


class DummyMetric(Metric):
    @property
    def name(self) -> str:
        return "dummy_metric"
    
    def calculate(self, result: EvaluationResult) -> int:
        return 1 if result.success else 0


class DummyEvaluator(CapabilityEvaluator):
    async def evaluate_case(self, case: EvaluationCase) -> EvaluationResult:
        return EvaluationResult(
            case_id=case.id,
            capability=case.capability,
            success=True,
            output={"tested": True},
            error=None,
            latency_ms=15.0
        )


@pytest.mark.asyncio
async def test_evaluation_framework_core():
    # 1. 验证 Data Model
    case = EvaluationCase(id="case_001", capability="dummy.cap", input={"query": "test"})
    assert case.id == "case_001"
    
    # 2. 验证 Registry 与 Evaluator
    registry = EvaluationRegistry()
    evaluator = DummyEvaluator(capability="dummy.cap", metrics=[DummyMetric()])
    registry.register("dummy.cap", evaluator)
    assert registry.get("dummy.cap") is not None
    
    # 3. 验证 Runner 执行链路
    runner = EvaluationRunner(registry)
    results = await runner.run([case])
    
    assert len(results) == 1
    res = results[0]
    assert res.case_id == "case_001"
    assert res.success is True
    assert res.latency_ms == 15.0
    
    # 4. 验证 Metric 调用
    metric = evaluator.metrics[0]
    assert metric.calculate(res) == 1