import pytest
from lunar_python import Solar

from guanchen_v2.bazi.adapter import LunarPythonBaziAdapter
from guanchen_v2.models.bazi import BirthProfile, Gender, LuckDirection
from tests.bazi.cases import BAZI_GOLDEN_CASES


@pytest.fixture
def adapter():
    return LunarPythonBaziAdapter()


@pytest.mark.parametrize("case", BAZI_GOLDEN_CASES, ids=lambda c: c.case_id)
def test_golden_fixtures(adapter, case):
    """验证所有核心签名，确保底层库升级时 GuanChen 能发现行为漂移。"""
    chart = adapter.calculate(case.profile)

    assert chart.year_pillar.gan_zhi.gan_zhi == case.expected_pillars[0]
    assert chart.month_pillar.gan_zhi.gan_zhi == case.expected_pillars[1]
    assert chart.day_pillar.gan_zhi.gan_zhi == case.expected_pillars[2]
    assert chart.hour_pillar.gan_zhi.gan_zhi == case.expected_pillars[3]
    assert chart.day_master.value == case.expected_day_master

    if case.expected_start_offset:
        y, m, d = case.expected_start_offset
        assert chart.da_yun.start_offset.years == y
        assert chart.da_yun.start_offset.months == m
        assert chart.da_yun.start_offset.days == d

    if case.expected_start_at:
        assert chart.da_yun.start_at == case.expected_start_at

    if case.expected_direction:
        assert chart.da_yun.direction == case.expected_direction


def test_full_mapping_f01(adapter):
    """对 F01 案例执行极其完整的全量结构断言。"""
    profile = BirthProfile(year=2005, month=12, day=23, hour=8, minute=37, gender=Gender.MALE)
    chart = adapter.calculate(profile)

    # 1. 四柱干支与十神映射校验
    assert chart.year_pillar.stem_ten_god.value == "偏财"
    assert chart.month_pillar.stem_ten_god.value == "正印"
    assert chart.day_pillar.stem_ten_god is None  # 日主自身无十神
    assert chart.hour_pillar.stem_ten_god.value == "伤官"

    # 2. 每柱 hidden_stems 的 stem + ten_god 极其严格的校验
    # 年柱 (酉)
    assert [(h.stem.value, h.ten_god.value) for h in chart.year_pillar.hidden_stems] == [("辛", "比肩")]
    # 月柱 (子)
    assert [(h.stem.value, h.ten_god.value) for h in chart.month_pillar.hidden_stems] == [("癸", "食神")]
    # 日柱 (巳) -> 校验 lunar_python 1.4.8 Issue #28 锁定行为：丙、庚、戊
    assert [(h.stem.value, h.ten_god.value) for h in chart.day_pillar.hidden_stems] == [
        ("丙", "正官"),
        ("庚", "劫财"),
        ("戊", "正印"),
    ]
    # 时柱 (辰)
    assert [(h.stem.value, h.ten_god.value) for h in chart.hour_pillar.hidden_stems] == [
        ("戊", "正印"),
        ("乙", "偏财"),
        ("癸", "食神"),
    ]

    # 3. 大运起步与第一条 DaYun 细节校验
    assert chart.da_yun.direction == LuckDirection.BACKWARD
    assert chart.da_yun.start_offset.years is not None
    assert chart.da_yun.start_at is not None

    first_da_yun = chart.da_yun.periods[0]
    assert first_da_yun.index == 1
    assert first_da_yun.start_year > 2005
    assert first_da_yun.start_age > 0
    assert first_da_yun.gan_zhi.gan_zhi == "丁亥"  # 戊子退一位

    # 4. calculation_method 全量校验
    method = chart.calculation_method
    assert method.library == "lunar_python"
    assert isinstance(method.library_version, str)
    assert method.late_zi_sect == 2
    assert method.yun_sect == 1
    assert method.true_solar_time is False
    assert method.birth_place_affects_calculation is False


def test_male_female_difference(adapter):
    """F06/F07 对照：验证同一个时刻的不同性别仅影响大运，绝不能污染四柱。"""
    male_prof = BirthProfile(year=2024, month=5, day=1, hour=12, minute=0, gender=Gender.MALE)
    female_prof = BirthProfile(year=2024, month=5, day=1, hour=12, minute=0, gender=Gender.FEMALE)

    male_chart = adapter.calculate(male_prof)
    female_chart = adapter.calculate(female_prof)

    assert male_chart.year_pillar.gan_zhi.gan_zhi == female_chart.year_pillar.gan_zhi.gan_zhi
    assert male_chart.day_master == female_chart.day_master

    assert male_chart.da_yun.direction != female_chart.da_yun.direction
    assert male_chart.da_yun.start_at != female_chart.da_yun.start_at


def test_birth_place_non_effect(adapter):
    """防御：验证出生地文本不参与运算，防止暗中接入真实经纬度修正。"""
    prof_none = BirthProfile(year=1990, month=1, day=1, hour=12, minute=0, gender=Gender.MALE)
    prof_chengdu = BirthProfile(
        year=1990, month=1, day=1, hour=12, minute=0, gender=Gender.MALE, birth_place_text="成都"
    )

    chart_a = adapter.calculate(prof_none)
    chart_b = adapter.calculate(prof_chengdu)

    assert chart_a.model_dump() == chart_b.model_dump()


def test_differential_mapping(adapter):
    """Differential Test：确保 Adapter 的值就是库原始吐出的值，没有串台。"""
    profile = BirthProfile(year=1998, month=7, day=21, hour=14, minute=30, gender=Gender.MALE)

    solar = Solar.fromYmdHms(1998, 7, 21, 14, 30, 0)
    raw_eight = solar.getLunar().getEightChar()
    raw_eight.setSect(2)

    chart = adapter.calculate(profile)
    assert chart.year_pillar.gan_zhi.stem.value == raw_eight.getYearGan()
    assert chart.day_master.value == raw_eight.getDayGan()
