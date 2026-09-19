import pytest

from guanchen_v2.mcp.server import GuanChenMCPServer


@pytest.mark.asyncio
async def test_tool_registry_discovery():
    tools = await GuanChenMCPServer().server.list_tools()
    assert {t.name for t in tools} == {"calculate_bazi", "knowledge_search", "cast_hexagram"}
    bazi = next(t for t in tools if t.name == "calculate_bazi")
    assert "request" in bazi.input_schema["properties"]
