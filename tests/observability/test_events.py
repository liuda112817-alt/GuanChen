from guanchen_v2.observability.events import ObservabilityEvent


def test_observability_event_model():
    event = ObservabilityEvent(
        timestamp="2026-09-18T10:00:00Z",
        trace_id="test_trace",
        component="bazi",
        event_type="SERVICE_CALL",
        status="SUCCESS",
        duration_ms=120.5,
        metadata={"year": 1990},
    )

    assert event.trace_id == "test_trace"
    assert event.component == "bazi"
    assert event.metadata["year"] == 1990
