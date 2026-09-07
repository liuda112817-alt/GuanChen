import pytest
from pydantic import ValidationError

from guanchen_v2.config.settings import Settings


def test_settings_instantiation_with_valid_kwargs():
    """Case 1: 显式参数可以创建 Settings"""
    settings = Settings(
        _env_file=None,  # 隔离真实 .env，避免测试意外依赖本地配置
        deepseek_api_key="test-secret-key",
        deepseek_model="deepseek-chat",
    )
    # 验证 SecretStr 的正确提取
    assert settings.deepseek_api_key.get_secret_value() == "test-secret-key"
    assert settings.deepseek_model == "deepseek-chat"
    assert settings.app_env == "development"


def test_settings_missing_required_fields_fails(monkeypatch):
    """Case 2: 缺 required API Key / model 时失败"""
    monkeypatch.delenv("GUANCHEN_DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("GUANCHEN_DEEPSEEK_MODEL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_type_coercion(monkeypatch):
    """Case 3: Environment String 能转成数值类型"""
    monkeypatch.setenv("GUANCHEN_DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("GUANCHEN_DEEPSEEK_MODEL", "deepseek-chat")
    monkeypatch.setenv("GUANCHEN_LLM_MAX_RETRIES", "4")

    settings = Settings(_env_file=None)
    assert settings.llm_max_retries == 4
    assert isinstance(settings.llm_max_retries, int)


def test_settings_invalid_temperature_fails():
    """Case 4: 非法 temperature 被拒绝"""
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            deepseek_api_key="test",
            deepseek_model="test",
            llm_temperature=3.0,  # 超出 le=2 限制
        )


def test_settings_invalid_retry_fails():
    """Case 5: 非法 retry 被拒绝"""
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            deepseek_api_key="test",
            deepseek_model="test",
            llm_max_retries=-1,  # 超出 ge=0 限制
        )


def test_settings_empty_api_key_fails():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            deepseek_api_key="",
            deepseek_model="deepseek-chat",
        )


def test_settings_invalid_log_level_fails():
    """验证：非法的日志等级会被 Pydantic 拒绝（Literal 约束）。"""
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            deepseek_api_key="test-key",
            deepseek_model="test-model",
            log_level="POTATO",  # 不在预设的 Enum 范围内
        )
