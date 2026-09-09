from unittest.mock import Mock

import httpx
import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from openai import APIStatusError
from pydantic import BaseModel

import guanchen_v2.llm.client
from guanchen_v2.llm.client import LLMClient
from guanchen_v2.llm.exceptions import (
    LLMEmptyResponseError,
    LLMProviderError,
    LLMRetryExhaustedError,
    LLMStructuredOutputError,
)


class DummySchema(BaseModel):
    field: str


@pytest.fixture
def fake_model():
    return Mock(spec=BaseChatModel)


@pytest.fixture
def llm_client(fake_model):
    # 关闭 jitter 以保证测试执行极速且 deterministic
    return LLMClient(model=fake_model, max_retries=2, retry_wait_exponential_jitter=False)


def test_text_happy_path(llm_client, fake_model):
    """Case 1: text happy path"""
    fake_model.invoke.return_value = AIMessage(content="ok")

    result = llm_client.text("hello")

    assert result == "ok"
    assert fake_model.invoke.call_count == 1


def test_non_retryable_provider_failure(llm_client, fake_model):
    """Case 2: non-retryable provider failure (400 Bad Request)"""
    mock_request = httpx.Request("POST", "https://api.deepseek.com/chat")
    fake_model.invoke.side_effect = APIStatusError(
        message="Bad Request", response=httpx.Response(400, request=mock_request), body=None
    )

    with pytest.raises(LLMProviderError):
        llm_client.text("hello")

    # 验证非瞬时错误直接熔断，不会发起重试
    assert fake_model.invoke.call_count == 1


def test_empty_structured_output_exhausts_retries(llm_client, fake_model):
    """Case 3: empty structured output -> finite retries -> LLMEmptyResponseError"""
    structured_mock = Mock()
    structured_mock.invoke.return_value = None
    fake_model.with_structured_output.return_value = structured_mock

    with pytest.raises(LLMEmptyResponseError):
        llm_client.structured("hello", DummySchema)

    # 1次原始请求 + 2次重试 = 3次
    assert structured_mock.invoke.call_count == 3


def test_structured_parse_failure_exhausts_retries(llm_client, fake_model):
    """Case 4: structured parse failure -> finite retries -> LLMStructuredOutputError"""
    structured_mock = Mock()
    # 返回了普通的字典，而不是 DummySchema 实例，触发类型断言错误
    structured_mock.invoke.return_value = {"field": "wrong type"}
    fake_model.with_structured_output.return_value = structured_mock

    with pytest.raises(LLMStructuredOutputError):
        llm_client.structured("hello", DummySchema)

    assert structured_mock.invoke.call_count == 3


def test_transient_provider_failure_exhausts_retries(llm_client, fake_model):
    """Case 5: transient provider failure -> finite retries -> LLMRetryExhaustedError"""
    mock_request = httpx.Request("POST", "https://api.deepseek.com/chat")
    # 模拟 502 Bad Gateway
    fake_model.invoke.side_effect = APIStatusError(
        message="Bad Gateway", response=httpx.Response(502, request=mock_request), body=None
    )

    with pytest.raises(LLMRetryExhaustedError):
        llm_client.text("hello")

    assert fake_model.invoke.call_count == 3


def test_from_settings_delegates_to_builder(monkeypatch):
    """
    重构回归测试：验证 LLMClient.from_settings 确实将模型构造委托给了 provider 层，
    并保留了自身的应用级 retry 控制权。
    """
    # 1. 伪造一个 BaseChatModel 实例
    fake_model = Mock(spec=BaseChatModel)

    # 2. 拦截 client 模块中的 build_chat_model 函数引用
    mock_build_chat_model = Mock(return_value=fake_model)
    monkeypatch.setattr(guanchen_v2.llm.client, "build_chat_model", mock_build_chat_model)

    # 3. 伪造 Settings 以避免真实环境变量文件的干扰
    mock_settings = Mock()
    mock_settings.llm_max_retries = 3

    # 4. 执行被测构造方法
    client = LLMClient.from_settings(mock_settings)

    # 5. 断言验证：确实发生了一次无损的参数委托
    mock_build_chat_model.assert_called_once_with(settings=mock_settings)

    # 6. （可选的防御性断言）在 Python 中我们可以直接验证内部组装是否成功
    # 证明装配后的模型就是工厂吐出的模型，且保留了 settings 里的 retry 次数
    assert client._model is fake_model
    assert client._max_retries == 3
