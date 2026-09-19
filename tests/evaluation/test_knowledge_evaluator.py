import pytest
from unittest.mock import AsyncMock, MagicMock
from guanchen_v2.evaluation.models import EvaluationCase
from guanchen_v2.evaluation.evaluators.knowledge import KnowledgeEvaluator

@pytest.mark.asyncio
async def test_knowledge_evaluator_citation_check():
    mock_service = AsyncMock()
    mock_result = MagicMock()
    mock_result.source_title = "Mock Book"
    mock_result.chunk_id = "chunk_123"
    # Ensure model_dump doesn't break
    mock_result.model_dump.return_value = {"text": "mock"}
    mock_service.search.return_value = [mock_result]
    
    evaluator = KnowledgeEvaluator(mock_service)
    
    case = EvaluationCase(
        id="test_002",
        capability="knowledge.search",
        input={"query": "test query", "top_k": 5},
        expected={"required_citation": True}
    )
    
    result = await evaluator.evaluate_case(case)
    assert result.success is True
    mock_service.search.assert_awaited_once_with(query="test query", limit=5)
