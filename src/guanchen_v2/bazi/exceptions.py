class BaziAdapterError(RuntimeError):
    """
    八字排盘适配器异常。
    当 lunar_python 计算失败或第三方返回值无法满足
    GuanChen Bazi Domain Contract 时抛出。
    """

    pass


class BaziCalculationError(RuntimeError):
    """
    GuanChen 八字确定性排盘业务能力执行失败。
    由服务层抛出，屏蔽了底层的第三方实现细节。
    """

    pass
