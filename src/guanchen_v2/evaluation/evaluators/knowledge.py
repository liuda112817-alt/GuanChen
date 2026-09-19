import time
from guanchen_v2.evaluation.evaluator import CapabilityEvaluator
from guanchen_v2.evaluation.models import EvaluationCase, EvaluationResult
from guanchen_v2.knowledge.retrieval.service import RetrievalService

class KnowledgeEvaluator(CapabilityEvaluator):
    def __init__(self, service: RetrievalService, metrics=None):
        super().__init__("knowledge.search", metrics)
        self.service = service

    async def evaluate_case(self, case: EvaluationCase) -> EvaluationResult:
        start_time = time.perf_counter()
        try:
            query = case.input["query"]
            limit = case.input.get("top_k", 5)
            
            # Ensure it awaits properly
            results = await self.service.search(query=query, limit=limit)
            output_dict = {"results": [getattr(r, "model_dump", lambda mode: r.__dict__)() for r in results]}
            
            success = True
            if case.expected and case.expected.get("required_citation"):
                if not results:
                    success = False
                else:
                    for r in results:
                        if not hasattr(r, "source_title") or not hasattr(r, "chunk_id"):
                            success = False
                            break

            latency = (time.perf_counter() - start_time) * 1000
            return EvaluationResult(case.id, self.capability, success, output_dict, None, latency)
            
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            return EvaluationResult(case.id, self.capability, False, None, str(e), latency)
