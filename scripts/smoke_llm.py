import logging

from pydantic import BaseModel, ConfigDict, Field

from guanchen_v2.config.settings import Settings
from guanchen_v2.core.logging import configure_logging
from guanchen_v2.llm.client import LLMClient
from guanchen_v2.llm.exceptions import LLMError
from guanchen_v2.prompts.smoke import TEXT_SMOKE_PROMPT, build_structured_smoke_prompt

logger = logging.getLogger(__name__)


class StructuredSmokeResult(BaseModel):
    """
    仅用于 Stage 1 Smoke 测试的契约，不属于业务 Domain Model。
    明确禁止 LLM 生成 schema 之外的冗余字段。
    """

    model_config = ConfigDict(extra="forbid")

    project_name: str = Field(min_length=1)
    agent_names: list[str] = Field(min_length=4, max_length=4)


def run_smoke(client: LLMClient) -> None:
    text_result = client.text(TEXT_SMOKE_PROMPT)
    assert text_result.strip(), "文本模型返回了空字符串"
    logger.info("文本生成执行成功。")
    print(text_result)

    structured_prompt = build_structured_smoke_prompt()
    structured_result = client.structured(structured_prompt, StructuredSmokeResult)
    logger.info("结构化输出执行成功。")
    print(structured_result.model_dump_json(indent=2))


def main():
    settings = Settings()
    configure_logging(settings.log_level)
    client = LLMClient.from_settings(settings=settings)
    try:
        run_smoke(client=client)
    except LLMError:
        logger.exception("LLM 基础设施调用失败")
        raise
    except Exception:
        logger.exception("发生未知的异常")
        raise


if __name__ == "__main__":
    main()
