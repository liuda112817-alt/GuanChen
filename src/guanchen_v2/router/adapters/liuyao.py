import uuid
from dataclasses import dataclass

from langgraph.types import Command

from guanchen_v2.liuyao.state import create_initial_liuyao_state
from guanchen_v2.liuyao.workflow import LiuyaoAgentRuntime
from guanchen_v2.router.contracts import RequiredDataType
from guanchen_v2.router.errors import RouterDispatchError
from guanchen_v2.router.requirements import RequirementContext


@dataclass(frozen=True)
class LiuyaoInvocationResult:
    thread_id: str
    output: object


class LiuyaoAgentAdapter:
    def __init__(self, runtime: LiuyaoAgentRuntime):
        self._graph = runtime.build_graph()

    @staticmethod
    def _config(thread_id: str) -> dict:
        return {
            "configurable": {
                "thread_id": thread_id,
            }
        }

    async def invoke(self, query: str, context: RequirementContext) -> LiuyaoInvocationResult:
        seed = context.available_data.get(RequiredDataType.DECISION_QUESTION)

        if seed is None:
            raise RouterDispatchError("LiuyaoAgentAdapter 缺少已声明可用的 DECISION_QUESTION")

        if not isinstance(seed, str) or not seed.strip():
            raise RouterDispatchError("DECISION_QUESTION 必须为非空字符串")

        initial_state = create_initial_liuyao_state(seed)

        thread_id = f"liuyao_adpt_{uuid.uuid4().hex}"

        output = await self._graph.ainvoke(
            initial_state,
            self._config(thread_id),
        )

        return LiuyaoInvocationResult(
            thread_id=thread_id,
            output=output,
        )

    async def resume(self, thread_id: str, payload: dict) -> object:
        """
        允许外部传入用户的交互载荷来恢复被 Interrupt 挂起的流。
        Adapter 自己绝不伪造或替用户确认。
        """
        if not isinstance(thread_id, str) or not thread_id.strip():
            raise RouterDispatchError("Liuyao resume 缺少合法 thread_id")

        return await self._graph.ainvoke(
            Command(resume=payload),
            self._config(thread_id),
        )
