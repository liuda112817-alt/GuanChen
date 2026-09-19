import pytest
from mcp import Client

from guanchen_v2.mcp.server import GuanChenMCPServer


@pytest.mark.asyncio
async def test_official_client_validation_failure_is_observed(monkeypatch):
    events = []
    monkeypatch.setattr("guanchen_v2.observability.tracer.log_event", events.append)
    app = GuanChenMCPServer()
    app._knowledge_adapter.service = object()  # No retrieval used by this validation test.
    async with Client(app.server) as client:
        result = await client.call_tool("cast_hexagram", {"request": {"method": "invalid"}})
        assert result.is_error
    assert any(e.component == "mcp" and e.status == "FAILED" for e in events)
