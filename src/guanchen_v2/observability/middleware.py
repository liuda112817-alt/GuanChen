from guanchen_v2.observability.integration import get_tracer


class TraceMiddleware:
    @staticmethod
    async def execute(component: str, operation: str, handler, *args, **kwargs):
        tracer = get_tracer()
        if tracer:
            with tracer.span(component, operation) as span:
                try:
                    res = await handler(*args, **kwargs)
                    if getattr(res, "is_error", False):
                        span.status = "FAILED"
                    return res
                except Exception as e:
                    span.status = "FAILED"
                    span.metadata["error"] = type(e).__name__
                    raise
        return await handler(*args, **kwargs)
