from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from guanchen_v2.agents.knowledge.agent import KnowledgeAgent
from guanchen_v2.agents.knowledge.models import KnowledgeAnswerDraft
from guanchen_v2.knowledge.errors import (
    KnowledgeAgentError,
    KnowledgeRetrievalError,
)
from guanchen_v2.knowledge.models import (
    KnowledgeDomain,
    RetrievalFilter,
    RetrievalResult,
    SourceType,
)
from guanchen_v2.knowledge.retrieval.dense import DenseRetriever
from guanchen_v2.knowledge.retrieval.service import RetrievalService
from guanchen_v2.knowledge.retrieval.sparse import SparseRetriever
from guanchen_v2.llm.client import LLMClient


def _create_result(
    chunk_id: str,
    rank: int,
) -> RetrievalResult:
    return RetrievalResult(
        rank=rank,
        chunk_id=chunk_id,
        document_id="doc1",
        domain=KnowledgeDomain.BAZI,
        source_title="T",
        source_type=SourceType.PROJECT_NOTE,
        section="S",
        text="TXT",
        rrf_score=0.9,
        rrf_rank=rank,
        reranker_score=None,
        dense_rank=1,
        sparse_rank=2,
    )


def _create_llm_mock() -> MagicMock:
    mock_llm = MagicMock(spec_set=LLMClient)
    mock_llm.generate_structured = AsyncMock()
    return mock_llm


@pytest.mark.asyncio
async def test_retrieval_service_propagates_filters():
    mock_dense = MagicMock(spec=DenseRetriever)
    mock_sparse = MagicMock(spec=SparseRetriever)

    mock_dense.search = AsyncMock(return_value=[])
    mock_sparse.search = MagicMock(return_value=[])

    mock_rrf = MagicMock()
    mock_reranker = MagicMock()
    mock_assembler = MagicMock()

    mock_rrf.fuse.return_value = []

    service = RetrievalService(
        mock_dense,
        mock_sparse,
        mock_rrf,
        mock_reranker,
        mock_assembler,
        candidate_limit=5,
        result_limit=2,
    )

    filters = RetrievalFilter(
        domains=frozenset(
            {
                KnowledgeDomain.BAZI,
            }
        )
    )

    await service.retrieve(
        "Query",
        filters=filters,
    )

    mock_dense.search.assert_called_once_with(
        "Query",
        limit=5,
        filters=filters,
    )

    mock_sparse.search.assert_called_once_with(
        "Query",
        limit=5,
        filters=filters,
    )


@pytest.mark.asyncio
async def test_retrieval_service_limits_safeguards():
    with pytest.raises(KnowledgeRetrievalError):
        RetrievalService(
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            MagicMock(),
            candidate_limit=2,
            result_limit=5,
        )

    service = RetrievalService(
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        5,
        2,
    )

    with pytest.raises(
        KnowledgeRetrievalError,
        match="不能为空",
    ):
        await service.retrieve("   ")


@pytest.mark.asyncio
async def test_agent_empty_evidence_bypasses_llm_and_single_call():
    mock_service = MagicMock(spec=RetrievalService)
    mock_service.retrieve = AsyncMock(return_value=[])

    mock_llm = _create_llm_mock()

    agent = KnowledgeAgent(
        mock_service,
        mock_llm,
    )

    response = await agent.answer("什么是八字？")

    assert "无法据此作答" in response.answer
    assert response.evidence_sufficient is False
    assert response.citations == ()

    mock_service.retrieve.assert_awaited_once_with(
        query="什么是八字？",
        filters=None,
    )

    mock_llm.generate_structured.assert_not_awaited()


@pytest.mark.asyncio
async def test_agent_uses_canonical_structured_llm_contract():
    mock_service = MagicMock(spec=RetrievalService)
    mock_service.retrieve = AsyncMock(
        return_value=[
            _create_result(
                "合法_1",
                1,
            )
        ]
    )

    mock_llm = _create_llm_mock()
    mock_llm.generate_structured.return_value = KnowledgeAnswerDraft(
        answer="基于证据作答。",
        evidence_sufficient=True,
        used_chunk_ids=["合法_1"],
    )

    agent = KnowledgeAgent(
        mock_service,
        mock_llm,
    )

    await agent.answer("查询")

    mock_llm.generate_structured.assert_awaited_once()

    kwargs = mock_llm.generate_structured.await_args.kwargs

    assert set(kwargs) == {
        "system_prompt",
        "user_prompt",
        "schema",
    }

    assert kwargs["schema"] is KnowledgeAnswerDraft

    assert "GuanChen Knowledge Agent" in kwargs["system_prompt"]

    assert "=== EVIDENCE START ===" in kwargs["user_prompt"]

    assert "问题：查询" in kwargs["user_prompt"]


@pytest.mark.asyncio
async def test_agent_zero_citations_discards_llm_answer():
    mock_service = MagicMock(spec=RetrievalService)

    mock_service.retrieve = AsyncMock(
        return_value=[
            _create_result(
                "合法",
                1,
            )
        ]
    )

    mock_llm = _create_llm_mock()

    mock_llm.generate_structured.return_value = KnowledgeAnswerDraft(
        answer="没有引用证据的回答。",
        evidence_sufficient=False,
        used_chunk_ids=[],
    )

    response = await KnowledgeAgent(
        mock_service,
        mock_llm,
    ).answer("查")

    assert response.answer == "当前知识库中没有检索到足够依据，无法据此作答。"

    assert response.evidence_sufficient is False
    assert response.citations == ()


@pytest.mark.asyncio
async def test_agent_insufficient_evidence_enforces_stamp():
    mock_service = MagicMock(spec=RetrievalService)

    mock_service.retrieve = AsyncMock(
        return_value=[
            _create_result(
                "合法_1",
                1,
            )
        ]
    )

    mock_llm = _create_llm_mock()

    mock_llm.generate_structured.return_value = KnowledgeAnswerDraft(
        answer=("这里包含部分证据支持的内容。"),
        evidence_sufficient=False,
        used_chunk_ids=["合法_1"],
    )

    response = await KnowledgeAgent(
        mock_service,
        mock_llm,
    ).answer("查")

    assert response.answer.startswith("现有检索证据不足以完整回答该问题。\n\n")

    assert "这里包含部分证据支持的内容。" in (response.answer)

    assert len(response.citations) == 1
    assert response.citations[0].chunk_id == "合法_1"


@pytest.mark.asyncio
async def test_agent_llm_fabrication_fails_fast():
    mock_service = MagicMock(spec=RetrievalService)

    mock_service.retrieve = AsyncMock(
        return_value=[
            _create_result(
                "合法_1",
                1,
            )
        ]
    )

    mock_llm = _create_llm_mock()

    mock_llm.generate_structured.return_value = KnowledgeAnswerDraft(
        answer="存在伪造证据编号。",
        evidence_sufficient=True,
        used_chunk_ids=[
            "合法_1",
            "虚构的_999",
        ],
    )

    with pytest.raises(
        KnowledgeAgentError,
        match="未授权的证据编号",
    ):
        await KnowledgeAgent(
            mock_service,
            mock_llm,
        ).answer("查询")


def test_knowledge_answer_draft_pydantic_invariants():
    with pytest.raises(
        ValidationError,
        match="必须至少提供一个实际引用的 chunk_id",
    ):
        KnowledgeAnswerDraft(
            answer="回答",
            evidence_sufficient=True,
            used_chunk_ids=[],
        )

    draft = KnowledgeAnswerDraft(
        answer="证据不足。",
        evidence_sufficient=False,
        used_chunk_ids=[],
    )

    assert draft.evidence_sufficient is False
