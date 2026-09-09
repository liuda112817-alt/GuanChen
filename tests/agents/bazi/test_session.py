from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from guanchen_v2.agents.bazi.models import (
    BaziAgentInput,
    BaziAgentResult,
    BaziBirthDataPatch,
    InvalidBaziInput,
    NeedUserInput,
    ReadyForBazi,
)
from guanchen_v2.agents.bazi.session import BaziTaskSession
from guanchen_v2.models.bazi import Gender


@pytest.fixture
def mock_runtime():
    """造一个假 Runtime 防止真正调取 LLM"""
    runtime = Mock()
    runtime.run.return_value = Mock(spec=BaziAgentResult)
    return runtime


def test_one_turn_completion(mock_runtime):
    """Case 1: 一次补齐缺失的所有资料"""
    session = BaziTaskSession(
        BaziAgentInput(question="事业", year=1998, month=7, day=21), mock_runtime
    )

    assert isinstance(session.evaluate(), NeedUserInput)
    assert mock_runtime.run.call_count == 0  # 缺资料绝不能调用

    patch = BaziBirthDataPatch(hour=14, minute=30, gender=Gender.MALE)
    res = session.supplement(patch)

    assert isinstance(res, BaziAgentResult)
    assert mock_runtime.run.call_count == 1  # 补齐后调用，且仅调用一次


def test_multi_turn_completion_and_question_preservation(mock_runtime):
    """Case 2: 拆分多轮补充，且确保第一轮的原始问题一直没被弄丢"""
    session = BaziTaskSession(BaziAgentInput(question="我的感情怎样", year=1998), mock_runtime)

    # Turn 2: 补月日
    res2 = session.supplement(BaziBirthDataPatch(month=7, day=21))
    assert isinstance(res2, NeedUserInput)
    assert res2.original_question == "我的感情怎样"

    # Turn 3: 补时分男
    res3 = session.supplement(BaziBirthDataPatch(hour=14, minute=30, gender=Gender.MALE))
    assert isinstance(res3, BaziAgentResult)
    assert mock_runtime.run.call_count == 1

    ready = mock_runtime.run.call_args.args[0]
    assert isinstance(ready, ReadyForBazi)
    assert ready.question == "我的感情怎样"
    assert ready.profile.year == 1998
    assert ready.profile.month == 7
    assert ready.profile.day == 21
    assert ready.profile.hour == 14
    assert ready.profile.minute == 30
    assert ready.profile.gender == Gender.MALE


def test_field_override_correction(mock_runtime):
    """Case 3: 用户自己纠错，提供新值会无情覆盖旧值"""
    session = BaziTaskSession(
        BaziAgentInput(question="问事业", year=1998, month=7, day=21, hour=13), mock_runtime
    )

    # 用户发现时辰错了，发补丁：hour=14
    session.supplement(BaziBirthDataPatch(hour=14, minute=30, gender=Gender.MALE))

    # 我们拦截被送往 runtime.run 的那个入参，看看 hour 到底有没有变成 14
    ready_for_bazi = mock_runtime.run.call_args.args[0]
    assert ready_for_bazi.profile.hour == 14


def test_invalid_patch_protects_state(mock_runtime):
    """Case 4: 恶意的/非法的单字段 Patch 会被 Pydantic 直接阻截，原状态不受损"""
    session = BaziTaskSession(BaziAgentInput(question="事业", year=1998, month=7), mock_runtime)

    with pytest.raises(ValidationError):
        # 用户输了一个不存在的月份，直接在 Patch 阶段就炸了
        session.supplement(BaziBirthDataPatch(month=17))

    # 我们验证原 Session 的月份仍然好好的
    assert session._current_input.month == 7


def test_invalid_date_combination_recovery(mock_runtime):
    """Case 5: 合法字段拼成了非法的组合(2023-02-29)，返回需要纠正，而后补丁依然能挽回"""
    session = BaziTaskSession(BaziAgentInput(question="算卦", year=2023, month=2), mock_runtime)

    res = session.supplement(BaziBirthDataPatch(day=29))
    assert isinstance(res, InvalidBaziInput)

    # 挽回补丁
    res_fixed = session.supplement(BaziBirthDataPatch(year=2024))
    assert isinstance(
        res_fixed, NeedUserInput
    )  # 虽然还缺时分秒，但已经越过了 InvalidBaziInput 边界


def test_completed_session_does_not_run_runtime_again(mock_runtime):
    """Case 6: 任务完成后，反复 evaluate 或是试图再次打补丁，都绝不能导致 Runtime 重复调用"""
    session = BaziTaskSession(
        BaziAgentInput(question="事业", year=1998, month=7, day=21), mock_runtime
    )

    # 补齐资料，完成任务
    result1 = session.supplement(BaziBirthDataPatch(hour=14, minute=30, gender=Gender.MALE))
    assert isinstance(result1, BaziAgentResult)
    assert mock_runtime.run.call_count == 1

    # 恶意反复调用 evaluate，验证其具有严格的幂等性
    result2 = session.evaluate()
    result3 = session.evaluate()

    assert result2 is result1
    assert result3 is result1
    assert mock_runtime.run.call_count == 1  # 依然死死锁在 1 次，没有浪费 LLM 预算

    # 恶意尝试在完成状态下继续塞入补丁
    with pytest.raises(RuntimeError, match="任务已完成。"):
        session.supplement(BaziBirthDataPatch(hour=15))

    assert mock_runtime.run.call_count == 1  # 绝对不会变成 2 次
