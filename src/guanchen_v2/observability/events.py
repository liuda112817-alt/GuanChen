from dataclasses import dataclass, field
from typing import Any

@dataclass
class ObservabilityEvent:
    timestamp: str
    trace_id: str
    component: str
    event_type: str
    status: str
    duration_ms: float | None
    metadata: dict[str, Any] = field(default_factory=dict)
