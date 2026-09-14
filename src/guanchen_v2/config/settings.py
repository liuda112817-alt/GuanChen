from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="GUANCHEN_", extra="ignore"
    )

    app_env: str = "development"
    log_level: LogLevel = "INFO"

    deepseek_api_key: SecretStr = Field(min_length=1)
    deepseek_model: str = Field(min_length=1)

    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_timeout_seconds: float = Field(default=30.0, gt=0.0)
    llm_max_retries: int = Field(default=2, ge=0, le=5)

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/guanchen"
