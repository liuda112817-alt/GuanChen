import json
from unittest.mock import AsyncMock, MagicMock

import mcp.types as types
import pytest

from guanchen_v2.mcp.server import GuanChenMCPServer


@pytest.mark.asyncio
async def test_mcp_knowledge_tool():
    """Test 2: 验证 knowledge.search 调用链路与 Citation 返回"""
    app = GuanChenMCPServer()
    
    # Mock Database RetrievalService
    mock_retrieval = AsyncMock()
    mock_result = MagicMock()
    mock_result.content = "【经文】测试内容"
    mock_result.source_title = "滴天髓阐微"
    mock_result.section = "天干"
    mock_result.chunk_id = "chunk_001"
    mock_retrieval.search.return_value = [mock_result]
    
    app._knowledge_adapter.service = mock_retrieval
    
    call_tool_handler = app.server.request_handlers[types.CallToolRequest]
    response = await call_tool_handler(
        types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(
                name="knowledge.search",
                arguments={"query": "五行生克制化"}
            )
        )
    )
    
    assert response.root.isError is not True
    result_text = response.root.content[0].text
    data = json.loads(result_text)
    
    assert "results" in data
    assert data["results"][0]["citation"]["source_title"] == "滴天髓阐微"
    
    mock_retrieval.search.assert_awaited_once()