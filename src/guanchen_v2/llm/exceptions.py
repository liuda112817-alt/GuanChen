from guanchen_v2.core.errors import ProjectError


class LLMError(ProjectError):
    """
    GuanChen LLM 基础设施异常根类型。

    所有稳定的大模型调用异常都应继承该类型。
    """

    pass


class LLMProviderError(LLMError):
    """
    LLM Provider 不可重试错误。

    例如：
    - 非瞬时 API 请求错误
    - 非法模型配置
    - Provider 明确拒绝请求
    """

    pass


class LLMTransientProviderError(LLMProviderError):
    """
    LLM Provider 瞬时错误。

    例如：
    - 网络连接失败
    - 429
    - 5xx
    - 临时服务不可用

    Retry policy 由 LLMClient 负责。
    """

    pass


class LLMResponseError(LLMError):
    """
    Provider 调用已经完成，
    但返回结果不满足 GuanChen 应用层契约。
    """

    pass


class LLMEmptyResponseError(LLMResponseError):
    """LLM 没有返回应用期望的有效内容。"""

    pass


class LLMStructuredOutputError(LLMResponseError):
    """LLM structured output 不满足目标 Schema。"""

    pass


class LLMRetryExhaustedError(LLMError):
    """可重试错误达到最大尝试次数后仍未恢复。"""

    pass
