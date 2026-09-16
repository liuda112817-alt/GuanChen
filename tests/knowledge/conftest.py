import pytest

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/guanchen_test"


@pytest.fixture(autouse=True)
def isolate_knowledge_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Knowledge tests 默认指向独立测试数据库。

    使用 function-scoped monkeypatch，避免在 pytest collection 阶段
    修改进程级环境变量并污染 tests/knowledge 之外的测试。
    """
    monkeypatch.setenv(
        "GUANCHEN_DATABASE_URL",
        TEST_DATABASE_URL,
    )
