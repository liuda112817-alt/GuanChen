from typing import Any, Mapping, Protocol

from guanchen_v2.router.contracts import IntentType, RoutingResult
from guanchen_v2.router.errors import RouterDispatchError
from guanchen_v2.router.requirements import (
    RequirementCheckResult,
    RequirementContext,
    RequirementStatus,
    check_requirements,
)


class AgentAdapter(Protocol):
    async def invoke(
        self,
        query: str,
        context: RequirementContext,
        agent_state: dict[str, Any] | None = None,
    ) -> object: ...


class SingleAgentDispatcher:
    def __init__(self, registry: Mapping[IntentType, AgentAdapter]):
        invalid_intents = {IntentType.CHITCHAT, IntentType.OUT_OF_SCOPE}
        for intent in registry:
            if intent in invalid_intents:
                raise RouterDispatchError(f"Registry 不能包含非专业 Agent: {intent.value}")

        self._registry = dict(registry)

    async def dispatch(
        self,
        routing: RoutingResult,
        requirement: RequirementCheckResult,
        query: str,
        context: RequirementContext,
        agent_state: dict[str, Any] | None = None,
    ) -> object:
        if routing.secondary_intents:
            raise RouterDispatchError("Single-agent dispatcher 不接受双领域 RoutingResult")

        if routing.primary_intent != requirement.intent:
            raise RouterDispatchError("RoutingResult 与 RequirementCheckResult intent 不一致")

        if requirement.status in {RequirementStatus.BYPASS, RequirementStatus.NEEDS_INPUT}:
            return requirement

        # 防伪防线：对“已就绪”的结果做一次确定性重算，防止携带陈旧 / 伪造的
        # RequirementCheckResult 绕过资料检查后直接调度 Agent。
        fresh = check_requirements(routing, context)
        if (
            fresh.intent != requirement.intent
            or fresh.status != requirement.status
            or fresh.missing_data != requirement.missing_data
        ):
            raise RouterDispatchError("RequirementCheckResult 与当前 RoutingResult / Context 不一致")

        adapter = self._registry.get(routing.primary_intent)
        if adapter is None:
            raise RouterDispatchError(f"缺少处理 {routing.primary_intent.value} 的 AgentAdapter")

        # 将对应 Agent 的状态字典传入 Adapter，让其实现自治的状态（包括 Checkpoint）存取
        return await adapter.invoke(query, context, agent_state)

