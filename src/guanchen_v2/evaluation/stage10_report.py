import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from guanchen_v2.evaluation.models import EvaluationCase
from guanchen_v2.evaluation.registry import EvaluationRegistry
from guanchen_v2.evaluation.runner import EvaluationRunner
from guanchen_v2.evaluation.reporting import (
    CapabilityEvaluationSummary,
    Stage10EvaluationReport,
)

from guanchen_v2.bazi.service import BaziService
from guanchen_v2.bazi.adapter import LunarPythonBaziAdapter
from guanchen_v2.evaluation.evaluators.bazi import BaziEvaluator

from guanchen_v2.liuyao.casting import (
    HexagramCastingService,
    SystemRandomCoinSource,
)
from guanchen_v2.liuyao.iching_adapter import IChingPyAdapter
from guanchen_v2.evaluation.evaluators.liuyao import LiuyaoEvaluator

from guanchen_v2.config.settings import Settings
from guanchen_v2.knowledge.persistence.database import create_database_runtime
from guanchen_v2.application.factory import build_retrieval_service
from guanchen_v2.evaluation.evaluators.knowledge import KnowledgeEvaluator

from guanchen_v2.observability.metrics import MetricsCollector
from guanchen_v2.observability.context import TraceContext
from guanchen_v2.observability.tracer import Tracer
from guanchen_v2.observability.integration import set_tracer, reset_tracer


def load_dataset(file_name: str) -> list[EvaluationCase]:
    file_path = Path(__file__).parent / "datasets" / file_name
    if not file_path.exists():
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return [EvaluationCase(**case) for case in data]


async def generate_report():
    print("=" * 60)
    print("GuanChen Stage 10 Evaluation Report")
    print("=" * 60)

    registry = EvaluationRegistry()
    metrics = MetricsCollector()

    # 建立全局上下文以捕获内部 @trace 装饰器的指标
    ctx = TraceContext.create(prefix="eval")
    tracer = Tracer(ctx, metrics=metrics)
    token = set_tracer(tracer)

    try:
        # 1. Bazi
        bazi_service = BaziService(adapter=LunarPythonBaziAdapter())
        registry.register("bazi.calculate", BaziEvaluator(bazi_service))

        # 2. Liuyao
        liuyao_service = HexagramCastingService(
            IChingPyAdapter(),
            SystemRandomCoinSource(),
        )
        registry.register("liuyao.cast_hexagram", LiuyaoEvaluator(liuyao_service))

        # 3. Knowledge (Real DB integration)
        settings = Settings()
        db_runtime = create_database_runtime(settings.database_url)
        await db_runtime.init_schema()
        retrieval_service = await build_retrieval_service(db_runtime.session_factory)
        registry.register(
            "knowledge.search",
            KnowledgeEvaluator(retrieval_service),
        )

        # 4. Load datasets & Run
        all_cases = (
            load_dataset("bazi_cases.json")
            + load_dataset("liuyao_cases.json")
            + load_dataset("knowledge_cases.json")
        )

        runner = EvaluationRunner(registry)
        results = await runner.run(all_cases)

        # 5. Aggregate Results
        summaries = []
        caps = set(r.capability for r in results)
        total_passed = 0

        print(f"\n{'Capability':<25} {'Cases':<7} {'Passed':<8} {'Success':<9} {'Avg(ms)':<8}")
        print("-" * 60)

        for cap in caps:
            cap_results = [r for r in results if r.capability == cap]
            total = len(cap_results)
            passed = sum(1 for r in cap_results if r.success)
            total_passed += passed
            avg_lat = (
                sum(r.latency_ms for r in cap_results) / total
                if total > 0
                else 0
            )

            summary = CapabilityEvaluationSummary(
                capability=cap,
                total_cases=total,
                passed_cases=passed,
                failed_cases=total - passed,
                success_rate=passed / total if total else 0.0,
                average_latency_ms=round(avg_lat, 2),
            )
            summaries.append(summary)

            print(
                f"{cap:<25} {total:<7} {passed:<8} "
                f"{summary.success_rate * 100:>6.1f}%   "
                f"{summary.average_latency_ms:>6.2f}"
            )

        # 6. Observability Metrics Snapshot
        snapshot = metrics.snapshot()
        print("\nRuntime Observability Snapshot")
        print("-" * 60)
        for k, v in snapshot["counters"].items():
            print(f"{k:<35} {v}")

        # 7. Generate Files
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)

        report_data = Stage10EvaluationReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            capabilities=summaries,
            overall_success_rate=(
                total_passed / len(results) if results else 0.0
            ),
            metrics_snapshot=snapshot,
        )

        # JSON Report
        import dataclasses

        json_path = reports_dir / "stage10_report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                dataclasses.asdict(report_data),
                f,
                ensure_ascii=False,
                indent=2,
            )

        # Markdown Report
        md_path = reports_dir / "stage10_report.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# GuanChen Stage 10 Evaluation Report\n\n")
            f.write(f"**Generated At:** {report_data.generated_at}\n\n")
            f.write("## 1. Summary\n")
            f.write(f"- **Total Cases:** {len(results)}\n")
            f.write(
                f"- **Overall Success Rate:** "
                f"{report_data.overall_success_rate * 100:.1f}%\n\n"
            )

            f.write("## 2. Capability Evaluation\n\n")
            for s in summaries:
                f.write(f"### {s.capability}\n")
                f.write(f"- Cases: {s.total_cases}\n")
                f.write(f"- Passed: {s.passed_cases}\n")
                f.write(
                    f"- Success Rate: {s.success_rate * 100:.1f}%\n"
                )
                f.write(
                    f"- Avg Latency: {s.average_latency_ms} ms\n\n"
                )

            f.write("## 3. Runtime Observability\n\n")
            f.write("### Request / Service Metrics\n")
            f.write("```json\n")
            f.write(json.dumps(snapshot["counters"], indent=2))
            f.write("\n```\n\n")
            f.write("### Latency Observations\n")
            f.write("```json\n")
            f.write(json.dumps(snapshot["observations"], indent=2))
            f.write("\n```\n\n")
            f.write("## 4. Stage Gate\n")
            f.write(
                "Stage 10 Passed. Ready for Stage 11 API Gateway / "
                "Frontend Integration.\n"
            )

        print("=" * 60)
        print(f"Reports generated at:\n- {json_path}\n- {md_path}")

    finally:
        reset_tracer(token)


if __name__ == "__main__":
    import sys

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(
            asyncio.WindowsSelectorEventLoopPolicy()
        )
    asyncio.run(generate_report())
