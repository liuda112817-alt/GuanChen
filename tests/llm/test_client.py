from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
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
    return LLMClient(
        model=fake_model,
        max_retries=2,
        retry_wait_exponential_jitter=False,
    )


def test_text_happy_path(llm_client, fake_model):
    fake_model.invoke.return_value = AIMessage(content="ok")

    result = llm_client.text("hello")

    assert result == "ok"
    assert fake_model.invoke.call_count == 1


def test_non_retryable_provider_failure(llm_client, fake_model):
    mock_request = httpx.Request(
        "POST",
        "https://api.deepseek.com/chat",
    )

    fake_model.invoke.side_effect = APIStatusError(
        message="Bad Request",
        response=httpx.Response(
            400,
            request=mock_request,
        ),
        body=None,
    )

    with pytest.raises(LLMProviderError):
        llm_client.text("hello")

    assert fake_model.invoke.call_count == 1


def test_empty_structured_output_exhausts_retries(
    llm_client,
    fake_model,
):
    structured_mock = Mock()
    structured_mock.invoke.return_value = None

    fake_model.with_structured_output.return_value = structured_mock

    with pytest.raises(LLMEmptyResponseError):
        llm_client.structured(
            "hello",
            DummySchema,
        )

    assert structured_mock.invoke.call_count == 3


def test_structured_parse_failure_exhausts_retries(
    llm_client,
    fake_model,
):
    structured_mock = Mock()
    structured_mock.invoke.return_value = {
        "field": "wrong type",
    }

    fake_model.with_structured_output.return_value = structured_mock

    with pytest.raises(LLMStructuredOutputError):
        llm_client.structured(
            "hello",
            DummySchema,
        )

    assert structured_mock.invoke.call_count == 3


def test_transient_provider_failure_exhausts_retries(
    llm_client,
    fake_model,
):
    mock_request = httpx.Request(
        "POST",
        "https://api.deepseek.com/chat",
    )

    fake_model.invoke.side_effect = APIStatusError(
        message="Bad Gateway",
        response=httpx.Response(
            502,
            request=mock_request,
        ),
        body=None,
    )

    with pytest.raises(LLMRetryExhaustedError):
        llm_client.text("hello")

    assert fake_model.invoke.call_count == 3


def test_from_settings_delegates_to_builder(monkeypatch):
    fake_model = Mock(spec=BaseChatModel)

    mock_build_chat_model = Mock(
        return_value=fake_model,
    )

    monkeypatch.setattr(
        guanchen_v2.llm.client,
        "build_chat_model",
        mock_build_chat_model,
    )

    mock_settings = Mock()
    mock_settings.llm_max_retries = 3

    client = LLMClient.from_settings(mock_settings)

    mock_build_chat_model.assert_called_once_with(settings=mock_settings)

    assert client._model is fake_model
    assert client._max_retries == 3


@pytest.mark.asyncio
async def test_generate_structured_happy_path_preserves_message_roles(
    llm_client,
    fake_model,
):
    structured_mock = Mock()
    structured_mock.ainvoke = AsyncMock(return_value=DummySchema(field="ok"))

    fake_model.with_structured_output.return_value = structured_mock

    result = await llm_client.generate_structured(
        system_prompt="SYSTEM RULES",
        user_prompt="USER DATA",
        schema=DummySchema,
    )

    assert result == DummySchema(field="ok")

    fake_model.with_structured_output.assert_called_once_with(DummySchema)

    structured_mock.ainvoke.assert_awaited_once()

    messages = structured_mock.ainvoke.await_args.args[0]

    assert len(messages) == 2

    assert isinstance(messages[0], SystemMessage)
    assert messages[0].content == "SYSTEM RULES"

    assert isinstance(messages[1], HumanMessage)
    assert messages[1].content == "USER DATA"


@pytest.mark.asyncio
async def test_generate_structured_empty_output_retries(
    llm_client,
    fake_model,
):
    structured_mock = Mock()
    structured_mock.ainvoke = AsyncMock(return_value=None)

    fake_model.with_structured_output.return_value = structured_mock

    with pytest.raises(LLMEmptyResponseError):
        await llm_client.generate_structured(
            system_prompt="SYSTEM",
            user_prompt="USER",
            schema=DummySchema,
        )

    assert structured_mock.ainvoke.await_count == 3


@pytest.mark.asyncio
async def test_generate_structured_invalid_type_retries(
    llm_client,
    fake_model,
):
    structured_mock = Mock()
    structured_mock.ainvoke = AsyncMock(return_value={"field": "wrong type"})

    fake_model.with_structured_output.return_value = structured_mock

    with pytest.raises(LLMStructuredOutputError):
        await llm_client.generate_structured(
            system_prompt="SYSTEM",
            user_prompt="USER",
            schema=DummySchema,
        )

    assert structured_mock.ainvoke.await_count == 3


@pytest.mark.asyncio
async def test_generate_structured_transient_failure_exhausts_retries(
    llm_client,
    fake_model,
):
    mock_request = httpx.Request(
        "POST",
        "https://api.deepseek.com/chat",
    )

    structured_mock = Mock()
    structured_mock.ainvoke = AsyncMock(
        side_effect=APIStatusError(
            message="Bad Gateway",
            response=httpx.Response(
                502,
                request=mock_request,
            ),
            body=None,
        )
    )

    fake_model.with_structured_output.return_value = structured_mock

    with pytest.raises(LLMRetryExhaustedError):
        await llm_client.generate_structured(
            system_prompt="SYSTEM",
            user_prompt="USER",
            schema=DummySchema,
        )

    assert structured_mock.ainvoke.await_count == 3
