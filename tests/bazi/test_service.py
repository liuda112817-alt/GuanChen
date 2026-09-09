from unittest.mock import Mock

import pytest

from guanchen_v2.bazi.exceptions import BaziAdapterError, BaziCalculationError
from guanchen_v2.bazi.service import BaziService
from guanchen_v2.models.bazi import BirthProfile, Gender


def test_bazi_service_happy_path():
    """验证服务正常代理到 Adapter，并正确返回数据。"""
    mock_adapter = Mock()
    mock_chart = Mock()
    mock_adapter.calculate.return_value = mock_chart

    service = BaziService(adapter=mock_adapter)
    profile = BirthProfile(year=2000, month=1, day=1, hour=12, minute=0, gender=Gender.MALE)

    result = service.calculate(profile)
    assert result is mock_chart
    mock_adapter.calculate.assert_called_once_with(profile=profile)


def test_bazi_service_error_translation():
    """验证服务将 Adapter 异常正确地翻译为 Calculation 异常，并保留根因。"""
    mock_adapter = Mock()
    mock_adapter.calculate.side_effect = BaziAdapterError("Simulated Adapter Error")

    service = BaziService(adapter=mock_adapter)
    profile = BirthProfile(year=2000, month=1, day=1, hour=12, minute=0, gender=Gender.MALE)

    with pytest.raises(BaziCalculationError) as exc_info:
        service.calculate(profile)

    assert str(exc_info.value) == "八字排盘业务执行失败。"
    assert isinstance(exc_info.value.__cause__, BaziAdapterError)
