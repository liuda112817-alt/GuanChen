from typing import Mapping, Protocol

from guanchen_v2.router.contracts import IntentType, RoutingResult
from guanchen_v2.router.errors import RouterDispatchError
from guanchen_v2.router.requirements import RequirementCheckResult, RequirementContext, RequirementStatus, check_requirements


class AgentAdapter(Protocol):
    async def invoke(
        self,
        query: str,
        context: RequirementContext,
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
    ) -> object:
        # 1. 拦截双领域
        if routing.secondary_intents:
            raise RouterDispatchError("Single-agent dispatcher 不接受双领域 RoutingResult")

        # 2. 拦截上下文意图不一致
        if routing.primary_intent != requirement.intent:
            raise RouterDispatchError("RoutingResult 与 RequirementCheckResult intent 不一致")

        # 3. 再次使用原始 Context 和 Routing 计算期待的 CheckResult 并全等比对
        expected_requirement = check_requirements(routing, context)
        if requirement != expected_requirement:
            raise RouterDispatchError("RequirementCheckResult 与当前 RoutingResult / Context 不一致")

        # 4. 按照状态过滤执行
        if requirement.status in {RequirementStatus.BYPASS, RequirementStatus.NEEDS_INPUT}:
            return requirement

        # 5. 精确取出 Primary Agent
        adapter = self._registry.get(routing.primary_intent)
        if adapter is None:
            raise RouterDispatchError(f"缺少处理 {routing.primary_intent.value} 的 AgentAdapter")

        return await adapter.invoke(query, context)
