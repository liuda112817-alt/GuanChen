from guanchen_v2.evaluation.evaluator import CapabilityEvaluator

class EvaluationRegistry:
    def __init__(self) -> None:
        self._evaluators: dict[str, CapabilityEvaluator] = {}

    def register(self, capability: str, evaluator: CapabilityEvaluator) -> None:
        self._evaluators[capability] = evaluator

    def get(self, capability: str) -> CapabilityEvaluator | None:
        return self._evaluators.get(capability)
