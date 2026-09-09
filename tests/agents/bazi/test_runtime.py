from unittest.mock import Mock

import pytest
from langchain_core.messages import ToolMessage

from guanchen_v2.agents.bazi.exceptions import BaziAgentInvariantError
from guanchen_v2.agents.bazi.models import BaziInterpretation, ReadyForBazi
from guanchen_v2.agents.bazi.runtime import BaziAgentRuntime
from guanchen_v2.bazi.adapter import LunarPythonBaziAdapter
from guanchen_v2.models.bazi import BirthProfile, Gender


@pytest.fixture
def ready_input():
    return ReadyForBazi(
        question="事业",
        profile=BirthProfile(year=1998, month=7, day=21, hour=14, minute=30, gender=Gender.MALE),
    )


def test_runtime_success_exact_one_tool_call(ready_input, monkeypatch):
    import guanchen_v2.agents.bazi.runtime

    mock_agent = Mock()
    adapter = LunarPythonBaziAdapter()
    real_chart = adapter.calculate(ready_input.profile)
    tool_msg = ToolMessage(
        content="{}", name="calculate_bazi", tool_call_id="1", artifact=real_chart
    )

    mock_agent.invoke.return_value = {
        "messages": [tool_msg],
        "structured_response": BaziInterpretation(answer="事业不错"),
    }

    monkeypatch.setattr(guanchen_v2.agents.bazi.runtime, "create_agent", lambda **kw: mock_agent)
    monkeypatch.setattr(guanchen_v2.agents.bazi.runtime, "build_chat_model", Mock())
    monkeypatch.setattr(guanchen_v2.agents.bazi.runtime, "build_calculate_bazi_tool", Mock())

    runtime = BaziAgentRuntime(Mock())
    result = runtime.run(ready_input)

    assert result.question == "事业"
    assert result.chart is real_chart
    assert result.answer == "事业不错"


def test_runtime_fails_on_zero_tool_calls(ready_input, monkeypatch):
    import guanchen_v2.agents.bazi.runtime

    mock_agent = Mock()
    mock_agent.invoke.return_value = {
        "messages": [],  # 危险情况：模型没调工具自己瞎编
        "structured_response": BaziInterpretation(answer="我直接盲猜了"),
    }

    monkeypatch.setattr(guanchen_v2.agents.bazi.runtime, "create_agent", lambda **kw: mock_agent)
    monkeypatch.setattr(guanchen_v2.agents.bazi.runtime, "build_chat_model", Mock())
    monkeypatch.setattr(guanchen_v2.agents.bazi.runtime, "build_calculate_bazi_tool", Mock())

    runtime = BaziAgentRuntime(Mock())
    with pytest.raises(BaziAgentInvariantError, match="必须只调用 1 次"):
        runtime.run(ready_input)
