from guanchen_v2.core.errors import ProjectError


class BaziError(ProjectError):
    """
    GuanChen Bazi 子系统异常根类型。
    """

    pass


class BaziAdapterError(BaziError):
    """
    八字第三方排盘适配器异常。

    当 lunar_python 计算失败，
    或其返回结果无法满足 GuanChen Bazi Domain Contract
    时抛出。
    """

    pass


class BaziCalculationError(BaziError):
    """
    GuanChen 八字确定性排盘业务能力执行失败。

    由 Service 层屏蔽底层 Adapter 实现细节后抛出。
    """

    pass
