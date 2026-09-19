from dataclasses import dataclass
from typing import Any


@dataclass
class CapabilityEvaluationSummary:
    capability: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    success_rate: float
    average_latency_ms: float


@dataclass
class Stage10EvaluationReport:
    generated_at: str
    capabilities: list[CapabilityEvaluationSummary]
    overall_success_rate: float
    metrics_snapshot: dict[str, Any]
