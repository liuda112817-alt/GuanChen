import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from guanchen_v2.bazi.adapter import LunarPythonBaziAdapter
from guanchen_v2.bazi.service import BaziService
from guanchen_v2.mcp.server import GuanChenMCPServer
from guanchen_v2.models.bazi import BirthProfile


@pytest.mark.asyncio
async def test_mcp_bazi_valid_input():
    app = GuanChenMCPServer()
    result = await app.server.call_tool(
        "calculate_bazi", {"request": {"year": 1990, "month": 1, "day": 1, "hour": 12, "minute": 30, "gender": "male"}}
    )
    assert not result.is_error
    expected = BaziService(LunarPythonBaziAdapter()).calculate(BirthProfile(year=1990, month=1, day=1, hour=12, minute=30, gender="male"))
    assert json.loads(result.content[0].text) == expected.model_dump(mode="json")


@pytest.mark.asyncio
async def test_mcp_bazi_invalid_input():
    app = GuanChenMCPServer()
    with pytest.raises(ToolError):
        await app.server.call_tool("calculate_bazi", {"request": {"year": "abc", "month": 1}})
