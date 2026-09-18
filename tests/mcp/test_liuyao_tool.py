import json

import mcp.types as types
import pytest

from guanchen_v2.mcp.server import GuanChenMCPServer


@pytest.mark.asyncio
async def test_mcp_liuyao_tool():
    """Test 3: 验证 liuyao.cast_hexagram 返回无状态卦象"""
    app = GuanChenMCPServer()
    call_tool_handler = app.server.request_handlers[types.CallToolRequest]
    
    response = await call_tool_handler(
        types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(
                name="liuyao.cast_hexagram",
                arguments={"question": "近期事业发展", "method": "random"}
            )
        )
    )
    
    assert response.root.isError is not True
    result_text = response.root.content[0].text
    data = json.loads(result_text)
    
    assert "ben_gua" in data
    assert "bian_gua" in data
    assert "dong_yao" in data