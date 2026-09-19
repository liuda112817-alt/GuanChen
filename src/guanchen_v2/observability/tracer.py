import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Generator

from guanchen_v2.application.progress import emit_progress
from guanchen_v2.observability.context import TraceContext
from guanchen_v2.observability.events import ObservabilityEvent
from guanchen_v2.observability.logger import log_event
from guanchen_v2.observability.metrics import MetricsCollector
from guanchen_v2.observability.models import AgentRun, CallBudgetExceeded, RunStep

_agent = ContextVar("trace_agent", default=None)
_node = ContextVar("trace_node", default=None)


@dataclass
class SpanState:
    """
    Tracer span 的运行状态。

    status 可以被：
    - Tracer exception handling 设置为 FAILED；
    - Decorator / Middleware 在业务返回 is_error=True 时设置为 FAILED。
    """

    status: str = "SUCCESS"
    metadata: dict[str, Any] = field(default_factory=dict)


class Tracer:
    def __init__(
        self,
        context: TraceContext,
        metrics: MetricsCollector | None = None,
    ):
        self.context = context
        self.metrics = metrics
        self.run = AgentRun(trace_id=context.trace_id)

    @contextmanager
    def span(
        self,
        component: str,
        event_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> Generator[SpanState, None, None]:
        """
        创建一个完整 execution span。

        一个 span 最终生成一个 ObservabilityEvent。

        支持两类失败：

        1. Exception Failure
           span 内抛出 Exception。

        2. Result Failure
           调用成功返回，但业务结果包含 is_error=True，
           由调用方设置 span.status = FAILED。
        """

        start_time = time.perf_counter()
        if event_type == "LLM":
            if self.run.model_calls >= self.run.model_call_limit:
                raise CallBudgetExceeded("Model call budget exceeded")
            self.run.model_calls += 1
        if event_type == "TOOL":
            if self.run.tool_calls >= self.run.tool_call_limit:
                raise CallBudgetExceeded("Tool call budget exceeded")
            self.run.tool_calls += 1
        agent_token = _agent.set(component) if event_type == "AGENT" else None
        node_token = _node.set(component) if event_type == "NODE" else None

        # copy，避免修改调用者原始 metadata。
        state = SpanState(metadata=dict(metadata or {}))
        if event_type == "TOOL":
            emit_progress("tool_start", {"tool": component})

        try:
            yield state

        except BaseException as exc:
            state.status = "INTERRUPTED" if type(exc).__name__ == "GraphInterrupt" else "FAILED"

            if state.status == "FAILED":
                state.metadata["error"] = type(exc).__name__

            raise

        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.run.steps.append(
                RunStep(
                    agent=_agent.get(),
                    node=_node.get(),
                    tool=component if event_type == "TOOL" else None,
                    kind=event_type,
                    latency_ms=duration_ms,
                    token=state.metadata.get("token"),
                    error=state.metadata.get("error"),
                    retrieved_chunk_ids=state.metadata.get("retrieved_chunk_ids", []),
                    status=state.status,
                )
            )
            if agent_token is not None:
                _agent.reset(agent_token)
            if node_token is not None:
                _node.reset(node_token)

            step = self.run.steps[-1]
            if event_type == "TOOL":
                emit_progress("tool_end", {"tool": component, "status": state.status})
            elif event_type == "RETRIEVAL":
                emit_progress("retrieval", {"chunk_ids": step.retrieved_chunk_ids, "status": state.status})
            elif event_type == "ROUTE" and state.status == "SUCCESS":
                emit_progress("route", {"intents": self.run.route.split("+")})
            state.metadata.update(agent=step.agent, node=step.node, tool=step.tool)
            event = ObservabilityEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                trace_id=self.context.trace_id,
                component=component,
                event_type=event_type,
                status=state.status,
                duration_ms=duration_ms,
                metadata=state.metadata,
            )

            log_event(event)

            if self.metrics:
                # 关键修改：
                #
                # 不再只在 except 中统计 error。
                # 最终 SpanState.status 为 FAILED，
                # 无论来自 Exception 还是 is_error=True，
                # 都应该统计为失败。
                if state.status == "FAILED":
                    self.metrics.increment(f"{component}_error_total")

                self.metrics.increment(f"{component}_{event_type}_total")

                self.metrics.observe(
                    f"{component}_{event_type}_latency_ms",
                    duration_ms,
                )
