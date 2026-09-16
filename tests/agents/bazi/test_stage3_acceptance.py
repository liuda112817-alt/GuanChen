from unittest.mock import AsyncMock, Mock

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

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_runtime():
    runtime = Mock()
    runtime.run = AsyncMock(return_value=Mock(spec=BaziAgentResult))
    return runtime


async def test_A01_complete_data_ready_for_bazi(mock_runtime):
    initial = BaziAgentInput(question="分析事业", year=1998, month=7, day=21, hour=14, minute=30, gender=Gender.MALE)
    session = BaziTaskSession(initial, mock_runtime)
    result = await session.evaluate()
    assert isinstance(result, BaziAgentResult)
    assert mock_runtime.run.call_count == 1


async def test_A02_missing_time(mock_runtime):
    initial = BaziAgentInput(question="看看事业", year=1998, month=7, day=21, gender=Gender.MALE)
    session = BaziTaskSession(initial, mock_runtime)
    result = await session.evaluate()
    assert isinstance(result, NeedUserInput)
    assert result.missing_fields == [MissingField.HOUR, MissingField.MINUTE]


async def test_A03_missing_gender(mock_runtime):
    initial = BaziAgentInput(question="事业", year=1998, month=7, day=21, hour=14, minute=30)
    session = BaziTaskSession(initial, mock_runtime)
    result = await session.evaluate()
    assert isinstance(result, NeedUserInput)


async def test_A04_multi_turn_repeated_supplement(mock_runtime):
    session = BaziTaskSession(BaziAgentInput(question="感情", year=1998), mock_runtime)
    assert isinstance(await session.supplement(BaziBirthDataPatch(month=7, day=21)), NeedUserInput)
    assert isinstance(await session.supplement(BaziBirthDataPatch(hour=14)), NeedUserInput)
    r4 = await session.supplement(BaziBirthDataPatch(minute=30, gender=Gender.MALE))
    assert isinstance(r4, BaziAgentResult)
    assert mock_runtime.run.call_count == 1
