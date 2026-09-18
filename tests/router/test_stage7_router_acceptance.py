from unittest.mock import AsyncMock

import pytest

from guanchen_v2.router.adapters.liuyao import LiuyaoInvocationResult
from guanchen_v2.router.contracts import IntentType, RequiredDataType
from guanchen_v2.router.core import HighPrecisionRuleRouter, RouterDecision, TwoLayerIntentRouter
from guanchen_v2.router.dispatch import SingleAgentDispatcher
from guanchen_v2.router.dual_dispatch import AgentExecutionResult, DualDomainDispatcher
from guanchen_v2.router.dual_requirements import check_dual_requirements
from guanchen_v2.router.requirements import RequirementContext, RequirementStatus
from guanchen_v2.router.synthesis import SynthesisInput
from guanchen_v2.router.synthesizer import AgentSynthesizer


@pytest.fixture
def mock_adapters():
    def create_adapter(return_val):
        adapter = AsyncMock()
        adapter.invoke.return_value = return_val
        return adapter

    return {
        IntentType.BAZI: create_adapter({"bazi": "done"}),
        IntentType.DREAM: create_adapter({"dream": "done"}),
        IntentType.LIUYAO: create_adapter(LiuyaoInvocationResult(thread_id="test_tid", output="paused")),
        IntentType.KNOWLEDGE: create_adapter("knowledge done"),
    }


@pytest.fixture
def mock_llm():
    return AsyncMock()


@pytest.mark.asyncio
async def test_stage7_case1_explicit_dual_domain_happy_path(mock_adapters, mock_llm):
    """Test 1: 真实双领域，成功流转直到合成器"""
    router = TwoLayerIntentRouter(HighPrecisionRuleRouter(), mock_llm)
    dual_dispatch = DualDomainDispatcher(mock_adapters)
    synthesizer = AgentSynthesizer(mock_llm)

    # 1. 路由
    query = "结合我的八字和昨晚的梦一起看吧"
    routing_result = await router.route(query)
    assert routing_result.primary_intent == IntentType.BAZI
    assert routing_result.secondary_intents == (IntentType.DREAM,)

    # 2. 校验
    context = RequirementContext(available_data={RequiredDataType.BIRTH_PROFILE: "profile", RequiredDataType.DREAM_CONTENT: "content"})
    req_result = check_dual_requirements(routing_result, context)
    assert req_result.status == RequirementStatus.READY

    # 3. 分发
    exec_results = await dual_dispatch.dispatch(routing_result, query, context)
    assert mock_adapters[IntentType.BAZI].invoke.call_count == 1
    assert mock_adapters[IntentType.DREAM].invoke.call_count == 1

    # 4. 汇总
    synthesis_input = SynthesisInput(query=query, results=exec_results)
    from guanchen_v2.router.synthesis import SynthesizedResponse

    mock_llm.generate_structured.return_value = SynthesizedResponse(content="合并结果", used_intents=())
    await synthesizer.synthesize(synthesis_input)

    # Synthesizer 发起的 LLM 调用合并结论
    mock_llm.generate_structured.assert_awaited_once()


@pytest.mark.asyncio
async def test_stage7_case2_missing_data_rejects_dispatch(mock_adapters, mock_llm):
    """Test 2: 资料缺失导致中断，绝不盲目派遣 Agent"""
    router = TwoLayerIntentRouter(HighPrecisionRuleRouter(), mock_llm)

    routing_result = await router.route("结合我的八字和昨晚的梦一起看吧")

    # Context 中故意漏掉 DreamContent
    context = RequirementContext(available_data={RequiredDataType.BIRTH_PROFILE: "profile"})
    req_result = check_dual_requirements(routing_result, context)

    # 精准阻断
    assert req_result.status == RequirementStatus.NEEDS_INPUT
    assert req_result.missing_data == (RequiredDataType.DREAM_CONTENT,)

    # 确保没有任何 Agent 被实际调用
    for adapter in mock_adapters.values():
        adapter.invoke.assert_not_called()


@pytest.mark.asyncio
async def test_stage7_case3_pseudo_dual_domain_isolated(mock_adapters, mock_llm):
    """Test 3: 防止伪双领域越权（提及算命，但属于单梦境诉求）"""
    mock_llm.generate_structured.return_value = RouterDecision(primary_intent=IntentType.DREAM, confidence=0.9, reason="仅仅提及八字")
    router = TwoLayerIntentRouter(HighPrecisionRuleRouter(), mock_llm)
    single_dispatch = SingleAgentDispatcher(mock_adapters)

    query = "昨天睡觉的时候，梦里有个道士帮我排八字，这是啥意思？"
    routing_result = await router.route(query)

    # 坚决不产生双领域
    assert routing_result.primary_intent == IntentType.DREAM
    assert routing_result.secondary_intents == ()

    context = RequirementContext(available_data={RequiredDataType.DREAM_CONTENT: "梦见道士排八字"})

    # 因为是单领域，所以可以直接使用 Single Dispatch
    from guanchen_v2.router.requirements import check_requirements

    req = check_requirements(routing_result, context)
    await single_dispatch.dispatch(routing_result, req, query, context)

    # 确保没有发生蔓延，Bazi Adapter 完全不知道
    assert mock_adapters[IntentType.DREAM].invoke.call_count == 1
    assert mock_adapters[IntentType.BAZI].invoke.call_count == 0


@pytest.mark.asyncio
async def test_stage7_case4_liuyao_synthesizer_preserves_thread_id(mock_adapters, mock_llm):
    """Test 4: Liuyao 返回结构必须能无损送达，且严格防止 thread_id 泄露给大模型"""
    synthesizer = AgentSynthesizer(mock_llm)

    exec_results = (
        mock_adapters[IntentType.BAZI].invoke("...", None),
        mock_adapters[IntentType.LIUYAO].invoke("...", None),
    )
    resolved = await __import__("asyncio").gather(*exec_results)

    synthesis_input = SynthesisInput(
        query="结合八字看看要不要换工作",
        results=(
            AgentExecutionResult(intent=IntentType.BAZI, output=resolved[0]),
            AgentExecutionResult(intent=IntentType.LIUYAO, output=resolved[1]),
        ),
    )

    from guanchen_v2.router.synthesis import SynthesizedResponse

    mock_llm.generate_structured.return_value = SynthesizedResponse(content="合并结果", used_intents=())
    await synthesizer.synthesize(synthesis_input)

    synthesizer_call_args = mock_llm.generate_structured.await_args.kwargs
    prompt_sent_to_llm = synthesizer_call_args["user_prompt"]

    # 核心断言：大模型看到的必须是纯业务载荷，绝对不包含内部状态句柄(test_tid)
    assert "[Liuyao Result]" in prompt_sent_to_llm
    assert "test_tid" not in prompt_sent_to_llm  # 防止内存越权泄漏
    assert "paused" in prompt_sent_to_llm
