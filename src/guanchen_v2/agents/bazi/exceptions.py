class BaziAgentError(Exception):
    """GuanChen Agent 基础异常"""

    pass


class BaziAgentExecutionError(BaziAgentError):
    """Agent runtime / model / structured output / call budget 环节执行失败"""

    pass


class BaziAgentInvariantError(BaziAgentError):
    """Agent 虽然执行结束，但违反了业务后置条件（如未调用排盘工具）"""

    pass


class BaziAgentCitationError(BaziAgentError):
    """模型伪造、或乱报了不属于本轮检索的 chunk_id。"""

    pass
