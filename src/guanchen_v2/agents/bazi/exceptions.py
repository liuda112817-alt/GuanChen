from guanchen_v2.bazi.exceptions import BaziError


class BaziAgentError(BaziError):
    """
    GuanChen Bazi Agent 异常根类型。
    """

    pass


class BaziAgentExecutionError(BaziAgentError):
    """
    Agent runtime / model / structured output /
    call budget 等执行阶段失败。
    """

    pass


class BaziAgentInvariantError(BaziAgentError):
    """
    Agent 执行完成，
    但违反 GuanChen Bazi Agent 后置条件。
    """

    pass


class BaziAgentCitationError(BaziAgentError):
    """
    Agent 返回了不属于本轮合法 Retrieval Evidence
    的 chunk_id。
    """

    pass
