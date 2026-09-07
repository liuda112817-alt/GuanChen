from typing import Any, TypeVar

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableLambda
from langchain_deepseek import ChatDeepSeek
from openai import APIConnectionError, APIError, APIStatusError
from pydantic import BaseModel, ValidationError

from guanchen_v2.config.settings import Settings
from guanchen_v2.llm.exceptions import (
    LLMEmptyResponseError,
    LLMError,
    LLMProviderError,
    LLMResponseError,
    LLMRetryExhaustedError,
    LLMStructuredOutputError,
    LLMTransientProviderError,
)

StructuredT = TypeVar("StructuredT", bound=BaseModel)


def _translate_provider_error(exc: Exception) -> LLMError:
    """Third-party Exception -> GuanChen LLM Exception 转换器"""
    if isinstance(exc, (OutputParserException, ValidationError)):
        return LLMStructuredOutputError("结构化输出失败")

    if isinstance(exc, APIConnectionError):
        return LLMTransientProviderError("网络连接失败")

    if isinstance(exc, APIStatusError):
        if exc.status_code in (408, 409, 429) or exc.status_code >= 500:
            return LLMTransientProviderError(f"服务暂时不可用 (HTTP {exc.status_code})")
        return LLMProviderError(f"服务请求失败 (HTTP {exc.status_code})")

    if isinstance(exc, APIError):
        return LLMProviderError(f"LLM API 异常: {exc}")

    return LLMProviderError(f"未知的 LLM 调用异常: {exc}")


class LLMClient:
    def __init__(
        self,
        model: BaseChatModel,
        max_retries: int = 0,
        *,
        retry_wait_exponential_jitter: bool = True,
    ) -> None:
        self._model = model
        self._max_retries = max_retries
        self._retry_jitter = retry_wait_exponential_jitter

    @classmethod
    def from_settings(cls, settings: Settings) -> "LLMClient":
        model = ChatDeepSeek(
            api_key=settings.deepseek_api_key.get_secret_value(),
            model=settings.deepseek_model,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
            extra_body={"thinking": {"type": "disabled"}},
        )
        return cls(
            model=model,
            max_retries=settings.llm_max_retries,
        )

    def _invoke_text_once(self, prompt: str) -> str:
        try:
            response = self._model.invoke(prompt)
            if not isinstance(response.content, str):
                raise LLMResponseError(
                    f"模型调用预期返回字符串，实际得到类型: {type(response.content)}"
                )
            if not response.content.split():
                raise LLMEmptyResponseError("返回了空字符串结果")
            return response.content
        except (LLMResponseError, LLMEmptyResponseError):
            raise
        except Exception as exc:
            raise _translate_provider_error(exc) from exc

    def text(self, prompt: str) -> str:
        runnable = RunnableLambda(self._invoke_text_once).with_retry(
            retry_if_exception_type=(LLMTransientProviderError, LLMEmptyResponseError),
            wait_exponential_jitter=self._retry_jitter,
            stop_after_attempt=self._max_retries + 1,
        )
        try:
            return runnable.invoke(prompt)
        except LLMTransientProviderError as exc:
            raise LLMRetryExhaustedError("文本生成重试次数已耗尽") from exc

    def _invoke_structured_once(self, payload: dict[str, Any]) -> StructuredT:
        prompt = payload["prompt"]
        schema = payload["schema"]

        try:
            structured_llm = self._model.with_structured_output(schema)
            result = structured_llm.invoke(prompt)

            if result is None:
                raise LLMEmptyResponseError("结构化输出返回了空结果")
            if not isinstance(result, schema):
                raise LLMStructuredOutputError(
                    f"结构化输出类型不匹配，预期 Schema: {schema.__name__}"
                )

            return result
        except (LLMEmptyResponseError, LLMStructuredOutputError):
            raise
        except Exception as exc:
            raise _translate_provider_error(exc) from exc

    def structured(self, prompt: str, schema: type[StructuredT]) -> StructuredT:
        runnable = RunnableLambda(self._invoke_structured_once).with_retry(
            retry_if_exception_type=(
                LLMTransientProviderError,
                LLMEmptyResponseError,
                LLMStructuredOutputError,
            ),
            wait_exponential_jitter=self._retry_jitter,
            stop_after_attempt=self._max_retries + 1,
        )
        try:
            return runnable.invoke({"prompt": prompt, "schema": schema})
        except LLMTransientProviderError as exc:
            raise LLMRetryExhaustedError("结构化输出重试次数已耗尽") from exc
