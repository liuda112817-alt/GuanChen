import pytest
import mcp.types as types

from guanchen_v2.mcp.server import GuanChenMCPServer

@pytest.mark.asyncio
async def test_mcp_bazi_discovery():
    """Test 1: Tool Discovery 验证返回正确的 bazi.calculate 定义"""
    app = GuanChenMCPServer()
    
    list_tools_handler = app.server.request_handlers[types.ListToolsRequest]
    response = await list_tools_handler(
        types.ListToolsRequest(method="tools/list")
    )
    
    tools = response.root.tools
    # Task 4 后已经注册了 3 个工具，所以只要 >= 1 即可
    assert len(tools) >= 1
    
    # 找到 bazi.calculate 并验证
    bazi_tool = next((t for t in tools if t.name == "bazi.calculate"), None)
    assert bazi_tool is not None
    assert bazi_tool.description == "Calculate a structured Bazi chart from birth information."

@pytest.mark.asyncio
async def test_mcp_bazi_valid_input():
    """Test 2: Valid Input 验证成功结果并触发了 Bazi Service 计算"""
    app = GuanChenMCPServer()
    call_tool_handler = app.server.request_handlers[types.CallToolRequest]
    
    response = await call_tool_handler(
        types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(
                name="bazi.calculate",
                arguments={
                    "year": 1990,
                    "month": 1,
                    "day": 1,
                    "hour": 12,
                    "minute": 30,
                    "gender": "male"
                }
            )
        )
    )
    
    assert response.root.isError is not True
    assert len(response.root.content) == 1
    result_text = response.root.content[0].text
    
    # 校验八字特有字段确实从 Domain Service 正确生成和返回
    assert "year_pillar" in result_text
    assert "day_master" in result_text

@pytest.mark.asyncio
async def test_mcp_bazi_invalid_input():
    """Test 3: Invalid Input 验证 MCP Protocol 层的异常拦截"""
    app = GuanChenMCPServer()
    call_tool_handler = app.server.request_handlers[types.CallToolRequest]
    
    response = await call_tool_handler(
        types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(
                name="bazi.calculate",
                arguments={
                    "year": "abc",  # 非法参数
                    "month": 1
                }
            )
        )
    )
    
    assert response.root.isError is True
    assert len(response.root.content) == 1
    
    error_msg = response.root.content[0].text.lower()
    assert "validation error" in error_msg or "invalid" in error_msg