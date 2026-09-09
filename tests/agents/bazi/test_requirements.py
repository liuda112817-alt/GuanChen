import pytest
from pydantic import ValidationError

from guanchen_v2.agents.bazi.models import (
    BaziAgentInput,
    InvalidBaziInput,
    MissingField,
    NeedUserInput,
    ReadyForBazi,
)
from guanchen_v2.agents.bazi.requirements import check_bazi_requirements
from guanchen_v2.models.bazi import Gender


def test_complete_input_ready_preserves_question():
    """Case 1: 资料齐全，不仅得到 BirthProfile，原问题也一字不落地保留并清洗。"""
    inp = BaziAgentInput(
        question="  测事业  ", year=1998, month=7, day=21, hour=14, minute=30, gender=Gender.MALE
    )
    result = check_bazi_requirements(inp)

    assert isinstance(result, ReadyForBazi)
    assert result.question == "测事业"
    assert result.profile.year == 1998


def test_missing_time_needs_input_preserves_question():
    """Case 2: 缺时辰时分，触发 NeedUserInput，同时记住用户想问什么。"""
    inp = BaziAgentInput(question="运势如何？", year=1998, month=7, day=21, gender=Gender.MALE)
    result = check_bazi_requirements(inp)

    assert isinstance(result, NeedUserInput)
    assert result.original_question == "运势如何？"
    assert result.missing_fields == [MissingField.HOUR, MissingField.MINUTE]


def test_missing_gender_needs_input():
    """Case 3: 缺少性别，触发 NeedUserInput。绝对不调用 LLM 去猜。"""
    inp = BaziAgentInput(question="测财运", year=1998, month=7, day=21, hour=14, minute=30)
    result = check_bazi_requirements(inp)

    assert isinstance(result, NeedUserInput)
    assert result.missing_fields == [MissingField.GENDER]


def test_multiple_missing_fields_stable_order():
    """Case 4: 大面积缺失资料，确保系统返回的 missing_fields 顺序是稳定的。"""
    inp = BaziAgentInput(question="我适合做什么？", year=2000)
    result = check_bazi_requirements(inp)

    assert isinstance(result, NeedUserInput)
    assert result.missing_fields == [
        MissingField.MONTH,
        MissingField.DAY,
        MissingField.HOUR,
        MissingField.MINUTE,
        MissingField.GENDER,
    ]


def test_invalid_calendar_date_preserves_question():
    """Case 5: 非法的跨字段日期组合，拦截器立刻阻断并报 Invalid。已知错误优先于缺失信息。"""
    inp = BaziAgentInput(question="算一卦", year=2023, month=2, day=29)
    result = check_bazi_requirements(inp)

    assert isinstance(result, InvalidBaziInput)
    assert result.original_question == "算一卦"
    assert "非法的日期组合" in result.reason


def test_empty_question_rejected():
    """Case 6: 最基础的输入 Schema 校验，拦截空白问题。"""
    with pytest.raises(ValidationError, match="question 不能为空或纯空格"):
        BaziAgentInput(question="   ", year=1998, month=1, day=1)


def test_known_single_field_invalid_rejected():
    """Case 7: 单字段自身的硬伤（如 year=0）直接在模型层被拒收，不会流入 NeedUserInput。"""
    with pytest.raises(ValidationError):
        BaziAgentInput(question="测事业", year=0, month=1, day=1)
