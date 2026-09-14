from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain.agents.middleware.tool_call_limit import ToolCallLimitExceededError
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import HumanMessage

from guanchen_v2.agents.bazi.exceptions import (
    BaziAgentCitationError,
    BaziAgentExecutionError,
    BaziAgentInvariantError,
)
from guanchen_v2.agents.bazi.models import BaziAgentResult, BaziInterpretation, ReadyForBazi
from guanchen_v2.bazi.adapter import LunarPythonBaziAdapter
from guanchen_v2.bazi.service import BaziService
from guanchen_v2.config.settings import Settings
from guanchen_v2.knowledge.models import Citation
from guanchen_v2.knowledge.retrieval.service import RetrievalService
from guanchen_v2.llm.provider import build_chat_model
from guanchen_v2.models.bazi import BaziChart
from guanchen_v2.prompts.bazi_agent import BAZI_AGENT_SYSTEM_PROMPT
from guanchen_v2.tools.bazi import build_calculate_bazi_tool
from guanchen_v2.tools.bazi_retrieval import (
    BaziKnowledgeArtifact,
    build_retrieve_bazi_knowledge_tool,
)


class BaziAgentRuntime:
    def __init__(self, settings: Settings, retrieval_service: RetrievalService):
        self._model = build_chat_model(settings=settings)
        self._service = BaziService(LunarPythonBaziAdapter())
        self._bazi_tool = build_calculate_bazi_tool(self._service)
        self._retrieve_tool = build_retrieve_bazi_knowledge_tool(retrieval_service)

        self._agent = create_agent(
            model=self._model,
            tools=[self._bazi_tool, self._retrieve_tool],
            system_prompt=BAZI_AGENT_SYSTEM_PROMPT,
            middleware=[
                ModelCallLimitMiddleware(run_limit=3, exit_behavior="error"),
                ToolCallLimitMiddleware(
                    tool_name="calculate_bazi", run_limit=1, exit_behavior="error"
                ),
                ToolCallLimitMiddleware(
                    tool_name="retrieve_bazi_knowledge", run_limit=1, exit_behavior="error"
                ),
            ],
            response_format=ToolStrategy(BaziInterpretation, handle_errors=False),
        )

    async def run(self, ready: ReadyForBazi) -> BaziAgentResult:
        content = (
            f"=== USER QUESTION ===\n{ready.question}\n\n"
            f"=== VERIFIED BIRTH INPUT ===\n"
            f"公历 {ready.profile.year}-{ready.profile.month}-{ready.profile.day} "
            f"{ready.profile.hour}:{ready.profile.minute:02d}\n"
            f"性别：{ready.profile.gender.value}\n"
        )

        if ready.profile.birth_place_text:
            content += f"出生地文本：{ready.profile.birth_place_text}\n"

        try:
            state = await self._agent.ainvoke({"messages": [HumanMessage(content=content)]})
        except (ModelCallLimitExceededError, ToolCallLimitExceededError) as exc:
            raise BaziAgentExecutionError("Agent 工具调用超载") from exc
        except Exception as exc:
            raise BaziAgentExecutionError("Agent 基础执行失败") from exc

        bazi_chart_artifact = None
        calc_bazi_count = 0
        retrieve_count = 0

        for msg in state.get("messages", []):
            if getattr(msg, "type", "") == "tool":
                if getattr(msg, "name", "") == "calculate_bazi":
                    calc_bazi_count += 1
                    if hasattr(msg, "artifact"):
                        bazi_chart_artifact = msg.artifact
                elif getattr(msg, "name", "") == "retrieve_bazi_knowledge":
                    retrieve_count += 1
                    if hasattr(msg, "artifact"):
                        bazi_knowledge_artifact = msg.artifact

        if calc_bazi_count != 1:
            raise BaziAgentInvariantError(
                f"calculate_bazi tool 必须只调用 1 次，实际调用 {calc_bazi_count} 次"
            )
        if retrieve_count > 1:
            raise BaziAgentInvariantError(
                f"retrieve_bazi_knowledge tool 最多只能调用 1 次，实际调用 {retrieve_count} 次"
            )

        if not isinstance(bazi_chart_artifact, BaziChart):
            raise BaziAgentInvariantError("未在 ToolMessage 中找到合法的 BaziChart artifact")

        if retrieve_count == 1 and not isinstance(bazi_knowledge_artifact, BaziKnowledgeArtifact):
            raise BaziAgentInvariantError(
                "retrieve_bazi_knowledge 未返回合法的 BaziKnowledgeArtifact"
            )

        structured_response = state.get("structured_response")
        if not structured_response or not isinstance(structured_response, BaziInterpretation):
            raise BaziAgentInvariantError("Agent 未生成合法的 BaziInterpretation 结构化输出")

        legal_chunk_ids = {}
        if bazi_knowledge_artifact:
            for res in bazi_knowledge_artifact.results:
                legal_chunk_ids[res.chunk_id] = res

        deduped_ids = []
        seen = set()
        for cid in structured_response.used_chunk_ids:
            if cid not in seen:
                deduped_ids.append(cid)
                seen.add(cid)

        for cid in deduped_ids:
            if cid not in legal_chunk_ids:
                raise BaziAgentCitationError("模型返回了未授权的证据编号。")

        citations = []
        for cid in deduped_ids:
            res = legal_chunk_ids[cid]
            citations.append(Citation.from_retrieval_result(res))

        return BaziAgentResult(
            question=ready.question,
            chart=bazi_chart_artifact,
            answer=structured_response.answer,
            citations=tuple(citations),
        )
