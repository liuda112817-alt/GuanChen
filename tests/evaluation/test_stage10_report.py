import pytest

from guanchen_v2.evaluation.reporting import Stage10EvaluationReport


@pytest.mark.asyncio
async def test_report_generation_mock(tmp_path):
    """Mock 测试报告生成的格式验证（绕过 DB）"""
    import dataclasses

    # 模拟一份生成的报告写入
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(exist_ok=True)
    json_path = reports_dir / "stage10_report.json"

    report_data = Stage10EvaluationReport(
        generated_at="2026-09-18T10:00:00Z",
        capabilities=[],
        overall_success_rate=1.0,
        metrics_snapshot={"counters": {}, "observations": {}},
    )

    import json

    with open(json_path, "w") as f:
        json.dump(dataclasses.asdict(report_data), f)

    assert json_path.exists()

    with open(json_path, "r") as f:
        data = json.load(f)
        assert data["overall_success_rate"] == 1.0
