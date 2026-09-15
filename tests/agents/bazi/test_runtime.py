from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import ToolMessage

from guanchen_v2.agents.bazi.exceptions import (
    BaziAgentCitationError,
    BaziAgentInvariantError,
)
from guanchen_v2.agents.bazi.models import (
    BaziInterpretation,
    ReadyForBazi,
)
from guanchen_v2.agents.bazi.runtime import (
    BaziAgentRuntime,
)
from guanchen_v2.bazi.adapter import (
    LunarPythonBaziAdapter,
)
from guanchen_v2.knowledge.models import (
    KnowledgeDomain,
    RetrievalResult,
    SourceType,
)
from guanchen_v2.models.bazi import (
    BirthProfile,
    Gender,
)
from guanchen_v2.tools.bazi_retrieval import (
    BaziKnowledgeArtifact,
)


@pytest.fixture
def ready_input():
    return ReadyForBazi(
        question="事业",
        profile=BirthProfile(
            year=1998,
            month=7,
            day=21,
            hour=14,
            minute=30,
            gender=Gender.MALE,
        ),
    )


def _patch_runtime_dependencies(
    monkeypatch,
    mock_agent,
) -> None:
    import guanchen_v2.agents.bazi.runtime

    monkeypatch.setattr(
        guanchen_v2.agents.bazi.runtime,
        "create_agent",
        lambda **kwargs: mock_agent,
    )

    monkeypatch.setattr(
        guanchen_v2.agents.bazi.runtime,
        "build_chat_model",
        Mock(),
    )

    monkeypatch.setattr(
        guanchen_v2.agents.bazi.runtime,
        "build_calculate_bazi_tool",
        Mock(),
    )

    monkeypatch.setattr(
        guanchen_v2.agents.bazi.runtime,
        "build_retrieve_bazi_knowledge_tool",
        Mock(),
    )


def _create_chart(
    ready_input: ReadyForBazi,
):
    adapter = LunarPythonBaziAdapter()
    return adapter.calculate(ready_input.profile)


def _create_retrieval_result(
    chunk_id: str = "c1",
) -> RetrievalResult:
    return RetrievalResult(
        rank=1,
        chunk_id=chunk_id,
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


@pytest.mark.asyncio
async def test_runtime_success_with_calculation_and_retrieval(
    ready_input,
    monkeypatch,
):
    real_chart = _create_chart(ready_input)

    bazi_tool_message = ToolMessage(
        content="{}",
        name="calculate_bazi",
        tool_call_id="1",
        artifact=real_chart,
    )

    retrieval_result = _create_retrieval_result("c1")

    retrieval_tool_message = ToolMessage(
        content="txt",
        name="retrieve_bazi_knowledge",
        tool_call_id="2",
        artifact=BaziKnowledgeArtifact(results=[retrieval_result]),
    )

    mock_agent = Mock()

    mock_agent.ainvoke = AsyncMock(
        return_value={
            "messages": [
                bazi_tool_message,
                retrieval_tool_message,
            ],
            "structured_response": (
                BaziInterpretation(
                    answer="成功获取解释",
                    used_chunk_ids=["c1"],
                )
            ),
        }
    )

    _patch_runtime_dependencies(
        monkeypatch,
        mock_agent,
    )

    runtime = BaziAgentRuntime(
        Mock(),
        Mock(),
    )

    result = await runtime.run(ready_input)

    assert result.answer == "成功获取解释"
    assert result.chart is real_chart

    assert len(result.citations) == 1

    assert result.citations[0].chunk_id == "c1"


@pytest.mark.asyncio
async def test_runtime_success_with_calculation_only(
    ready_input,
    monkeypatch,
):
    """
    用户只询问确定性排盘事实时，
    Retrieval Tool 可以合法地完全不调用。
    """
    real_chart = _create_chart(ready_input)

    bazi_tool_message = ToolMessage(
        content="{}",
        name="calculate_bazi",
        tool_call_id="1",
        artifact=real_chart,
    )

    mock_agent = Mock()

    mock_agent.ainvoke = AsyncMock(
        return_value={
            "messages": [bazi_tool_message],
            "structured_response": (
                BaziInterpretation(
                    answer=("你的日主为当前排盘计算结果所示日主。"),
                    used_chunk_ids=[],
                )
            ),
        }
    )

    _patch_runtime_dependencies(
        monkeypatch,
        mock_agent,
    )

    runtime = BaziAgentRuntime(
        Mock(),
        Mock(),
    )

    result = await runtime.run(ready_input)

    assert result.chart is real_chart

    assert result.answer == "你的日主为当前排盘计算结果所示日主。"

    assert result.citations == ()


@pytest.mark.asyncio
async def test_calculation_only_cannot_fabricate_citation(
    ready_input,
    monkeypatch,
):
    """
    未调用 Retrieval 时，
    structured response 不能凭空声明知识证据。
    """
    real_chart = _create_chart(ready_input)

    bazi_tool_message = ToolMessage(
        content="{}",
        name="calculate_bazi",
        tool_call_id="1",
        artifact=real_chart,
    )

    mock_agent = Mock()

    mock_agent.ainvoke = AsyncMock(
        return_value={
            "messages": [bazi_tool_message],
            "structured_response": (
                BaziInterpretation(
                    answer="带有伪造出处的解释。",
                    used_chunk_ids=["fabricated-chunk"],
                )
            ),
        }
    )

    _patch_runtime_dependencies(
        monkeypatch,
        mock_agent,
    )

    runtime = BaziAgentRuntime(
        Mock(),
        Mock(),
    )

    with pytest.raises(
        BaziAgentCitationError,
        match="未授权的证据编号",
    ):
        await runtime.run(ready_input)


@pytest.mark.asyncio
async def test_runtime_fails_on_zero_calculation_calls(
    ready_input,
    monkeypatch,
):
    mock_agent = Mock()

    mock_agent.ainvoke = AsyncMock(
        return_value={
            "messages": [],
            "structured_response": (
                BaziInterpretation(
                    answer="没有经过排盘的回答。",
                    used_chunk_ids=[],
                )
            ),
        }
    )

    _patch_runtime_dependencies(
        monkeypatch,
        mock_agent,
    )

    runtime = BaziAgentRuntime(
        Mock(),
        Mock(),
    )

    with pytest.raises(
        BaziAgentInvariantError,
        match="必须只调用 1 次",
    ):
        await runtime.run(ready_input)


@pytest.mark.asyncio
async def test_runtime_fails_when_retrieval_has_no_valid_artifact(
    ready_input,
    monkeypatch,
):
    real_chart = _create_chart(ready_input)

    bazi_tool_message = ToolMessage(
        content="{}",
        name="calculate_bazi",
        tool_call_id="1",
        artifact=real_chart,
    )

    malformed_retrieval_message = ToolMessage(
        content="txt",
        name="retrieve_bazi_knowledge",
        tool_call_id="2",
        artifact=None,
    )

    mock_agent = Mock()

    mock_agent.ainvoke = AsyncMock(
        return_value={
            "messages": [
                bazi_tool_message,
                malformed_retrieval_message,
            ],
            "structured_response": (
                BaziInterpretation(
                    answer="解释。",
                    used_chunk_ids=[],
                )
            ),
        }
    )

    _patch_runtime_dependencies(
        monkeypatch,
        mock_agent,
    )

    runtime = BaziAgentRuntime(
        Mock(),
        Mock(),
    )

    with pytest.raises(
        BaziAgentInvariantError,
        match=("未返回合法的 BaziKnowledgeArtifact"),
    ):
        await runtime.run(ready_input)
