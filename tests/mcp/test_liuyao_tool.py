import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from guanchen_v2.mcp.server import GuanChenMCPServer
from guanchen_v2.models.liuyao import HexagramResult


@pytest.mark.asyncio
async def test_mcp_liuyao_tool():
    app = GuanChenMCPServer()
    result = await app.server.call_tool("cast_hexagram", {"request": {"method": "manual", "manual": {"lines": [7, 8, 7, 8, 7, 8]}}})
    assert not result.is_error
    facts = HexagramResult.model_validate(json.loads(result.content[0].text))
    assert len(facts.lines) == 6


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{"method": "typo"}, {"method": "manual"}, {"method": "random", "manual": {"lines": [7] * 6}}])
async def test_invalid_method_never_casts(payload):
    app = GuanChenMCPServer()
    with pytest.raises(ToolError):
        await app.server.call_tool("cast_hexagram", {"request": payload})
