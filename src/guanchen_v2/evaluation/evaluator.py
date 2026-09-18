from abc import ABC, abstractmethod
from guanchen_v2.evaluation.models import EvaluationCase, EvaluationResult
from guanchen_v2.evaluation.metrics import Metric

class CapabilityEvaluator(ABC):
    def __init__(self, capability: str, metrics: list[Metric] | None = None):
        self.capability = capability
        self.metrics = metrics or []

    @abstractmethod
    async def evaluate_case(self, case: EvaluationCase) -> EvaluationResult:
        pass

    async def evaluate(self, cases: list[EvaluationCase]) -> list[EvaluationResult]:
        results = []
        for case in cases:
            if case.capability == self.capability:
                result = await self.evaluate_case(case)
                results.append(result)
        return results
