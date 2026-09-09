from importlib.metadata import version

import pytest

from guanchen_v2.bazi.adapter import LunarPythonBaziAdapter
from guanchen_v2.bazi.exceptions import BaziAdapterError
from guanchen_v2.models.bazi import BirthProfile, Gender


@pytest.fixture
def adapter():
    return LunarPythonBaziAdapter()


def test_adapter_happy_path(adapter):
    """Case 1: 验证普通 BirthProfile 能正常走通整条排盘映射链。"""
    profile = BirthProfile(year=1998, month=7, day=21, hour=14, minute=30, gender=Gender.MALE)
    chart = adapter.calculate(profile)

    assert chart.year_pillar.gan_zhi.gan_zhi == "戊寅"
    # 1998年7月21日的日柱是“己卯”，所以日干（日主）应该是“己”
    assert chart.day_master.value == "己"
    # DaYun mapping: 确保 index 0 已被抛弃，第一个运是 index 1
    assert chart.da_yun.periods[0].index == 1


def test_calculation_method_provenance(adapter):
    """Case 2: 验证产生的 calculation_method 完全符合 Stage 2.3 的硬编码契约。"""
    profile = BirthProfile(year=1998, month=7, day=21, hour=14, minute=30, gender=Gender.MALE)
    method = adapter.calculate(profile).calculation_method

    assert method.library == "lunar_python"
    assert method.late_zi_sect == 2
    assert method.yun_sect == 1
    assert method.library_version == version("lunar_python")
    assert method.true_solar_time is False


def test_day_stem_ten_god_is_none(adapter):
    """Case 3: 验证日柱十神按要求置空。"""
    profile = BirthProfile(year=1998, month=7, day=21, hour=14, minute=30, gender=Gender.MALE)
    chart = adapter.calculate(profile)

    assert chart.year_pillar.stem_ten_god is not None
    assert chart.day_pillar.stem_ten_god is None  # 日主自身不需要十神


def test_gender_mapping_female(adapter):
    """Case 4: 验证女性排盘同样可以正确执行。"""
    profile = BirthProfile(year=2000, month=1, day=1, hour=0, minute=0, gender=Gender.FEMALE)
    chart = adapter.calculate(profile)
    assert chart is not None


def test_adapter_error_translation(adapter, monkeypatch):
    """Case 5: 验证第三方崩溃时能正确封装为 BaziAdapterError。"""

    def mock_get_eight_char(*args, **kwargs):
        raise ValueError("Simulated third-party crash")

    # 猴子补丁破坏底层库调用
    import lunar_python

    monkeypatch.setattr(lunar_python.Lunar, "getEightChar", mock_get_eight_char)

    profile = BirthProfile(year=1998, month=7, day=21, hour=14, minute=30, gender=Gender.MALE)
    with pytest.raises(BaziAdapterError, match="lunar_python 排盘或字段映射失败") as exc_info:
        adapter.calculate(profile)

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert str(exc_info.value.__cause__) == "Simulated third-party crash"


def test_adapter_hidden_stems_mapping_drift(adapter, monkeypatch):
    """Case 6: 验证藏干与十神数量不一致时（API 漂移），Adapter 会拒绝静默截断并抛出异常。"""
    import lunar_python

    # 猴子补丁：强行修改类的底层方法，让年柱的地支十神永远只返回 1 个元素
    monkeypatch.setattr(lunar_python.EightChar, "getYearShiShenZhi", lambda self: ["正财"])

    # 1998年是戊寅年，寅（YIN）的真实藏干有 3 个（戊、丙、甲）。
    # 此时 zip(strict=True) 会因为 3 != 1 抛出 ValueError，并被 Adapter 捕获转化为 BaziAdapterError
    profile = BirthProfile(year=1998, month=7, day=21, hour=14, minute=30, gender=Gender.MALE)

    with pytest.raises(BaziAdapterError, match="lunar_python 排盘或字段映射失败。"):
        adapter.calculate(profile)
