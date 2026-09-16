from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)
from langchain.agents.middleware.model_call_limit import (
    ModelCallLimitExceededError,
)
from langchain.agents.middleware.tool_call_limit import (
    ToolCallLimitExceededError,
)
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import HumanMessage

from guanchen_v2.agents.bazi.exceptions import (
    BaziAgentCitationError,
    BaziAgentExecutionError,
    BaziAgentInvariantError,
)
from guanchen_v2.agents.bazi.models import (
    BaziAgentResult,
    BaziInterpretation,
    ReadyForBazi,
)
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
    def __init__(
        self,
        settings: Settings,
        retrieval_service: RetrievalService,
    ) -> None:
        self._model = build_chat_model(settings=settings)

        self._service = BaziService(LunarPythonBaziAdapter())

        self._bazi_tool = build_calculate_bazi_tool(self._service)

        self._retrieve_tool = build_retrieve_bazi_knowledge_tool(retrieval_service)

        self._agent = create_agent(
            model=self._model,
            tools=[
                self._bazi_tool,
                self._retrieve_tool,
            ],
            system_prompt=BAZI_AGENT_SYSTEM_PROMPT,
            middleware=[
                ModelCallLimitMiddleware(
                    run_limit=3,
                    exit_behavior="error",
                ),
                ToolCallLimitMiddleware(
                    tool_name="calculate_bazi",
                    run_limit=1,
                    exit_behavior="error",
                ),
                ToolCallLimitMiddleware(
                    tool_name=("retrieve_bazi_knowledge"),
                    run_limit=1,
                    exit_behavior="error",
                ),
            ],
            response_format=ToolStrategy(
                BaziInterpretation,
                handle_errors=False,
            ),
        )

    async def run(
        self,
        ready: ReadyForBazi,
    ) -> BaziAgentResult:
        content = (
            "=== USER QUESTION ===\n"
            f"{ready.question}\n\n"
            "=== VERIFIED BIRTH INPUT ===\n"
            f"公历 {ready.profile.year}-"
            f"{ready.profile.month}-"
            f"{ready.profile.day} "
            f"{ready.profile.hour}:"
            f"{ready.profile.minute:02d}\n"
            f"性别：{ready.profile.gender.value}\n"
        )

        if ready.profile.birth_place_text:
            content += f"出生地文本：{ready.profile.birth_place_text}\n"

        try:
            state = await self._agent.ainvoke({"messages": [HumanMessage(content=content)]})
        except (
            ModelCallLimitExceededError,
            ToolCallLimitExceededError,
        ) as exc:
            raise BaziAgentExecutionError("Agent 工具调用超载") from exc
        except Exception as exc:
            raise BaziAgentExecutionError("Agent 基础执行失败") from exc

        # ---------------------------------------------------------
        # 工具集
        # ---------------------------------------------------------

        bazi_chart_artifact: BaziChart | None = None

        bazi_knowledge_artifact: BaziKnowledgeArtifact | None = None

        calc_bazi_count = 0
        retrieve_count = 0

        for message in state.get(
            "messages",
            [],
        ):
            if (
                getattr(
                    message,
                    "type",
                    "",
                )
                != "tool"
            ):
                continue

            tool_name = getattr(
                message,
                "name",
                "",
            )

            if tool_name == "calculate_bazi":
                calc_bazi_count += 1

                if hasattr(
                    message,
                    "artifact",
                ):
                    bazi_chart_artifact = message.artifact

            elif tool_name == "retrieve_bazi_knowledge":
                retrieve_count += 1

                if hasattr(
                    message,
                    "artifact",
                ):
                    bazi_knowledge_artifact = message.artifact

        # ---------------------------------------------------------
        # 工具调用约束条件
        # ---------------------------------------------------------

        if calc_bazi_count != 1:
            raise BaziAgentInvariantError(f"calculate_bazi tool 必须只调用 1 次，实际调用 {calc_bazi_count} 次")

        if retrieve_count > 1:
            raise BaziAgentInvariantError(f"retrieve_bazi_knowledge tool 最多只能调用 1 次，实际调用 {retrieve_count} 次")

        if not isinstance(
            bazi_chart_artifact,
            BaziChart,
        ):
            raise BaziAgentInvariantError("未在 ToolMessage 中找到合法的 BaziChart artifact")

        if retrieve_count == 1 and not isinstance(
            bazi_knowledge_artifact,
            BaziKnowledgeArtifact,
        ):
            raise BaziAgentInvariantError("retrieve_bazi_knowledge 未返回合法的 BaziKnowledgeArtifact")

        # ---------------------------------------------------------
        # 结构化响应不变量
        # ---------------------------------------------------------

        structured_response = state.get("structured_response")

        if not isinstance(
            structured_response,
            BaziInterpretation,
        ):
            raise BaziAgentInvariantError("Agent 未生成合法的 BaziInterpretation 结构化输出")

        # ---------------------------------------------------------
        # 引文溯源
        # ---------------------------------------------------------

        legal_chunk_ids = {}

        if bazi_knowledge_artifact is not None:
            for result in bazi_knowledge_artifact.results:
                legal_chunk_ids[result.chunk_id] = result

        deduped_ids: list[str] = []
        seen: set[str] = set()

        for chunk_id in structured_response.used_chunk_ids:
            if chunk_id in seen:
                continue

            seen.add(chunk_id)
            deduped_ids.append(chunk_id)

        for chunk_id in deduped_ids:
            if chunk_id not in legal_chunk_ids:
                raise BaziAgentCitationError("模型返回了未授权的证据编号。")

        citations: list[Citation] = []

        for chunk_id in deduped_ids:
            result = legal_chunk_ids[chunk_id]

            citations.append(Citation.from_retrieval_result(result))

        return BaziAgentResult(
            question=ready.question,
            chart=bazi_chart_artifact,
            answer=structured_response.answer,
            citations=tuple(citations),
        )
