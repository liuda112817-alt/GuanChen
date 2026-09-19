from guanchen_v2.bazi.formatting import render_bazi_facts
from guanchen_v2.dream.runtime import DreamAgentResult
from guanchen_v2.llm.client import LLMClient
from guanchen_v2.prompts.voice import GUANCHEN_VOICE_GUIDE
from guanchen_v2.router.adapters.liuyao import LiuyaoInvocationResult
from guanchen_v2.router.contracts import IntentType
from guanchen_v2.router.dual_requirements import DualRequirementCheckResult
from guanchen_v2.router.output_formatter import format_agent_result
from guanchen_v2.router.requirements import RequirementCheckResult, RequirementStatus
from guanchen_v2.router.synthesis import SynthesisDraft, SynthesisInput, SynthesizedResponse

SYNTHESIZER_PROMPT = """
你是系统中的结果整理器（Synthesizer）。

你的输入来自一个或多个已经完成专业处理的 Agent。
这些 Agent 的输出已经经过各自领域逻辑处理。

你的唯一职责：
- 整理 Agent 输出
- 合并信息表达
- 帮助用户理解不同 Agent 提供的参考内容
八字的确定性排盘表、起运偏移、日期和年龄由应用代码直接展示。
不要在整理文字中重新抄写或改写这些数值、单位、四柱或藏干清单。

你不是专业分析 Agent。
你不能重新执行任何领域推理。

====================
Agent 权责边界
====================

BAZI Agent：
- 负责八字相关分析结果。
- 只能引用其已经提供的八字分析内容。
- 不允许你根据出生资料重新推导新的结论。

DREAM Agent：
- 负责梦境内容相关解释。
- 只能整理其已经提供的梦境分析。
- 不允许你自行解释梦境象征。

LIUYAO Agent：
- 负责六爻流程产生的结果。
- 只能整理其已经提供的卦象、解释或流程状态。
- 不允许你自行重新起卦、断卦或推演。

KNOWLEDGE Agent：
- 负责传统文化知识说明。
- 只能整理其提供的知识内容。

====================
信息合并规则
====================

1. 保留不同 Agent 的来源区别。

例如：
- “八字分析认为……”
- “梦境解析认为……”
- “六爻结果显示……”

不要将不同 Agent 的内容混合成一个无法追溯来源的新观点。

2. 如果不同 Agent 的观点存在差异：
- 如实保留差异。
- 可以说明“不同角度提供了不同参考”。
- 不允许自行判断哪个观点正确。

3. 不允许创造 Agent 没有提供的信息。

禁止：
- 推导新的因果关系。
- 增加新的预测。
- 增加新的建议。
- 替用户做最终决定。

====================
输出要求
====================

根据输入内容组织自然语言回复。

推荐结构：

【领域参考】
整理各 Agent 提供的主要内容。

【综合整理】
仅总结已有信息之间的联系。

【说明】
如果涉及传统文化分析：
说明内容属于文化参考，不替代现实判断。

如果只有一个 Agent：
直接整理该 Agent 输出。
不要制造不存在的“综合分析”。

====================
系统字段处理
====================

输入中的以下字段属于系统控制信息：

- thread_id
- checkpoint 信息
- workflow 状态

这些字段：
- 可以用于保持系统流程完整性。
- 不得展示给最终用户。

====================
绝对禁止
====================

1. 不重新进行八字分析。
2. 不重新解释梦境。
3. 不重新进行六爻判断。
4. 不生成 Agent 未提供的新结论。
5. 不替用户选择现实方案。
6. 不隐藏 Agent 之间的重要差异。
7. 不泄露系统内部字段。

你的输出必须只是：
对已有 Agent 结果的准确整理。
""".strip()

SYNTHESIZER_PROMPT += "\n\n" + GUANCHEN_VOICE_GUIDE


