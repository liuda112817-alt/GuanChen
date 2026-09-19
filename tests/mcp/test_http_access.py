import httpx
import pytest
from starlette.responses import JSONResponse

from guanchen_v2.mcp.registry import access_context
from guanchen_v2.mcp.server import BearerAccess, GuanChenMCPServer


@pytest.mark.asyncio
async def test_http_token_and_scopes_reach_actual_registry():
    server = GuanChenMCPServer()

    async def endpoint(scope, receive, send):
        client, permissions = access_context.get()
        result = await server._registry.dispatch("cast_hexagram", {"method": "random"}, client, permissions)
        await JSONResponse({"denied": result.is_error})(scope, receive, send)

    app = BearerAccess(endpoint, "synthetic-token", ["knowledge.read"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
        assert (await client.post("/mcp")).status_code == 401
        assert (await client.post("/mcp", headers={"Authorization": "Bearer wrong"})).status_code == 401
        response = await client.post("/mcp", headers={"Authorization": "Bearer synthetic-token"})
        assert response.json() == {"denied": True}
