from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from guanchen_v2.knowledge.models import (
    KnowledgeDomain,
    RetrievalResult,
    SourceType,
)
from guanchen_v2.knowledge.retrieval.service import RetrievalService
from guanchen_v2.tools.bazi_retrieval import BaziKnowledgeQuery, build_retrieve_bazi_knowledge_tool


def test_query_validation_rejects_empty():
    """验证空白字符在工具门槛外就会被阻断。"""
    with pytest.raises(ValidationError, match="不能为空或纯空格"):
        BaziKnowledgeQuery(query="   ")


@pytest.mark.asyncio
async def test_tool_happy_path_and_domain_locking():
    """核心：确认强制锁定了 BAZI 过滤，并且将结果组装成了不包含分数的证据文本。"""
    mock_service = MagicMock(spec=RetrievalService)
    res = RetrievalResult(
        rank=1,
        chunk_id="c1",
        document_id="d1",
        domain=KnowledgeDomain.BAZI,
        source_title="《渊海子平》",
        source_type=SourceType.PUBLIC_DOMAIN_CLASSIC,
        section="卷一",
        text="测试文本",
        rrf_score=0.9,
        rrf_rank=1,
        reranker_score=None,
        dense_rank=1,
        sparse_rank=1,
    )
    mock_service.retrieve = AsyncMock(return_value=[res])

    tool = build_retrieve_bazi_knowledge_tool(mock_service)
    content, artifact = await tool.coroutine(query="测试搜索")

    # 验证底层被呼叫时，死死锁定了领域
    call_kwargs = mock_service.retrieve.call_args.kwargs
    assert call_kwargs["query"] == "测试搜索"
    assert call_kwargs["filters"].domains == frozenset({KnowledgeDomain.BAZI})

    # 验证证据文本对 LLM 做到了极简隔离
    assert "chunk_id: c1" in content
    assert "测试文本" in content
    assert "rrf_score" not in content  # 决不暴露分数给 LLM

    # Artifact 完整留存供下游溯源
    assert artifact.results == [res]


@pytest.mark.asyncio
async def test_tool_empty_results_fallback():
    """验证查无资料时能够给予模型温和退让指引。"""
    mock_service = MagicMock(spec=RetrievalService)
    mock_service.retrieve = AsyncMock(return_value=[])

    tool = build_retrieve_bazi_knowledge_tool(mock_service)
    content, artifact = await tool.coroutine(query="天外飞仙")

    assert "当前知识库未检索到足够依据" in content
    assert artifact.results == []
