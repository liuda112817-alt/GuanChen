from abc import ABC, abstractmethod
from typing import Any
from guanchen_v2.evaluation.models import EvaluationResult

class Metric(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def calculate(self, result: EvaluationResult) -> Any:
        pass
