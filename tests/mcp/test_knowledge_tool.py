from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from guanchen_v2.knowledge.models import KnowledgeDomain, RetrievalResult, SourceType
from guanchen_v2.mcp.server import GuanChenMCPServer


@pytest.mark.asyncio
async def test_mcp_knowledge_tool():
    app = GuanChenMCPServer()
    row = RetrievalResult(
        rank=1,
        chunk_id="c1",
        document_id="d1",
        domain=KnowledgeDomain.BAZI,
        source_title="Book",
        source_type=SourceType.PROJECT_NOTE,
        section="s",
        text="actual text",
        rrf_score=0.1,
        rrf_rank=1,
        reranker_score=None,
        dense_rank=1,
        sparse_rank=1,
    )
    retrieval = SimpleNamespace(retrieve=AsyncMock(return_value=[row]))
    app._knowledge_adapter.service = retrieval
    result = await app.server.call_tool("knowledge_search", {"request": {"query": "五行", "filters": {"source_titles": ["Book"]}}})
    assert not result.is_error
    assert result.structured_content["results"][0]["content"] == "actual text"
    assert result.structured_content["results"][0]["citation"]["document_id"] == "d1"
    assert retrieval.retrieve.await_args.kwargs["filters"].source_titles == frozenset(["Book"])
