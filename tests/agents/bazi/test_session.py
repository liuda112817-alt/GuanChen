from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from guanchen_v2.agents.bazi.models import (
    BaziAgentInput,
    BaziAgentResult,
    BaziBirthDataPatch,
    InvalidBaziInput,
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


async def test_one_turn_completion(mock_runtime):
    session = BaziTaskSession(BaziAgentInput(question="事业", year=1998, month=7, day=21), mock_runtime)
    assert isinstance(await session.evaluate(), NeedUserInput)
    assert mock_runtime.run.call_count == 0

    res = await session.supplement(BaziBirthDataPatch(hour=14, minute=30, gender=Gender.MALE))
    assert isinstance(res, BaziAgentResult)
    assert mock_runtime.run.call_count == 1


async def test_multi_turn_completion_and_question_preservation(mock_runtime):
    session = BaziTaskSession(BaziAgentInput(question="感情怎样", year=1998), mock_runtime)
    res2 = await session.supplement(BaziBirthDataPatch(month=7, day=21))
    assert isinstance(res2, NeedUserInput)

    res3 = await session.supplement(BaziBirthDataPatch(hour=14, minute=30, gender=Gender.MALE))
    assert isinstance(res3, BaziAgentResult)

    ready = mock_runtime.run.call_args.args[0]
    assert ready.question == "感情怎样"
    assert ready.profile.year == 1998


async def test_field_override_correction(mock_runtime):
    session = BaziTaskSession(
        BaziAgentInput(question="事业", year=1998, month=7, day=21, hour=13), mock_runtime
    )
    await session.supplement(BaziBirthDataPatch(hour=14, minute=30, gender=Gender.MALE))
    assert mock_runtime.run.call_args.args[0].profile.hour == 14


async def test_invalid_patch_protects_state(mock_runtime):
    session = BaziTaskSession(BaziAgentInput(question="事业", year=1998, month=7), mock_runtime)
    with pytest.raises(ValidationError):
        await session.supplement(BaziBirthDataPatch(month=17))
    assert session._current_input.month == 7


async def test_invalid_date_combination_recovery(mock_runtime):
    session = BaziTaskSession(BaziAgentInput(question="算卦", year=2023, month=2), mock_runtime)
    assert isinstance(await session.supplement(BaziBirthDataPatch(day=29)), InvalidBaziInput)
    assert isinstance(await session.supplement(BaziBirthDataPatch(year=2024)), NeedUserInput)


async def test_completed_session_does_not_run_runtime_again(mock_runtime):
    session = BaziTaskSession(BaziAgentInput(question="事业", year=1998, month=7, day=21), mock_runtime)
    result1 = await session.supplement(BaziBirthDataPatch(hour=14, minute=30, gender=Gender.MALE))

    result2 = await session.evaluate()
    assert result2 is result1
    assert mock_runtime.run.call_count == 1

    with pytest.raises(RuntimeError, match="已完成"):
        await session.supplement(BaziBirthDataPatch(hour=15))
