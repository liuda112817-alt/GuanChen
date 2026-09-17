from guanchen_v2.dream.runtime import DreamAgentRuntime
from guanchen_v2.router.contracts import RequiredDataType
from guanchen_v2.router.errors import RouterDispatchError
from guanchen_v2.router.requirements import RequirementContext


class DreamAgentAdapter:
    def __init__(self, runtime: DreamAgentRuntime):
        self._runtime = runtime

    async def invoke(self, query: str, context: RequirementContext) -> object:
        content = context.available_data.get(RequiredDataType.DREAM_CONTENT)

        if content is None:
            raise RouterDispatchError("DreamAgentAdapter 缺少已声明可用的 DREAM_CONTENT")

        if not isinstance(content, str) or not content.strip():
            raise RouterDispatchError("DREAM_CONTENT 必须为非空字符串")

        return await self._runtime.handle_turn(content)
