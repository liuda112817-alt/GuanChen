from dataclasses import dataclass
from typing import Any, Mapping

from guanchen_v2.router.contracts import IntentType, RoutingResult
from guanchen_v2.router.dispatch import AgentAdapter
from guanchen_v2.router.errors import RouterDispatchError
from guanchen_v2.router.requirements import RequirementContext


@dataclass(frozen=True)
class AgentExecutionResult:
    """
    Router 层统一 Agent 执行结果。

    Router 不解析领域 Agent 内部结构。
    """

    intent: IntentType

    output: object

class DualDomainDispatcher:
    def __init__(self, registry: Mapping[IntentType, AgentAdapter]):
        invalid_intents = {IntentType.CHITCHAT, IntentType.OUT_OF_SCOPE}
        for intent in registry:
            if intent in invalid_intents:
                raise RouterDispatchError(f"Dual registry 不能包含非专业 Agent: {intent.value}")

        self._registry = dict(registry)

    async def dispatch(
        self,
        routing: RoutingResult,
        query: str,
        context: RequirementContext,
        primary_agent_state: dict[str, Any] | None = None,
        secondary_agent_state: dict[str, Any] | None = None,
    ) -> tuple[AgentExecutionResult, ...]:
        if len(routing.secondary_intents) != 1:
            raise RouterDispatchError(f"DualDomainDispatcher 仅接受双领域请求，当前 secondary 数量: {len(routing.secondary_intents)}")

        primary_intent = routing.primary_intent
        secondary_intent = routing.secondary_intents[0]

        primary_adapter = self._registry.get(primary_intent)
        secondary_adapter = self._registry.get(secondary_intent)

        if primary_adapter is None or secondary_adapter is None:
            missing = (
                primary_intent.value
                if primary_adapter is None
                else secondary_intent.value
            )
            raise RouterDispatchError(f"缺少处理 {missing} 的 AgentAdapter")

        # 严格串行执行；仅在显式提供 Agent State 时透传（保持协议默认参数语义）
        if primary_agent_state is None:
            primary_output = await primary_adapter.invoke(query, context)
        else:
            primary_output = await primary_adapter.invoke(query, context, primary_agent_state)

        if secondary_agent_state is None:
            secondary_output = await secondary_adapter.invoke(query, context)
        else:
            secondary_output = await secondary_adapter.invoke(query, context, secondary_agent_state)

        return (
            AgentExecutionResult(intent=primary_intent, output=primary_output),
            AgentExecutionResult(intent=secondary_intent, output=secondary_output),
        )

