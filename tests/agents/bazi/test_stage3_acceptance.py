from unittest.mock import Mock

import pytest

from guanchen_v2.agents.bazi.models import (
    BaziAgentInput,
    BaziAgentResult,
    BaziBirthDataPatch,
    MissingField,
    NeedUserInput,
)
from guanchen_v2.agents.bazi.session import BaziTaskSession
from guanchen_v2.models.bazi import Gender


@pytest.fixture
def mock_runtime():
    runtime = Mock()
    runtime.run.return_value = Mock(spec=BaziAgentResult)
    return runtime


def test_A01_complete_data_ready_for_bazi(mock_runtime):
    """A01: 资料完整 -> ReadyForBazi，进入 Runtime"""
    initial = BaziAgentInput(
        question="请从传统八字视角分析我的事业倾向。",
        year=1998,
        month=7,
        day=21,
        hour=14,
        minute=30,
        gender=Gender.MALE,
    )
    session = BaziTaskSession(initial, mock_runtime)

    result = session.evaluate()

    assert isinstance(result, BaziAgentResult)
    assert mock_runtime.run.call_count == 1

    ready_input = mock_runtime.run.call_args.args[0]
    assert ready_input.question == "请从传统八字视角分析我的事业倾向。"
    assert ready_input.profile.year == 1998


def test_A02_missing_time(mock_runtime):
    """A02: 缺时间 -> NeedUserInput(hour, minute)，Runtime不执行"""
    initial = BaziAgentInput(question="看看事业", year=1998, month=7, day=21, gender=Gender.MALE)
    session = BaziTaskSession(initial, mock_runtime)

    result = session.evaluate()

    assert isinstance(result, NeedUserInput)
    assert result.missing_fields == [MissingField.HOUR, MissingField.MINUTE]
    assert mock_runtime.run.call_count == 0


def test_A03_missing_gender(mock_runtime):
    """A03: 缺性别 -> NeedUserInput(gender)，绝对不让大模型去猜性别，Runtime不执行"""
    initial = BaziAgentInput(question="看看事业", year=1998, month=7, day=21, hour=14, minute=30)
    session = BaziTaskSession(initial, mock_runtime)

    result = session.evaluate()

    assert isinstance(result, NeedUserInput)
    assert result.missing_fields == [MissingField.GENDER]
    assert mock_runtime.run.call_count == 0


def test_A04_multi_turn_repeated_supplement(mock_runtime):
    """A04: 跨多轮补充，仅在最后一次补充后进入 Runtime，原问题全链路保留"""
    session = BaziTaskSession(BaziAgentInput(question="我想分析感情", year=1998), mock_runtime)

    # Turn 2
    r2 = session.supplement(BaziBirthDataPatch(month=7, day=21))
    assert isinstance(r2, NeedUserInput)
    assert mock_runtime.run.call_count == 0

    # Turn 3
    r3 = session.supplement(BaziBirthDataPatch(hour=14))
    assert isinstance(r3, NeedUserInput)
    assert mock_runtime.run.call_count == 0

    # Turn 4 (Complete)
    r4 = session.supplement(BaziBirthDataPatch(minute=30, gender=Gender.MALE))
    assert isinstance(r4, BaziAgentResult)
    assert mock_runtime.run.call_count == 1

    # 验证最终输送给 Runtime 的权威数据
    ready_input = mock_runtime.run.call_args.args[0]
    assert ready_input.question == "我想分析感情"
    assert ready_input.profile.year == 1998
    assert ready_input.profile.month == 7
    assert ready_input.profile.day == 21
    assert ready_input.profile.hour == 14
    assert ready_input.profile.minute == 30
    assert ready_input.profile.gender == Gender.MALE
