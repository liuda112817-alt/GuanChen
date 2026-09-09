from langchain_core.language_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek

from guanchen_v2.config.settings import Settings


def build_chat_model(settings: Settings) -> BaseChatModel:
    """
    基础对话模型构建工厂 (Model Construction)。

    提供给 LLMClient、Agent Runtime 共享使用的统一基座。
    注意：
    - 这里严格设置 max_retries=0，禁止底层 Provider 偷偷重试；
    - 所有的 Retry 和重试策略均由各自的应用方（如 LLMClient 或 Agent）自行管理。
    - 在 extra_body 中禁用 deepseek 的 thinking 模式。
    """
    return ChatDeepSeek(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key.get_secret_value(),
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,
        extra_body={"thinking": {"type": "disabled"}},
    )
