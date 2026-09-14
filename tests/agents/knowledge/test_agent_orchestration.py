from unittest.mock import AsyncMock, MagicMock

import pytest

from guanchen_v2.agents.knowledge.agent import KnowledgeAgent
from guanchen_v2.agents.knowledge.models import KnowledgeAnswerDraft
from guanchen_v2.knowledge.errors import KnowledgeAgentError, KnowledgeRetrievalError
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


def _create_result(chunk_id: str, rank: int) -> RetrievalResult:
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


@pytest.mark.asyncio
async def test_retrieval_service_propagate_filters():
    """证明 Service 在调用 Dense/Sparse 时，毫无保留地下发了统一的 Filter，没自作主张。"""
    mock_dense = MagicMock(spec=DenseRetriever)
    mock_sparse = MagicMock(spec=SparseRetriever)
    mock_dense.search = AsyncMock(return_value=[])
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

    filters = RetrievalFilter(domains=frozenset({KnowledgeDomain.BAZI}))
    await service.retrieve("Query", filters=filters)

    # 双方接收到的指令和过滤器必须一模一样
    mock_dense.search.assert_called_once_with("Query", limit=5, filters=filters)
    mock_sparse.search.assert_called_once_with("Query", limit=5, filters=filters)


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
        MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), 5, 2
    )
    with pytest.raises(KnowledgeRetrievalError, match="不能为空"):
        await service.retrieve("   ")


@pytest.mark.asyncio
async def test_agent_empty_evidence_bypasses_llm_and_single_call():
    """无证不审测试：什么都没查到时，不但 LLM 不被唤醒，而且只进行了一次检索调用。"""
    mock_service = MagicMock(spec=RetrievalService)
    mock_service.retrieve = AsyncMock(return_value=[])
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.generate_structured = AsyncMock()

    agent = KnowledgeAgent(mock_service, mock_llm)
    resp = await agent.answer("什么是八字？")

    assert "无法据此作答" in resp.answer
    assert resp.evidence_sufficient is False
    # 【核心】：确保检索只被调用 1 次，没有诡异的自我反思重试
    mock_service.retrieve.assert_called_once_with(query="什么是八字？", filters=None)
    mock_llm.generate_structured.assert_not_called()


@pytest.mark.asyncio
async def test_agent_zero_citations_discards_llm_hallucination():
    """【绝对核心】无引用必杀：如果模型交白卷却夹带私货，代码将彻底销毁其回答，返回防幻觉标准底牌！"""
    mock_service = MagicMock(spec=RetrievalService)
    mock_service.retrieve = AsyncMock(return_value=[_create_result("合法", 1)])

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.generate_structured = AsyncMock(
        return_value=KnowledgeAnswerDraft(
            answer="这是我自己背下来的知识，我要输出给你！",
            evidence_sufficient=False,
            used_chunk_ids=[],  # 重点：模型没有引用任何合法证据
        )
    )

    resp = await KnowledgeAgent(mock_service, mock_llm).answer("查")

    # 模型的私货被彻底物理抹除！
    assert resp.answer == "当前知识库中没有检索到足够依据，无法据此作答。"
    assert resp.evidence_sufficient is False
    assert len(resp.citations) == 0


@pytest.mark.asyncio
async def test_agent_insufficient_evidence_enforces_stamp_securely():
    """部分引用防线：模型引用了证据，但又调皮捣蛋试图混淆前缀，代码强制盖章于最前方。"""
    mock_service = MagicMock(spec=RetrievalService)
    mock_service.retrieve = AsyncMock(return_value=[_create_result("合法_1", 1)])

    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.generate_structured = AsyncMock(
        return_value=KnowledgeAnswerDraft(
            answer="哪怕这里有 现有检索证据不足以完整回答该问题 的子串，你也不能放过我。",
            evidence_sufficient=False,
            used_chunk_ids=["合法_1"],  # 重点：提供了合法引用，所以这是部分回答
        )
    )

    resp = await KnowledgeAgent(mock_service, mock_llm).answer("查")

    # 无论中间有多像，开头必定被盖上强制钢印
    assert resp.answer.startswith("现有检索证据不足以完整回答该问题。\n\n")
    assert "哪怕这里有" in resp.answer


@pytest.mark.asyncio
async def test_agent_llm_fabrication_fails_fast():
    mock_service = MagicMock(spec=RetrievalService)
    mock_service.retrieve = AsyncMock(return_value=[_create_result("合法_1", 1)])
    mock_llm = MagicMock(spec=LLMClient)

    mock_llm.generate_structured = AsyncMock(
        return_value=KnowledgeAnswerDraft(
            answer="编得很圆", evidence_sufficient=True, used_chunk_ids=["合法_1", "虚构的_999"]
        )
    )

    with pytest.raises(KnowledgeAgentError, match="未授权的证据编号"):
        await KnowledgeAgent(mock_service, mock_llm).answer("查询")


@pytest.mark.asyncio
async def test_knowledge_answer_draft_pydantic_invariants():
    """直接在模型层面拦截 '声称充分但交白卷' 的欺骗行为。"""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="必须至少提供一个实际引用的 chunk_id"):
        KnowledgeAnswerDraft(answer="满分答案", evidence_sufficient=True, used_chunk_ids=[])

    # 合法的不足情况
    draft = KnowledgeAnswerDraft(answer="我不知道", evidence_sufficient=False, used_chunk_ids=[])
    assert draft.evidence_sufficient is False
