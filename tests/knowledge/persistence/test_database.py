import os
import subprocess
import sys
from unittest.mock import MagicMock

import pytest

import guanchen_v2.knowledge.persistence.database as database
from guanchen_v2.config.settings import (
    DatabaseSettings,
)
from guanchen_v2.knowledge.errors import (
    KnowledgePersistenceError,
)


def test_database_settings_are_independent_from_llm():
    settings = DatabaseSettings(
        _env_file=None,
        database_url=("postgresql+asyncpg://postgres:postgres@localhost:5432/test"),
    )

    assert settings.database_url.endswith("/test")


def test_database_module_import_has_no_llm_config_dependency(
    tmp_path,
):
    """
    在一个没有 DeepSeek credentials 的独立 Python
    进程中 import database 模块必须成功。

    该测试直接锁住 CODE-10 的原始故障。
    """
    env = os.environ.copy()

    env.pop(
        "GUANCHEN_DEEPSEEK_API_KEY",
        None,
    )

    env.pop(
        "GUANCHEN_DEEPSEEK_MODEL",
        None,
    )

    command = "import guanchen_v2.knowledge.persistence.database as db; assert db._default_runtime is None"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            command,
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_database_runtime_is_created_lazily(
    monkeypatch,
):
    fake_runtime = MagicMock()

    fake_settings = DatabaseSettings(
        _env_file=None,
        database_url=("postgresql+asyncpg://postgres:postgres@localhost:5432/lazy_test"),
    )

    create_mock = MagicMock(return_value=fake_runtime)

    monkeypatch.setattr(
        database,
        "_default_runtime",
        None,
    )

    monkeypatch.setattr(
        database,
        "create_database_runtime",
        create_mock,
    )

    runtime = database.get_database_runtime(settings=fake_settings)

    assert runtime is fake_runtime

    create_mock.assert_called_once_with(database_url=(fake_settings.database_url))


def test_database_runtime_is_reused(
    monkeypatch,
):
    fake_runtime = MagicMock()

    monkeypatch.setattr(
        database,
        "_default_runtime",
        fake_runtime,
    )

    create_mock = MagicMock()

    monkeypatch.setattr(
        database,
        "create_database_runtime",
        create_mock,
    )

    first = database.get_database_runtime()

    second = database.get_database_runtime()

    assert first is fake_runtime
    assert second is fake_runtime

    create_mock.assert_not_called()


def test_blank_database_url_is_rejected():
    with pytest.raises(
        KnowledgePersistenceError,
        match="数据库连接地址不能为空",
    ):
        database.DatabaseRuntime(database_url="   ")
