from guanchen_v2.evaluation.reporting import (
    CapabilityEvaluationSummary,
    Stage10EvaluationReport,
)


def test_report_models():
    summary = CapabilityEvaluationSummary("test.cap", 10, 9, 1, 0.9, 15.5)
    report = Stage10EvaluationReport(
        generated_at="2026-09-18T10:00:00Z",
        capabilities=[summary],
        overall_success_rate=0.9,
        metrics_snapshot={"counters": {}, "observations": {}},
    )
    assert report.capabilities[0].capability == "test.cap"
    assert report.overall_success_rate == 0.9
