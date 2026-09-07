class LLMError(RuntimeError):
    """
    GuanChen LLM 基础设施的顶层基类。
    所有大模型相关的自定义异常均继承自此类，用于业务层统一兜底拦截。
    """

    pass


class LLMProviderError(LLMError):
    """
    LLM 供应商层面不可重试错误。
    例如：API Key 错误、模型名称错误、账户欠费等（通常对应 400 或 401 等状态码）。
    """

    pass


class LLMTransientProviderError(LLMProviderError):
    """
    LLM 供应商层面可重试错误。
    例如：网络超时、502 网关崩溃、429 频率限制等。LLMClient 会自动捕获此类错误并触发指数退避重试。
    """

    pass


class LLMResponseError(LLMError):
    """
    大模型返回值异常的基类。
    表示网络请求已成功，但大模型给出的结果不符合应用层的契约要求。
    """

    pass


class LLMEmptyResponseError(LLMResponseError):
    """LLM 调用完成，但没有得到应用期望的有效内容。"""

    pass


class LLMStructuredOutputError(LLMResponseError):
    """LLM structured output 未满足调用方提供的 Pydantic Schema。"""

    pass


class LLMRetryExhaustedError(LLMError):
    """可重试的瞬时 Provider 错误达到最大尝试次数后仍未恢复。"""

    pass
