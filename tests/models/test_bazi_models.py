from datetime import datetime

import pytest
from pydantic import ValidationError

from guanchen_v2.models.bazi import (
    BaziCalculationMethod,
    BaziChart,
    BirthProfile,
    DaYunPeriod,
    DaYunResult,
    EarthlyBranch,
    FiveElement,
    GanZhi,
    Gender,
    HeavenlyStem,
    HiddenStem,
    LuckDirection,
    LuckStartOffset,
    Pillar,
    TenGod,
)


def test_valid_birth_profile():
    profile = BirthProfile(
        year=2024,
        month=2,
        day=29,
        hour=14,
        minute=30,
        gender=Gender.MALE,
        birth_place_text="  成都  ",
    )
    assert profile.year == 2024
    assert profile.gender == Gender.MALE
    assert profile.birth_place_text == "成都"  # 验证清洗


def test_birth_profile_empty_place():
    profile = BirthProfile(year=2024, month=1, day=1, hour=12, minute=0, gender=Gender.MALE, birth_place_text="   ")
    assert profile.birth_place_text is None  # 空白字符串转为 None


def test_impossible_calendar_date():
    with pytest.raises(ValidationError, match="非法的日期.*组合"):
        BirthProfile(year=2023, month=2, day=29, hour=12, minute=0, gender=Gender.FEMALE)

    with pytest.raises(ValidationError, match="非法的日期.*组合"):
        BirthProfile(year=2025, month=2, day=30, hour=12, minute=0, gender=Gender.MALE)


def test_illegal_calculation_method():
    # 验证严格禁用的排盘规则会被拒绝
    with pytest.raises(ValidationError):
        BaziCalculationMethod(
            library_version="1.0",
            late_zi_sect=1,
            yun_sect=1,
            true_solar_time=True,  # Stage 2 锁定禁止
        )


def test_empty_lists_rejected():
    gz = GanZhi(stem=HeavenlyStem.JIA, branch=EarthlyBranch.ZI)

    with pytest.raises(ValidationError):
        Pillar(gan_zhi=gz, stem_ten_god=None, hidden_stems=[])  # 必须包含藏干

    with pytest.raises(ValidationError):
        DaYunResult(
            direction=LuckDirection.FORWARD,
            start_offset=LuckStartOffset(years=0, months=0, days=0, hours=0),
            start_at=datetime(2030, 1, 1, 0, 0),
            periods=[],  # 必须包含大运步
        )


def test_derived_fields_and_invariants():
    # 验证甲子干支正确派生出五行为：水、木
    gz = GanZhi(stem=HeavenlyStem.JIA, branch=EarthlyBranch.ZI)
    assert gz.gan_zhi == "甲子"

    hidden = HiddenStem(stem=HeavenlyStem.GUI, ten_god=TenGod.ZHENG_YIN)
    assert hidden.element == FiveElement.WATER

    pillar = Pillar(gan_zhi=gz, stem_ten_god=None, hidden_stems=[hidden])
    assert pillar.stem_element == FiveElement.WOOD
    assert pillar.branch_element == FiveElement.WATER

    dummy_method = BaziCalculationMethod(library_version="1.0", late_zi_sect=2, yun_sect=1)
    dummy_dayun = DaYunResult(
        direction=LuckDirection.FORWARD,
        start_offset=LuckStartOffset(years=0, months=0, days=0, hours=0),
        start_at=datetime(2030, 1, 1, 0, 0),
        periods=[DaYunPeriod(index=1, start_year=2025, start_age=1, gan_zhi=gz)],
    )

    chart = BaziChart(
        year_pillar=pillar,
        month_pillar=pillar,
        day_pillar=pillar,
        hour_pillar=pillar,
        da_yun=dummy_dayun,
        calculation_method=dummy_method,
    )
    # 日主自动从日柱天干甲读取
    assert chart.day_master == HeavenlyStem.JIA
