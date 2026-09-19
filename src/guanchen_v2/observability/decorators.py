import asyncio
import functools

from guanchen_v2.observability.integration import get_tracer


def trace(component: str, event_type: str):
    def decorator(func):
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                tracer = get_tracer()
                if tracer:
                    with tracer.span(component, event_type) as span:
                        res = await func(*args, **kwargs)
                        if event_type == "ROUTE":
                            route = res["conversation"].routing_result
                            tracer.run.route = "+".join(i.value for i in (route.primary_intent, *route.secondary_intents))
                        if event_type == "RETRIEVAL":
                            span.metadata["retrieved_chunk_ids"] = [r.chunk_id for r in res]
                        # 业务层捕获异常返回 is_error 时，标记状态为 FAILED，交给 Tracer 的 finally 处理指标
                        if getattr(res, "is_error", False) is True:
                            span.status = "FAILED"
                        return res
                return await func(*args, **kwargs)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                tracer = get_tracer()
                if tracer:
                    with tracer.span(component, event_type) as span:
                        res = func(*args, **kwargs)
                        if getattr(res, "is_error", False) is True:
                            span.status = "FAILED"
                        return res
                return func(*args, **kwargs)

            return sync_wrapper

    return decorator
