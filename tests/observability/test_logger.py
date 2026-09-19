import json

from guanchen_v2.observability.events import ObservabilityEvent
from guanchen_v2.observability.logger import log_event


def test_structured_logger():
    event = ObservabilityEvent(
        timestamp="2026-09-18T10:00:00Z",
        trace_id="trace_xyz",
        component="mcp",
        event_type="TOOL_CALL",
        status="FAILED",
        duration_ms=45.0,
        metadata={"error": "Not Found"},
    )

    json_str = log_event(event)
    parsed = json.loads(json_str)

    assert parsed["trace_id"] == "trace_xyz"
    assert parsed["status"] == "FAILED"
    assert parsed["duration_ms"] == 45.0
    assert parsed["metadata"]["error"] == "Not Found"
