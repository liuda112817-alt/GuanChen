from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvaluationCase:
    id: str
    capability: str
    input: dict[str, Any]
    expected: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    case_id: str
    capability: str
    success: bool
    output: dict[str, Any] | None
    error: str | None
    latency_ms: float
