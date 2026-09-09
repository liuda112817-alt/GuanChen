from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain.agents.middleware.tool_call_limit import ToolCallLimitExceededError
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import HumanMessage

from guanchen_v2.agents.bazi.exceptions import BaziAgentExecutionError, BaziAgentInvariantError
from guanchen_v2.agents.bazi.models import BaziAgentResult, BaziInterpretation, ReadyForBazi
from guanchen_v2.bazi.adapter import LunarPythonBaziAdapter
from guanchen_v2.bazi.service import BaziService
from guanchen_v2.config.settings import Settings
from guanchen_v2.llm.provider import build_chat_model
from guanchen_v2.models.bazi import BaziChart
from guanchen_v2.prompts.bazi_agent import BAZI_AGENT_SYSTEM_PROMPT
from guanchen_v2.tools.bazi import build_calculate_bazi_tool


class BaziAgentRuntime:
    def __init__(self, settings: Settings):
        self._model = build_chat_model(settings=settings)
        self._service = BaziService(LunarPythonBaziAdapter())
        self._bazi_tool = build_calculate_bazi_tool(self._service)
        self._agent = create_agent(
            model=self._model,
            tools=[self._bazi_tool],
            system_prompt=BAZI_AGENT_SYSTEM_PROMPT,
            middleware=[
                ModelCallLimitMiddleware(run_limit=3, exit_behavior="error"),
                ToolCallLimitMiddleware(
                    tool_name="calculate_bazi", run_limit=1, exit_behavior="error"
                ),
            ],
            response_format=ToolStrategy(BaziInterpretation),
        )

    def run(self, ready: ReadyForBazi) -> BaziAgentResult:
        content = (
            f"用户原问题：{ready.question}\n"
            f"已验证完整出生资料：\n"
            f"公历 {ready.profile.year}-{ready.profile.month}-{ready.profile.day} "
            f"{ready.profile.hour}:{ready.profile.minute:02d}\n"
            f"性别：{ready.profile.gender.value}\n"
        )

        if ready.profile.birth_place_text:
            content += f"出生地文本：{ready.profile.birth_place_text}\n"

        try:
            state = self._agent.invoke({"messages": [HumanMessage(content=content)]})
        except (ModelCallLimitExceededError, ToolCallLimitExceededError):
            raise BaziAgentExecutionError("Agent 调用超载")

        bazi_chart_artifact = None
        tool_call_count = 0

        for msg in state.get("messages", []):
            if getattr(msg, "type", "") == "tool_call":
                continue

            if getattr(msg, "type", "") == "tool" and getattr(msg, "name", "") == "calculate_bazi":
                tool_call_count += 1
                if hasattr(msg, "artifact"):
                    bazi_chart_artifact = msg.artifact

        if tool_call_count != 1:
            raise BaziAgentInvariantError(
                f"calculate_bazi tool 必须只调用 1 次，实际调用 {tool_call_count} 次"
            )

        if bazi_chart_artifact is None:
            raise BaziAgentInvariantError("未在 ToolMessage 中找到排盘底座 BaziChart artifact")

        if not isinstance(bazi_chart_artifact, BaziChart):
            raise BaziAgentInvariantError("未在 ToolMessage 中找到合法的 BaziChart artifact")

        structured_response = state.get("structured_response")
        if not structured_response or not isinstance(structured_response, BaziInterpretation):
            raise BaziAgentInvariantError("Agent 未生成合法的 BaziInterpretation 结构化输出")

        return BaziAgentResult(
            question=ready.question, chart=bazi_chart_artifact, answer=structured_response.answer
        )
