import pytest
import mcp.types as types

from guanchen_v2.mcp.server import GuanChenMCPServer


@pytest.mark.asyncio
async def test_tool_registry_discovery():
    """Test 1: 验证 Registry 重构后支持全部三个 Tool 的发现"""
    app = GuanChenMCPServer()
    list_tools_handler = app.server.request_handlers[types.ListToolsRequest]
    
    response = await list_tools_handler(types.ListToolsRequest(method="tools/list"))
    
    tools = response.root.tools
    assert len(tools) == 3
    names = [t.name for t in tools]
    assert "bazi.calculate" in names
    assert "knowledge.search" in names
    assert "liuyao.cast_hexagram" in names