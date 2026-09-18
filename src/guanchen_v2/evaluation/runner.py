import logging
from guanchen_v2.evaluation.models import EvaluationCase, EvaluationResult
from guanchen_v2.evaluation.registry import EvaluationRegistry

logger = logging.getLogger(__name__)

class EvaluationRunner:
    def __init__(self, registry: EvaluationRegistry):
        self.registry = registry

    async def run(self, cases: list[EvaluationCase]) -> list[EvaluationResult]:
        cases_by_cap: dict[str, list[EvaluationCase]] = {}
        for case in cases:
            cases_by_cap.setdefault(case.capability, []).append(case)
        
        all_results = []
        
        for capability, cap_cases in cases_by_cap.items():
            evaluator = self.registry.get(capability)
            if not evaluator:
                logger.warning(f"No evaluator registered for {capability}. Skipping.")
                continue
            
            results = await evaluator.evaluate(cap_cases)
            all_results.extend(results)
            
        return all_results
