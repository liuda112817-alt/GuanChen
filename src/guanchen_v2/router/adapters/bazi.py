from guanchen_v2.agents.bazi.models import ReadyForBazi
from guanchen_v2.agents.bazi.runtime import BaziAgentRuntime
from guanchen_v2.models.bazi import BirthProfile
from guanchen_v2.router.contracts import RequiredDataType
from guanchen_v2.router.errors import RouterDispatchError
from guanchen_v2.router.requirements import RequirementContext


class BaziAgentAdapter:
    def __init__(self, runtime: BaziAgentRuntime):
        self._runtime = runtime

    async def invoke(self, query: str, context: RequirementContext) -> object:
        # 防御性快失：Dispatcher 既然说是 READY，那就必须真有
        profile = context.available_data.get(RequiredDataType.BIRTH_PROFILE)
        if profile is None:
            raise RouterDispatchError("BaziAgentAdapter 缺少已声明可用的 BIRTH_PROFILE")

        if not isinstance(profile, BirthProfile):
            raise RouterDispatchError("BIRTH_PROFILE 数据类型不合法，必须为 BirthProfile 实例")

        # 转换为已有 Agent 的标准入口参数
        ready_input = ReadyForBazi(question=query, profile=profile)

        # 直接透传执行，不捕获底层的业务异常 (如 BaziCalculationError 等)
        return await self._runtime.run(ready_input)
