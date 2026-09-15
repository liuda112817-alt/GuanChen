from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

LogLevel = Literal[
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
]


class DatabaseSettings(BaseSettings):
    """
    GuanChen 数据库独立配置。

    该配置可以在完全没有 LLM credentials 的情况下独立创建，
    供：
    - ingestion scripts
    - retrieval scripts
    - database maintenance
    - integration tests
    使用。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="GUANCHEN_",
        extra="ignore",
    )

    database_url: str = Field(
        default=("postgresql+asyncpg://postgres:postgres@localhost:5432/guanchen"),
        min_length=1,
    )


class Settings(DatabaseSettings):
    """
    GuanChen 完整应用配置。

    Application Runtime 需要 LLM 配置；
    纯数据库基础设施不应依赖该类型。
    """

    app_env: str = "development"

    log_level: LogLevel = "INFO"

    deepseek_api_key: SecretStr = Field(min_length=1)

    deepseek_model: str = Field(min_length=1)

    llm_temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
    )

    llm_timeout_seconds: float = Field(
        default=30.0,
        gt=0.0,
    )

    llm_max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
    )
