import uuid
from dataclasses import dataclass

@dataclass
class TraceContext:
    trace_id: str
    parent_id: str | None = None

    @classmethod
    def create(cls, prefix: str = "trace") -> "TraceContext":
        return cls(trace_id=f"{prefix}_{uuid.uuid4().hex[:12]}")
