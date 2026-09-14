from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import ToolMessage

from guanchen_v2.agents.bazi.exceptions import BaziAgentInvariantError
from guanchen_v2.agents.bazi.models import BaziInterpretation, ReadyForBazi
from guanchen_v2.agents.bazi.runtime import BaziAgentRuntime
from guanchen_v2.bazi.adapter import LunarPythonBaziAdapter
from guanchen_v2.knowledge.models import KnowledgeDomain, RetrievalResult, SourceType
from guanchen_v2.models.bazi import BirthProfile, Gender
from guanchen_v2.tools.bazi_retrieval import BaziKnowledgeArtifact


@pytest.fixture
def ready_input():
    return ReadyForBazi(
        question="事业",
        profile=BirthProfile(year=1998, month=7, day=21, hour=14, minute=30, gender=Gender.MALE),
    )


@pytest.mark.asyncio
async def test_runtime_success_exact_tool_calls(ready_input, monkeypatch):
    """确保 Runtime 严格读取了计算工具和检索工具的双端 Artifact。"""
    import guanchen_v2.agents.bazi.runtime

    adapter = LunarPythonBaziAdapter()
    real_chart = adapter.calculate(ready_input.profile)
    bazi_tool_msg = ToolMessage(
        content="{}", name="calculate_bazi", tool_call_id="1", artifact=real_chart
    )

    mock_res = RetrievalResult(
        rank=1,
        chunk_id="c1",
        document_id="d1",
        domain=KnowledgeDomain.BAZI,
        source_title="T",
        source_type=SourceType.PROJECT_NOTE,
        section="S",
        text="T",
        rrf_score=0.9,
        rrf_rank=1,
        reranker_score=None,
        dense_rank=1,
        sparse_rank=1,
    )
    retrieval_tool_msg = ToolMessage(
        content="txt",
        name="retrieve_bazi_knowledge",
        tool_call_id="2",
        artifact=BaziKnowledgeArtifact(results=[mock_res]),
    )

    mock_agent = Mock()
    mock_agent.ainvoke = AsyncMock(
        return_value={
            "messages": [bazi_tool_msg, retrieval_tool_msg],
            "structured_response": BaziInterpretation(answer="成功获取解释", used_chunk_ids=["c1"]),
        }
    )

    monkeypatch.setattr(guanchen_v2.agents.bazi.runtime, "create_agent", lambda **kw: mock_agent)
    monkeypatch.setattr(guanchen_v2.agents.bazi.runtime, "build_chat_model", Mock())
    monkeypatch.setattr(guanchen_v2.agents.bazi.runtime, "build_calculate_bazi_tool", Mock())
    monkeypatch.setattr(
        guanchen_v2.agents.bazi.runtime, "build_retrieve_bazi_knowledge_tool", Mock()
    )

    runtime = BaziAgentRuntime(Mock(), Mock())
    result = await runtime.run(ready_input)

    assert result.answer == "成功获取解释"
    assert result.chart is real_chart
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "c1"


@pytest.mark.asyncio
async def test_runtime_fails_on_zero_tool_calls(ready_input, monkeypatch):
    import guanchen_v2.agents.bazi.runtime

    mock_agent = Mock()
    mock_agent.ainvoke = AsyncMock(
        return_value={
            "messages": [],
            "structured_response": BaziInterpretation(answer="我瞎猜的", used_chunk_ids=[]),
        }
    )
    monkeypatch.setattr(guanchen_v2.agents.bazi.runtime, "create_agent", lambda **kw: mock_agent)
    monkeypatch.setattr(guanchen_v2.agents.bazi.runtime, "build_chat_model", Mock())
    monkeypatch.setattr(guanchen_v2.agents.bazi.runtime, "build_calculate_bazi_tool", Mock())
    monkeypatch.setattr(
        guanchen_v2.agents.bazi.runtime, "build_retrieve_bazi_knowledge_tool", Mock()
    )

    runtime = BaziAgentRuntime(Mock(), Mock())
    with pytest.raises(BaziAgentInvariantError, match="必须只调用 1 次"):
        await runtime.run(ready_input)
