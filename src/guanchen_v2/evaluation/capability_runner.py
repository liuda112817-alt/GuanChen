import asyncio
import json
from pathlib import Path
import logging

from guanchen_v2.evaluation.models import EvaluationCase
from guanchen_v2.evaluation.registry import EvaluationRegistry
from guanchen_v2.evaluation.runner import EvaluationRunner
from guanchen_v2.evaluation.metrics import SuccessRateMetric, AverageLatencyMetric

from guanchen_v2.bazi.service import BaziService
from guanchen_v2.bazi.adapter import LunarPythonBaziAdapter
from guanchen_v2.evaluation.evaluators.bazi import BaziEvaluator

from guanchen_v2.liuyao.casting import HexagramCastingService, SystemRandomCoinSource
from guanchen_v2.liuyao.iching_adapter import IChingPyAdapter
from guanchen_v2.evaluation.evaluators.liuyao import LiuyaoEvaluator

# Mock or real retrieval for knowledge can be loaded similarly, omitted DB init here for safety
# In real runner, build_retrieval_service should be used
from guanchen_v2.evaluation.evaluators.knowledge import KnowledgeEvaluator

logger = logging.getLogger(__name__)

def load_dataset(file_name: str) -> list[EvaluationCase]:
    file_path = Path(__file__).parent / "datasets" / file_name
    if not file_path.exists():
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return [EvaluationCase(**case) for case in data]

async def main():
    print("=" * 60)
    print("GuanChen Capability Evaluation Runner")
    print("=" * 60)
    
    registry = EvaluationRegistry()
    metrics = [SuccessRateMetric(), AverageLatencyMetric()]
    
    # 1. Bazi Evaluator
    bazi_service = BaziService(adapter=LunarPythonBaziAdapter())
    registry.register("bazi.calculate", BaziEvaluator(bazi_service, metrics))
    
    # 2. Liuyao Evaluator
    liuyao_service = HexagramCastingService(IChingPyAdapter(), SystemRandomCoinSource())
    registry.register("liuyao.cast_hexagram", LiuyaoEvaluator(liuyao_service, metrics))
    
    # Run
    runner = EvaluationRunner(registry)
    all_cases = load_dataset("bazi_cases.json") + load_dataset("liuyao_cases.json")
    results = await runner.run(all_cases)
    
    # Report
    caps = set(r.capability for r in results)
    for cap in caps:
        cap_results = [r for r in results if r.capability == cap]
        report = {
            "capability": cap,
            "success_rate": metrics[0].calculate(cap_results),
            "average_latency_ms": round(metrics[1].calculate(cap_results), 2)
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
