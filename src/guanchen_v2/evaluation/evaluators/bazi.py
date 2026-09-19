import time

from guanchen_v2.bazi.service import BaziService
from guanchen_v2.evaluation.evaluator import CapabilityEvaluator
from guanchen_v2.evaluation.models import EvaluationCase, EvaluationResult
from guanchen_v2.models.bazi import BirthProfile, Gender


class BaziEvaluator(CapabilityEvaluator):
    def __init__(self, service: BaziService, metrics=None):
        super().__init__("bazi.calculate", metrics)
        self.service = service

    async def evaluate_case(self, case: EvaluationCase) -> EvaluationResult:
        start_time = time.perf_counter()
        try:
            profile = BirthProfile(
                year=case.input["year"],
                month=case.input["month"],
                day=case.input["day"],
                hour=case.input["hour"],
                minute=case.input["minute"],
                gender=Gender(case.input["gender"]),
            )
            chart = self.service.calculate(profile)
            output_dict = chart.model_dump(mode="json")

            # Validation
            success = True
            expected_fields = case.expected.get("required_fields", []) if case.expected else []
            for field in expected_fields:
                if field not in output_dict:
                    success = False
                    break

            latency = (time.perf_counter() - start_time) * 1000
            return EvaluationResult(case.id, self.capability, success, output_dict, None, latency)

        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return EvaluationResult(case.id, self.capability, False, None, str(e), latency)
