import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Generator

from guanchen_v2.observability.context import TraceContext
from guanchen_v2.observability.events import ObservabilityEvent
from guanchen_v2.observability.logger import log_event
from guanchen_v2.observability.metrics import MetricsCollector


@dataclass
class SpanState:
    """
    Tracer span 的运行状态。

    status 可以被：
    - Tracer exception handling 设置为 FAILED；
    - Decorator / Middleware 在业务返回 isError=True 时设置为 FAILED。
    """

    status: str = "SUCCESS"
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


class Tracer:
    def __init__(
        self,
        context: TraceContext,
        metrics: MetricsCollector | None = None,
    ):
        self.context = context
        self.metrics = metrics

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
           调用成功返回，但业务结果包含 isError=True，
           由调用方设置 span.status = FAILED。
        """

        start_time = time.perf_counter()

        # copy，避免修改调用者原始 metadata。
        state = SpanState(
            metadata=dict(
                metadata or {}
            )
        )

        try:
            yield state

        except Exception as exc:
            state.status = "FAILED"

            state.metadata["error"] = type(
                exc
            ).__name__

            state.metadata["error_detail"] = str(
                exc
            )

            raise

        finally:
            duration_ms = (
                time.perf_counter() - start_time
            ) * 1000

            event = ObservabilityEvent(
                timestamp=datetime.now(
                    timezone.utc
                ).isoformat(),
                trace_id=self.context.trace_id,
                component=component,
                event_type=event_type,
                status=state.status,
                duration_ms=duration_ms,
                metadata=state.metadata,
            )

            log_event(
                event
            )

            if self.metrics:
                # 关键修改：
                #
                # 不再只在 except 中统计 error。
                # 最终 SpanState.status 为 FAILED，
                # 无论来自 Exception 还是 isError=True，
                # 都应该统计为失败。
                if state.status == "FAILED":
                    self.metrics.increment(
                        f"{component}_error_total"
                    )

                self.metrics.increment(
                    f"{component}_{event_type}_total"
                )

                self.metrics.observe(
                    f"{component}_{event_type}_latency_ms",
                    duration_ms,
                )