class AgentSynthesizer:
    def __init__(self, llm_client: LLMClient):
        self._llm_client = llm_client

    async def synthesize(self, synthesis_input: SynthesisInput) -> SynthesizedResponse:
        # Single-domain results retain their validated facts/citations without another LLM.
        if len(synthesis_input.results) == 1:
            result = synthesis_input.results[0]
            output = result.output
            intents = (result.intent,)
            if isinstance(output, (RequirementCheckResult, DualRequirementCheckResult)):
                if output.status == RequirementStatus.BYPASS:
                    content = (
                        "得嘞，传统文化、八字、梦境和六爻决策反思，我都可以陪你捋一捋。"
                        if result.intent == IntentType.CHITCHAT
                        else "这件事不在当前服务范围里，咱们先不硬掰。"
                    )
                    return SynthesizedResponse(content=content, used_intents=())
                return SynthesizedResponse(
                    content="先补一点关键资料，别急着往下猜：" + "、".join(x.value for x in output.missing_data),
                    status="needs_input",
                    used_intents=intents,
                )
            if isinstance(output, LiuyaoInvocationResult):
                values = output.output
                if not isinstance(values, dict):
                    values = {"final_response": str(values)}
                question = values.get("question")
                status = getattr(question, "status", None)
                interrupts = values.get("__interrupt__", ())
                if interrupts:
                    content = "先别急着落子，咱们把问题再对一遍：" + str(getattr(question, "clarified_question", ""))
                    response_status = "interrupted"
                elif str(status) == "cancelled":
                    content, response_status = "行，这次先不落卦，停在这儿。", "cancelled"
                else:
                    content = values.get("final_response") or values.get("clarification") or "请继续补充决策问题。"
                    response_status = "answered" if values.get("final_response") else "needs_input"
                hexagram = values.get("hexagram")
                if hexagram is not None and response_status == "answered":
                    content = (
                        "起卦方式："
                        + hexagram.casting_method.value
                        + "；爻值（自下而上）："
                        + ", ".join(str(x.value.value) for x in hexagram.lines)
                        + "\n\n"
                        + content
                    )
                return SynthesizedResponse(
                    content=content,
                    used_intents=intents,
                    thread_id=output.thread_id,
                    status=response_status,
                    citations=tuple(values.get("citations", ())),
                    facts=hexagram.model_dump(mode="json") if hexagram is not None else {},
                )
            if isinstance(output, DreamAgentResult):
                content = output.clarification_question or (
                    "【传统文化象征】\n" + output.response.traditional_view + "\n\n【心理与现实情境】\n" + output.response.psychological_context_view
                )
                return SynthesizedResponse(content=content, used_intents=intents, status=output.status.value, citations=tuple(output.citations))
            content = getattr(output, "answer", None) or getattr(output, "content", None)
            if content is not None:
                facts = output.chart.model_dump(mode="json") if hasattr(output, "chart") else {}
                if hasattr(output, "chart"):
                    content = render_bazi_facts(output.chart) + "\n\n【传统解释与现实反思】\n" + content
                return SynthesizedResponse(content=content, used_intents=intents, citations=tuple(getattr(output, "citations", ())), facts=facts)
        if len(synthesis_input.results) == 2:
            workflow = next((r for r in synthesis_input.results if isinstance(r.output, LiuyaoInvocationResult)), None)
            if workflow is not None:
                projected = await self.synthesize(SynthesisInput(query=synthesis_input.query, results=(workflow,)))
                if projected.status != "answered":
                    other = next(r for r in synthesis_input.results if r is not workflow)
                    other_response = await self.synthesize(SynthesisInput(query=synthesis_input.query, results=(other,)))
                    return projected.model_copy(
                        update={
                            "content": other_response.content + "\n\n" + projected.content,
                            "used_intents": tuple(r.intent for r in synthesis_input.results),
                            "citations": (*other_response.citations, *projected.citations),
                            "facts": {other.intent.value: other_response.facts, workflow.intent.value: projected.facts},
                        }
                    )
        formatted_blocks = []
        for res in synthesis_input.results:
            formatted_blocks.append(f"=== {res.intent.value} Agent Result ===\n{format_agent_result(res)}")

        user_prompt = f"用户原始问题: {synthesis_input.query}\n\nAgent 产出结果:\n" + "\n\n".join(formatted_blocks)

        response = await self._llm_client.generate_structured(
            system_prompt=SYNTHESIZER_PROMPT,
            user_prompt=user_prompt,
            schema=SynthesisDraft,
        )

        # Preserve authoritative facts and nested workflow citations through dual synthesis.
        citations = []
        facts = {}
        thread_id = None
        fact_blocks = []
        for result in synthesis_input.results:
            output = result.output
            if isinstance(output, LiuyaoInvocationResult):
                values = output.output if isinstance(output.output, dict) else {}
                citations.extend(values.get("citations", ()))
                if values.get("hexagram") is not None:
                    facts[result.intent.value] = values["hexagram"].model_dump(mode="json")
                thread_id = output.thread_id
            else:
                citations.extend(getattr(output, "citations", ()))
                if hasattr(output, "chart"):
                    facts[result.intent.value] = output.chart.model_dump(mode="json")
                    fact_blocks.append(render_bazi_facts(output.chart))
        return SynthesizedResponse(
            content="\n\n".join([*fact_blocks, response.content]),
            used_intents=tuple(r.intent for r in synthesis_input.results),
            citations=tuple(citations),
            facts=facts,
            thread_id=thread_id,
        )
