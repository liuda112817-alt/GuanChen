"""Regression coverage for evidence rejection in the real Dream runtime."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from guanchen_v2.dream.exceptions import DreamInterpretationError
from guanchen_v2.dream.runtime import DreamAgentRuntime, DreamInterpretationDraft
from guanchen_v2.models.dream import DreamContextResult, DreamContextStatus, DreamRecord


def runtime(draft):
    context = SimpleNamespace(
        apply_turn=AsyncMock(
            return_value=DreamContextResult(status=DreamContextStatus.UPDATED, record=DreamRecord(raw_descriptions=["synthetic dream"]))
        )
    )
    retrieval = SimpleNamespace(retrieve=AsyncMock(return_value=[]))
    llm = SimpleNamespace(generate_structured=AsyncMock(return_value=draft))
    return DreamAgentRuntime(context, retrieval, llm), llm


@pytest.mark.asyncio
async def test_uncited_paragraph_is_never_exposed_and_does_not_retry():
    agent, llm = runtime(DreamInterpretationDraft(traditional_view="UNSUPPORTED CLAIM", psychological_context_view="Consider your own feelings."))
    result = await agent.handle_turn("synthetic dream")
    assert result.status.value == "answered"
    assert "UNSUPPORTED CLAIM" not in result.response.traditional_view
    assert not result.citations
    llm.generate_structured.assert_awaited_once()


@pytest.mark.asyncio
async def test_hallucinated_evidence_id_still_fails_closed():
    agent, _ = runtime(DreamInterpretationDraft(traditional_view="claim", used_chunk_ids=["nonexistent"], psychological_context_view="reflection"))
    with pytest.raises(DreamInterpretationError):
        await agent.handle_turn("synthetic dream")
