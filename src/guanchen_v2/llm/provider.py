from langchain_core.language_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek

from guanchen_v2.config.settings import Settings
from guanchen_v2.observability.llm_callback import ModelTraceCallback


def build_chat_model(settings: Settings) -> BaseChatModel:
    """
    基础对话模型构建工厂 (Model Construction)。

    提供给 LLMClient、Agent Runtime 共享使用的统一基座。
    注意：
    - 这里严格设置 max_retries=0，禁止底层 Provider 偷偷重试；
    - 所有的 Retry 和重试策略均由各自的应用方（如 LLMClient 或 Agent）自行管理。
    - thinking mode 默认关闭；需要更复杂推理的部署可以通过配置显式开启。
    """
    thinking_mode = getattr(settings, "deepseek_thinking_mode", "disabled")
    if not isinstance(thinking_mode, str) or thinking_mode not in {"enabled", "disabled"}:
        thinking_mode = "disabled"
    reasoning_effort = getattr(settings, "deepseek_reasoning_effort", "low")
    if not isinstance(reasoning_effort, str) or reasoning_effort not in {"low", "high", "max"}:
        reasoning_effort = "low"
    kwargs = {
        "model": settings.deepseek_model,
        "api_key": settings.deepseek_api_key.get_secret_value(),
        "temperature": settings.llm_temperature,
        "timeout": settings.llm_timeout_seconds,
        "max_retries": 0,
        "callbacks": [ModelTraceCallback()],
        "extra_body": {"thinking": {"type": thinking_mode}},
    }
    if thinking_mode == "enabled":
        kwargs["reasoning_effort"] = reasoning_effort
    return ChatDeepSeek(**kwargs)
