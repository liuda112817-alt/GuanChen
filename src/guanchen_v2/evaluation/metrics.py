from abc import ABC, abstractmethod
from typing import Any
from guanchen_v2.evaluation.models import EvaluationResult

class Metric(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def calculate(self, results: list[EvaluationResult]) -> Any:
        pass

class SuccessRateMetric(Metric):
    @property
    def name(self) -> str:
        return "success_rate"

    def calculate(self, results: list[EvaluationResult]) -> float:
        if not results: return 0.0
        return sum(1 for r in results if r.success) / len(results)

class AverageLatencyMetric(Metric):
    @property
    def name(self) -> str:
        return "average_latency_ms"

    def calculate(self, results: list[EvaluationResult]) -> float:
        if not results: return 0.0
        return sum(r.latency_ms for r in results) / len(results)
