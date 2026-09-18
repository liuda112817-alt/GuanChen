from typing import Any

from guanchen_v2.agents.bazi.models import ReadyForBazi
from guanchen_v2.agents.bazi.runtime import BaziAgentRuntime
from guanchen_v2.models.bazi import BirthProfile
from guanchen_v2.router.contracts import RequiredDataType
from guanchen_v2.router.errors import RouterDispatchError
from guanchen_v2.router.requirements import RequirementContext


class BaziAgentAdapter:
    def __init__(self, runtime: BaziAgentRuntime):
        self._runtime = runtime

    async def invoke(
        self,
        query: str,
        context: RequirementContext,
        agent_state: dict[str, Any] | None = None,
    ) -> object:
        profile = context.available_data.get(RequiredDataType.BIRTH_PROFILE)
        if profile is None:
            raise RouterDispatchError("缺少已声明可用的 BIRTH_PROFILE")
        if not isinstance(profile, BirthProfile):
            raise RouterDispatchError("数据类型不合法：BIRTH_PROFILE 必须是 BirthProfile 对象")
            
        ready_input = ReadyForBazi(question=query, profile=profile)
        return await self._runtime.run(ready_input)

