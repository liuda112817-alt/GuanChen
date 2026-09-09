from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from guanchen_v2.models.bazi import BaziChart
from guanchen_v2.tools.bazi import build_calculate_bazi_tool


def test_calculate_bazi_tool_schema():
    """验证工具暴露给大模型的 Schema，确保必填项齐全，且没有泄漏排盘配置信息。"""
    mock_service = Mock()
    bazi_tool = build_calculate_bazi_tool(service=mock_service)

    # 1. 验证提供给模型的 Tool 名称
    assert bazi_tool.name == "calculate_bazi"

    schema = bazi_tool.args_schema.model_json_schema()
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # 2. 验证大模型必须要生成的必填字段
    expected_required = {"year", "month", "day", "hour", "minute", "gender"}
    for req_field in expected_required:
        assert req_field in properties
        assert req_field in required

    # 3. 验证存在但不强制生成的选填字段
    assert "birth_place_text" in properties
    assert "birth_place_text" not in required

    # 4. 严格断言：大模型绝不能看到或干预的系统级溯源及流派参数
    internal_fields = [
        "late_zi_sect",
        "yun_sect",
        "library",
        "library_version",
        "true_solar_time",
        "birth_place_affects_calculation",
    ]
    for internal in internal_fields:
        assert internal not in properties


def test_calculate_bazi_tool_successful_invocation():
    """验证 Tool 调用链路返回一个可序列化的 JSON 兼容字典对象。"""
    mock_service = Mock()
    mock_chart = Mock(spec=BaziChart)
    mock_chart.model_dump_json.return_value = '{"day_master": "甲"}'
    mock_service.calculate.return_value = mock_chart

    bazi_tool = build_calculate_bazi_tool(service=mock_service)

    assert bazi_tool.response_format == "content_and_artifact"

    # 验证底层函数确实返回了 (字符串，原实体对象) 元组
    content, artifact = bazi_tool.func(year=2000, month=1, day=1, hour=12, minute=0, gender="male")
    assert content == '{"day_master": "甲"}'
    assert artifact is mock_chart


def test_calculate_bazi_tool_missing_fields_rejected():
    """验证缺少字段时，LangChain 工具的 args_schema 会直接拦截，不会调用底层业务逻辑。"""
    mock_service = Mock()
    bazi_tool = build_calculate_bazi_tool(service=mock_service)

    with pytest.raises(ValidationError):
        # 故意缺失 hour 和 minute 等核心字段
        bazi_tool.invoke({"year": 2000, "month": 1, "day": 1, "gender": "male"})

    mock_service.calculate.assert_not_called()
