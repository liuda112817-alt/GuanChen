from guanchen_v2.bazi.adapter import LunarPythonBaziAdapter
from guanchen_v2.bazi.exceptions import BaziAdapterError, BaziCalculationError
from guanchen_v2.models.bazi import BaziChart, BirthProfile


class BaziService:
    """八字排盘业务层，封装底层实现，对外提供稳定的业务能力。"""

    def __init__(self, adapter: LunarPythonBaziAdapter) -> None:
        self._adapter = adapter

    def calculate(self, profile: BirthProfile) -> BaziChart:
        """执行确定性排盘。发生异常时不进行重试，并封装为纯业务异常抛出。"""
        try:
            return self._adapter.calculate(profile=profile)
        except BaziAdapterError as exc:
            raise BaziCalculationError("八字排盘业务执行失败。") from exc
