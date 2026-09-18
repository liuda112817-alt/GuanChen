import mcp.types as types
import pytest

from guanchen_v2.mcp.registry import ToolRegistry


@pytest.mark.asyncio
async def test_mcp_permission_denied():
    """Test 4: 验证 ToolRegistry 的权限拦截机制"""
    registry = ToolRegistry()
    
    async def dummy_handler(args):
        return types.CallToolResult(content=[types.TextContent(type="text", text="Success")])
        
    registry.register(
        name="protected.tool", 
        handler=dummy_handler, 
        metadata={"name": "protected.tool", "description": "", "inputSchema": {}, "permission": "protected.read"}
    )
    
    # Missing required permission
    response = await registry.dispatch("protected.tool", {}, "client_1", ["other.permission"])
    
    assert response.isError is True
    assert "Permission denied" in response.content[0].text