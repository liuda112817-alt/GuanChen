import time
from guanchen_v2.evaluation.evaluator import CapabilityEvaluator
from guanchen_v2.evaluation.models import EvaluationCase, EvaluationResult
from guanchen_v2.liuyao.casting import HexagramCastingService, ManualCastingInput
from guanchen_v2.models.liuyao import LineValue

class LiuyaoEvaluator(CapabilityEvaluator):
    def __init__(self, service: HexagramCastingService, metrics=None):
        super().__init__("liuyao.cast_hexagram", metrics)
        self.service = service

    async def evaluate_case(self, case: EvaluationCase) -> EvaluationResult:
        start_time = time.perf_counter()
        try:
            method = case.input.get("method", "random")
            if method == "manual":
                records = case.input.get("manual_records", [])
                if len(records) != 6:
                    raise ValueError("Manual cast requires exactly 6 line values.")
                lines = tuple(LineValue(v) for v in records)
                result = self.service.cast_manual(ManualCastingInput(lines=lines))
            else:
                result = self.service.cast_random()

            output_dict = {
                "ben_gua": result.primary_hexagram.name,
                "bian_gua": result.changed_hexagram.name if result.changed_hexagram else "",
                "dong_yao": result.moving_line_positions
            }
            
            success = True
            expected_fields = case.expected.get("required_fields", []) if case.expected else []
            for field in expected_fields:
                if field not in output_dict:
                    success = False
                    break
            
            if case.expected and case.expected.get("error_expected"):
                success = False

            latency = (time.perf_counter() - start_time) * 1000
            return EvaluationResult(case.id, self.capability, success, output_dict, None, latency)
            
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            success = False
            # Catch expected errors
            if case.expected and case.expected.get("error_expected"):
                success = True
            return EvaluationResult(case.id, self.capability, success, None, str(e), latency)
