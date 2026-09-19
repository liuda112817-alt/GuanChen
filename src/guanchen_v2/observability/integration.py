import contextvars
from guanchen_v2.observability.tracer import Tracer

_tracer_var: contextvars.ContextVar[Tracer | None] = contextvars.ContextVar("current_tracer", default=None)

def set_tracer(tracer: Tracer) -> contextvars.Token:
    return _tracer_var.set(tracer)

def get_tracer() -> Tracer | None:
    return _tracer_var.get()

def reset_tracer(token: contextvars.Token) -> None:
    _tracer_var.reset(token)
