import pytest
from pydantic import ValidationError

from guanchen_v2.config.settings import (
    DatabaseSettings,
    Settings,
)


def test_settings_instantiation_with_valid_kwargs():
    settings = Settings(
        _env_file=None,
        deepseek_api_key="test-secret-key",
        deepseek_model="deepseek-chat",
    )

    assert settings.deepseek_api_key.get_secret_value() == "test-secret-key"

    assert settings.deepseek_model == "deepseek-chat"

    assert settings.app_env == "development"


def test_settings_missing_required_fields_fails(
    monkeypatch,
):
    monkeypatch.delenv(
        "GUANCHEN_DEEPSEEK_API_KEY",
        raising=False,
    )

    monkeypatch.delenv(
        "GUANCHEN_DEEPSEEK_MODEL",
        raising=False,
    )

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_type_coercion(
    monkeypatch,
):
    monkeypatch.setenv(
        "GUANCHEN_DEEPSEEK_API_KEY",
        "test-key",
    )

    monkeypatch.setenv(
        "GUANCHEN_DEEPSEEK_MODEL",
        "deepseek-chat",
    )

    monkeypatch.setenv(
        "GUANCHEN_LLM_MAX_RETRIES",
        "4",
    )

    settings = Settings(_env_file=None)

    assert settings.llm_max_retries == 4

    assert isinstance(
        settings.llm_max_retries,
        int,
    )


def test_settings_invalid_temperature_fails():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            deepseek_api_key="test",
            deepseek_model="test",
            llm_temperature=3.0,
        )


def test_settings_invalid_retry_fails():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            deepseek_api_key="test",
            deepseek_model="test",
            llm_max_retries=-1,
        )


def test_settings_empty_api_key_fails():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            deepseek_api_key="",
            deepseek_model="deepseek-chat",
        )


def test_settings_invalid_log_level_fails():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            deepseek_api_key="test-key",
            deepseek_model="test-model",
            log_level="POTATO",
        )


def test_database_settings_does_not_require_llm_credentials(
    monkeypatch,
):
    monkeypatch.delenv(
        "GUANCHEN_DEEPSEEK_API_KEY",
        raising=False,
    )

    monkeypatch.delenv(
        "GUANCHEN_DEEPSEEK_MODEL",
        raising=False,
    )

    settings = DatabaseSettings(_env_file=None)

    assert settings.database_url == ("postgresql+asyncpg://postgres:postgres@localhost:5432/guanchen")


def test_database_settings_reads_database_env_only(
    monkeypatch,
):
    monkeypatch.delenv(
        "GUANCHEN_DEEPSEEK_API_KEY",
        raising=False,
    )

    monkeypatch.delenv(
        "GUANCHEN_DEEPSEEK_MODEL",
        raising=False,
    )

    monkeypatch.setenv(
        "GUANCHEN_DATABASE_URL",
        ("postgresql+asyncpg://user:pass@db:5432/test_db"),
    )

    settings = DatabaseSettings(_env_file=None)

    assert settings.database_url == ("postgresql+asyncpg://user:pass@db:5432/test_db")
