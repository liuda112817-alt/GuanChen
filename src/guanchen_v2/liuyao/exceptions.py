from guanchen_v2.core.errors import ProjectError


class LiuyaoError(ProjectError):
    """
    GuanChen 六爻子系统异常根类型。
    """

    pass


class HexagramCalculationError(LiuyaoError):
    """
    六爻卦象确定性计算失败。
    当第三方排盘库崩溃或返回非法格式时抛出。
    """

    pass


class LiuyaoPolicyError(LiuyaoError):
    """六爻策略与状态机校验不一致异常"""

    pass
