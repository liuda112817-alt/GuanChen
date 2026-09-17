from guanchen_v2.agents.knowledge.agent import KnowledgeAgent
from guanchen_v2.router.requirements import RequirementContext


class KnowledgeAgentAdapter:
    def __init__(self, agent: KnowledgeAgent):
        self._agent = agent

    async def invoke(self, query: str, context: RequirementContext) -> object:
        # 最薄的 Adapter：
        # 知识域只取 query，完全忽略 context.available_data！
        # 这就从物理层面上杜绝了 Knowledge Agent 误读 BirthProfile 的可能。
        return await self._agent.answer(query)
