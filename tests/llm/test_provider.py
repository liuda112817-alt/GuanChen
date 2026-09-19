from unittest.mock import Mock

import guanchen_v2.llm.provider
from guanchen_v2.llm.provider import build_chat_model


def test_build_chat_model_contract(monkeypatch):
    """
    验证基础模型工厂是否严格遵循 Stage 1 的构造契约。
    重点防御底层重试泄露 (max_retries=0) 和 thinking mode 禁用。
    """
    mock_chat_deepseek = Mock()
    monkeypatch.setattr(guanchen_v2.llm.provider, "ChatDeepSeek", mock_chat_deepseek)

    # 使用 Mock 对象彻底隔离 Pydantic Settings 对 .env 文件的磁盘读取
    mock_settings = Mock()
    mock_settings.deepseek_model = "deepseek-test"
    # llm_api_key 是 SecretStr，因此我们要 mock 它的 get_secret_value 方法
    mock_settings.deepseek_api_key.get_secret_value.return_value = "sk-fake-key"
    mock_settings.llm_temperature = 0.8
    mock_settings.llm_timeout_seconds = 45.0

    # 调用工厂
    build_chat_model(mock_settings)

    mock_chat_deepseek.assert_called_once()
    call_kwargs = mock_chat_deepseek.call_args.kwargs

    # 验证常规透传
    assert call_kwargs["model"] == "deepseek-test"
    assert call_kwargs["api_key"] == "sk-fake-key"
    assert call_kwargs["temperature"] == 0.8
    assert call_kwargs["timeout"] == 45.0

    # 验证底线契约
    assert call_kwargs["max_retries"] == 0
    assert call_kwargs["extra_body"].get("thinking", {}).get("type") == "disabled"


def test_build_chat_model_can_explicitly_enable_reasoning(monkeypatch):
    mock_chat_deepseek = Mock()
    monkeypatch.setattr(guanchen_v2.llm.provider, "ChatDeepSeek", mock_chat_deepseek)

    mock_settings = Mock()
    mock_settings.deepseek_model = "deepseek-flash"
    mock_settings.deepseek_api_key.get_secret_value.return_value = "sk-fake-key"
    mock_settings.llm_temperature = 0.2
    mock_settings.llm_timeout_seconds = 30.0
    mock_settings.deepseek_thinking_mode = "enabled"
    mock_settings.deepseek_reasoning_effort = "high"

    build_chat_model(mock_settings)

    call_kwargs = mock_chat_deepseek.call_args.kwargs
    assert call_kwargs["extra_body"]["thinking"]["type"] == "enabled"
    assert call_kwargs["reasoning_effort"] == "high"
