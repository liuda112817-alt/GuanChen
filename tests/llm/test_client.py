from unittest.mock import Mock

import httpx
import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from openai import APIStatusError
from pydantic import BaseModel

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
