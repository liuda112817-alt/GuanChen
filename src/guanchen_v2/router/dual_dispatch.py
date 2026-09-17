from dataclasses import dataclass
from typing import Mapping

from guanchen_v2.router.contracts import IntentType, RoutingResult
from guanchen_v2.router.dispatch import AgentAdapter
from guanchen_v2.router.errors import RouterDispatchError
from guanchen_v2.router.requirements import RequirementContext


@dataclass(frozen=True)
class AgentExecutionResult:
    """
    统一的 Agent 执行结果信封。
    保留原始输出对象（无论是 dict, 文本，还是 LiuyaoInvocationResult），
    解耦 Synthesizer 对底层 Agent 签名的直接依赖。
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
    ) -> tuple[AgentExecutionResult, ...]:
        """
        双领域安全分发：绝对串行执行，保留六爻 HITL 的时序安全。
        """
        # 1. 严格防御：只接受正好 1 个 secondary intent 的双领域路由
        if len(routing.secondary_intents) != 1:
            raise RouterDispatchError(f"DualDomainDispatcher 仅接受双领域请求，当前 secondary 数量: {len(routing.secondary_intents)}")

        primary_intent = routing.primary_intent
        secondary_intent = routing.secondary_intents[0]

        # 2. 严格防御：检查注册表完整性
        primary_adapter = self._registry.get(primary_intent)
        secondary_adapter = self._registry.get(secondary_intent)

        if primary_adapter is None:
            raise RouterDispatchError(f"缺少处理 {primary_intent.value} 的 AgentAdapter")
        if secondary_adapter is None:
            raise RouterDispatchError(f"缺少处理 {secondary_intent.value} 的 AgentAdapter")

        # 3. 严格串行执行 (禁止 asyncio.gather，避免中断型 Agent 的状态竞态)
        primary_output = await primary_adapter.invoke(query, context)
        secondary_output = await secondary_adapter.invoke(query, context)

        # 4. 组装契约返回
        return (
            AgentExecutionResult(intent=primary_intent, output=primary_output),
            AgentExecutionResult(intent=secondary_intent, output=secondary_output),
        )
