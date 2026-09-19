from typing import Any

from guanchen_v2.agents.knowledge.agent import KnowledgeAgent
from guanchen_v2.observability.decorators import trace
from guanchen_v2.router.requirements import RequirementContext


class KnowledgeAgentAdapter:
    def __init__(self, agent: KnowledgeAgent):
        self._agent = agent

    @trace("knowledge", "AGENT")
    async def invoke(
        self,
        query: str,
        context: RequirementContext,
        agent_state: dict[str, Any] | None = None,
    ) -> object:
        return await self._agent.answer(query)

