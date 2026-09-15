from typing import Any, TypeVar

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda
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
from guanchen_v2.llm.provider import build_chat_model

StructuredT = TypeVar(
    "StructuredT",
    bound=BaseModel,
)


def _translate_provider_error(
    exc: Exception,
) -> LLMError:
    """
    将第三方异常转换为 GuanChen 稳定 LLM 异常。

    重要约束：
    - 不把 str(exc) 拼入稳定项目错误消息；
    - Provider 原始异常通过 exception chaining 保存在 __cause__；
    - 对外消息只表达应用需要知道的错误类别。
    """
    if isinstance(
        exc,
        (
            OutputParserException,
            ValidationError,
        ),
    ):
        return LLMStructuredOutputError("结构化输出失败")

    if isinstance(
        exc,
        APIConnectionError,
    ):
        return LLMTransientProviderError("LLM 网络连接失败")

    if isinstance(
        exc,
        APIStatusError,
    ):
        if (
            exc.status_code
            in (
                408,
                409,
                429,
            )
            or exc.status_code >= 500
        ):
            return LLMTransientProviderError("LLM 服务暂时不可用")

        return LLMProviderError("LLM 服务请求失败")

    if isinstance(
        exc,
        APIError,
    ):
        return LLMProviderError("LLM API 调用失败")

    return LLMProviderError("LLM 调用失败")


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
    def from_settings(
        cls,
        settings: Settings,
    ) -> "LLMClient":
        model = build_chat_model(settings=settings)

        return cls(
            model=model,
            max_retries=(settings.llm_max_retries),
        )

    def _invoke_text_once(
        self,
        prompt: str,
    ) -> str:
        try:
            response = self._model.invoke(prompt)

            if not isinstance(
                response.content,
                str,
            ):
                raise LLMResponseError("模型调用返回了非文本内容")

            if not response.content.split():
                raise LLMEmptyResponseError("返回了空字符串结果")

            return response.content

        except (
            LLMResponseError,
            LLMEmptyResponseError,
        ):
            raise

        except Exception as exc:
            raise _translate_provider_error(exc) from exc

    def text(
        self,
        prompt: str,
    ) -> str:
        runnable = RunnableLambda(self._invoke_text_once).with_retry(
            retry_if_exception_type=(
                LLMTransientProviderError,
                LLMEmptyResponseError,
            ),
            wait_exponential_jitter=(self._retry_jitter),
            stop_after_attempt=(self._max_retries + 1),
        )

        try:
            return runnable.invoke(prompt)

        except LLMTransientProviderError as exc:
            raise LLMRetryExhaustedError("文本生成重试次数已耗尽") from exc

    def _invoke_structured_once(
        self,
        payload: dict[str, Any],
    ) -> StructuredT:
        prompt: str = payload["prompt"]
        schema: type[StructuredT] = payload["schema"]

        try:
            structured_llm = self._model.with_structured_output(schema)

            result = structured_llm.invoke(prompt)

            if result is None:
                raise LLMEmptyResponseError("结构化输出返回了空结果")

            if not isinstance(
                result,
                schema,
            ):
                raise LLMStructuredOutputError(f"结构化输出类型不匹配，预期 Schema: {schema.__name__}")

            return result

        except (
            LLMEmptyResponseError,
            LLMStructuredOutputError,
        ):
            raise

        except Exception as exc:
            raise _translate_provider_error(exc) from exc

    def structured(
        self,
        prompt: str,
        schema: type[StructuredT],
    ) -> StructuredT:
        runnable = RunnableLambda(self._invoke_structured_once).with_retry(
            retry_if_exception_type=(
                LLMTransientProviderError,
                LLMEmptyResponseError,
                LLMStructuredOutputError,
            ),
            wait_exponential_jitter=(self._retry_jitter),
            stop_after_attempt=(self._max_retries + 1),
        )

        try:
            return runnable.invoke(
                {
                    "prompt": prompt,
                    "schema": schema,
                }
            )

        except LLMTransientProviderError as exc:
            raise LLMRetryExhaustedError("结构化输出重试次数已耗尽") from exc

    async def _ainvoke_structured_once(
        self,
        payload: dict[str, Any],
    ) -> StructuredT:
        system_prompt: str = payload["system_prompt"]
        user_prompt: str = payload["user_prompt"]
        schema: type[StructuredT] = payload["schema"]

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        try:
            structured_llm = self._model.with_structured_output(schema)

            result = await structured_llm.ainvoke(messages)

            if result is None:
                raise LLMEmptyResponseError("结构化输出返回了空结果")

            if not isinstance(
                result,
                schema,
            ):
                raise LLMStructuredOutputError(f"结构化输出类型不匹配，预期 Schema: {schema.__name__}")

            return result

        except (
            LLMEmptyResponseError,
            LLMStructuredOutputError,
        ):
            raise

        except Exception as exc:
            raise _translate_provider_error(exc) from exc

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: type[StructuredT],
    ) -> StructuredT:
        runnable = RunnableLambda(self._ainvoke_structured_once).with_retry(
            retry_if_exception_type=(
                LLMTransientProviderError,
                LLMEmptyResponseError,
                LLMStructuredOutputError,
            ),
            wait_exponential_jitter=(self._retry_jitter),
            stop_after_attempt=(self._max_retries + 1),
        )

        try:
            return await runnable.ainvoke(
                {
                    "system_prompt": (system_prompt),
                    "user_prompt": (user_prompt),
                    "schema": schema,
                }
            )

        except LLMTransientProviderError as exc:
            raise LLMRetryExhaustedError("结构化输出重试次数已耗尽") from exc
