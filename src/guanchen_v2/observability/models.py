from dataclasses import dataclass, field


@dataclass
class RunStep:
    agent: str | None
    node: str | None
    tool: str | None
    kind: str
    latency_ms: float
    token: dict[str, int] | None
    error: str | None
    retrieved_chunk_ids: list[str]
    status: str


@dataclass
class AgentRun:
    trace_id: str
    route: str = "unresolved"
    status: str = "RUNNING"
    latency_ms: float = 0
    model_call_limit: int = 20
    tool_call_limit: int = 4
    model_calls: int = 0
    tool_calls: int = 0
    steps: list[RunStep] = field(default_factory=list)


class CallBudgetExceeded(RuntimeError):
    pass
