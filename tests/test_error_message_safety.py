from unittest.mock import Mock

import httpx
import pytest
from langchain_core.language_models.chat_models import (
    BaseChatModel,
)
from openai import APIStatusError
from pydantic import ValidationError

from guanchen_v2.agents.bazi.models import (
    BaziAgentInput,
    InvalidBaziInput,
)
from guanchen_v2.agents.bazi.requirements import (
    check_bazi_requirements,
)
from guanchen_v2.llm.client import LLMClient
from guanchen_v2.llm.exceptions import (
    LLMProviderError,
)
from guanchen_v2.models.bazi import (
    BirthProfile,
    Gender,
)


def test_unknown_provider_exception_message_is_stable_and_raw_cause_is_preserved():
    model = Mock(spec=BaseChatModel)

    raw_error = RuntimeError("SECRET_PROVIDER_BODY_123")

    model.invoke.side_effect = raw_error

    client = LLMClient(
        model=model,
        max_retries=0,
        retry_wait_exponential_jitter=False,
    )

    with pytest.raises(
        LLMProviderError,
    ) as exc_info:
        client.text("hello")

    assert str(exc_info.value) == "LLM 调用失败"

    assert "SECRET_PROVIDER_BODY_123" not in str(exc_info.value)

    assert exc_info.value.__cause__ is raw_error


def test_api_status_error_does_not_leak_provider_message():
    model = Mock(spec=BaseChatModel)

    request = httpx.Request(
        "POST",
        "https://api.example.test/chat",
    )

    raw_error = APIStatusError(
        message=("Bad Request: SECRET_PROVIDER_RESPONSE"),
        response=httpx.Response(
            400,
            request=request,
        ),
        body={"detail": ("SECRET_PROVIDER_RESPONSE")},
    )

    model.invoke.side_effect = raw_error

    client = LLMClient(
        model=model,
        max_retries=0,
        retry_wait_exponential_jitter=False,
    )

    with pytest.raises(
        LLMProviderError,
    ) as exc_info:
        client.text("hello")

    assert str(exc_info.value) == "LLM 服务请求失败"

    assert "SECRET_PROVIDER_RESPONSE" not in str(exc_info.value)

    assert exc_info.value.__cause__ is raw_error


def test_invalid_bazi_date_returns_stable_business_reason():
    input_data = BaziAgentInput(
        question="测事业",
        year=2023,
        month=2,
        day=29,
    )

    result = check_bazi_requirements(input_data)

    assert isinstance(
        result,
        InvalidBaziInput,
    )

    assert result.reason == ("非法的日期组合，请检查年月日后重新提供。")

    assert "day is out of range" not in result.reason


def test_birth_profile_validation_does_not_leak_datetime_exception():
    with pytest.raises(
        ValidationError,
    ) as exc_info:
        BirthProfile(
            year=2023,
            month=2,
            day=29,
            hour=12,
            minute=0,
            gender=Gender.FEMALE,
        )

    message = str(exc_info.value)

    assert "非法的日期时间组合" in message

    assert "day is out of range" not in message
