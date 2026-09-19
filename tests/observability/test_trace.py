import pytest
from guanchen_v2.observability.context import TraceContext
from guanchen_v2.observability.tracer import Tracer
from guanchen_v2.observability.metrics import MetricsCollector

def test_trace_context_creation():
    ctx = TraceContext.create()
    assert ctx.trace_id.startswith("trace_")

def test_tracer_span_success():
    ctx = TraceContext.create()
    metrics = MetricsCollector()
    tracer = Tracer(context=ctx, metrics=metrics)
    
    with tracer.span(component="bazi", event_type="SERVICE_CALL", metadata={"test": True}):
        # Mocking some work
        _ = 1 + 1
        
    assert metrics.get_counter("bazi_SERVICE_CALL_total") == 1
    assert metrics.get_average_observation("bazi_SERVICE_CALL_latency_ms") > 0

def test_tracer_span_failure():
    ctx = TraceContext.create()
    metrics = MetricsCollector()
    tracer = Tracer(context=ctx, metrics=metrics)
    
    with pytest.raises(ValueError):
        with tracer.span(component="knowledge", event_type="SEARCH"):
            raise ValueError("Intentional error")
            
    assert metrics.get_counter("knowledge_error_total") == 1