from datetime import date

from pydantic import ValidationError

from guanchen_v2.agents.bazi.models import (
    BaziAgentInput,
    InvalidBaziInput,
    MissingField,
    NeedUserInput,
    ReadyForBazi,
)
from guanchen_v2.models.bazi import (
    BirthProfile,
)


def check_bazi_requirements(
    input_data: BaziAgentInput,
) -> ReadyForBazi | NeedUserInput | InvalidBaziInput:
    """
    Bazi 排盘前置 Gatekeeper。

    职责：
    - 优先识别已经确定的非法年月日组合；
    - 检查排盘所需字段完整性；
    - 构建严格 BirthProfile；
    - 不向用户暴露 Python / Pydantic 底层异常原文。
    """

    if input_data.year is not None and input_data.month is not None and input_data.day is not None:
        try:
            date(
                input_data.year,
                input_data.month,
                input_data.day,
            )
        except ValueError:
            return InvalidBaziInput(
                original_question=(input_data.question),
                reason=("非法的日期组合，请检查年月日后重新提供。"),
            )

    missing: list[MissingField] = []

    if input_data.year is None:
        missing.append(MissingField.YEAR)

    if input_data.month is None:
        missing.append(MissingField.MONTH)

    if input_data.day is None:
        missing.append(MissingField.DAY)

    if input_data.hour is None:
        missing.append(MissingField.HOUR)

    if input_data.minute is None:
        missing.append(MissingField.MINUTE)

    if input_data.gender is None:
        missing.append(MissingField.GENDER)

    if missing:
        return NeedUserInput(
            original_question=(input_data.question),
            missing_fields=missing,
        )

    try:
        profile = BirthProfile(
            year=input_data.year,
            month=input_data.month,
            day=input_data.day,
            hour=input_data.hour,
            minute=input_data.minute,
            gender=input_data.gender,
            birth_place_text=(input_data.birth_place_text),
        )

    except ValidationError:
        return InvalidBaziInput(
            original_question=(input_data.question),
            reason=("出生资料不符合排盘输入约束，请检查后重新提供。"),
        )

    return ReadyForBazi(
        question=input_data.question,
        profile=profile,
    )
