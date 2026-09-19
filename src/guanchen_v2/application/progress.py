"""Transport-independent progress notifications; never send prompts or tool inputs."""

from contextvars import ContextVar
from typing import Callable

progress_sink: ContextVar[Callable[[str, dict], None] | None] = ContextVar("progress_sink", default=None)


def emit_progress(event: str, data: dict) -> None:
    sink = progress_sink.get()
    if sink is not None:
        sink(event, data)
