import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from guanchen_v2.application.orchestrator import ConversationOrchestrator
from guanchen_v2.core.session.models import ConversationState
from guanchen_v2.liuyao.workflow import LiuyaoAgentRuntime
from guanchen_v2.memory.implementations.inmemory import InMemoryMemoryStore
from guanchen_v2.router.adapters.liuyao import LiuyaoAgentAdapter
from guanchen_v2.router.contracts import IntentType, RequiredDataType
from guanchen_v2.router.core import HighPrecisionRuleRouter, RouterDecision, TwoLayerIntentRouter, build_routing_result
from guanchen_v2.router.dispatch import SingleAgentDispatcher
from guanchen_v2.router.dual_dispatch import DualDomainDispatcher
from guanchen_v2.router.requirements import RequirementContext
from guanchen_v2.router.synthesizer import AgentSynthesizer
from tests.memory.test_checkpoint_recovery import build_mock_services

PROFILE = dict(year=1992, month=8, day=18, hour=10, minute=0, gender="male")


def build_orch(adapters, store=None):
    llm = MagicMock()
    llm.generate_structured = AsyncMock(side_effect=AssertionError("unexpected LLM routing/synthesis"))
    return ConversationOrchestrator(
        store or InMemoryMemoryStore(),
        TwoLayerIntentRouter(HighPrecisionRuleRouter(), llm),
        SingleAgentDispatcher(adapters),
        DualDomainDispatcher(adapters),
        AgentSynthesizer(llm),
    )


def adapter():
    return MagicMock(invoke=AsyncMock(return_value=SimpleNamespace(answer="已完成", citations=())))


@pytest.mark.asyncio
async def test_new_dream_enters_agent_and_followup_stays_in_task():
    dream = adapter()
    orch = build_orch({IntentType.DREAM: dream})
    await orch.execute("dream", "我梦见在河里游泳，非常害怕")
    await orch.execute("dream", "最近工作压力很大")
    assert dream.invoke.await_count == 2
    assert dream.invoke.await_args.args[1].available_data == {RequiredDataType.DREAM_CONTENT: "最近工作压力很大"}


@pytest.mark.asyncio
async def test_explicit_bazi_request_leaves_previous_dream_context():
    dream, bazi = adapter(), adapter()
    orch = build_orch({IntentType.DREAM: dream, IntentType.BAZI: bazi})
    await orch.execute("switch-domain", "我梦见在学校迷路，有点着急")
    response = await orch.execute("switch-domain", "请用八字帮我看看事业。")
    assert response.status == "needs_input"
    assert response.used_intents == (IntentType.BAZI,)
    assert dream.invoke.await_count == 1
    bazi.invoke.assert_not_awaited()


def test_explicit_liuyao_method_request_routes_to_confirmation_workflow():
    decision = HighPrecisionRuleRouter().match("请用六爻帮我看看：未来三个月是否换工作？")
    assert decision.primary_intent == IntentType.LIUYAO


@pytest.mark.asyncio
async def test_birth_supplements_across_rebuild_keep_original_question():
    bazi = adapter()
    store = InMemoryMemoryStore()
    first = build_orch({IntentType.BAZI: bazi}, store)
    response = await first.execute("b", "我的八字事业怎么样")
    assert response.status == "needs_input"
    assert "hour" in response.content
    await first.execute("b", "补充资料", birth_patch={k: v for k, v in PROFILE.items() if k != "hour"})
    bazi.invoke.assert_not_awaited()
    rebuilt = build_orch({IntentType.BAZI: bazi}, store)
    await rebuilt.execute("b", "补充时间", birth_patch={"hour": 10})
    assert bazi.invoke.await_args.args[0] == "我的八字事业怎么样"
    assert bazi.invoke.await_args.args[1].available_data[RequiredDataType.BIRTH_PROFILE].hour == 10


@pytest.mark.asyncio
async def test_dual_pending_and_ready_roundtrip():
    bazi, dream = adapter(), adapter()
    # use real response object for dual synthesis, without a live model
    orch = build_orch({IntentType.BAZI: bazi, IntentType.DREAM: dream})
    from guanchen_v2.router.synthesis import SynthesizedResponse

    orch._synthesizer._llm_client.generate_structured.side_effect = None
    orch._synthesizer._llm_client.generate_structured.return_value = SynthesizedResponse(content="综合", used_intents=())
    query = "结合我的八字和昨晚的梦一起看，我梦见游泳"
    await orch.execute("dual", query)
    pending = await orch._memory_store.load("dual")
    assert pending.requirement_result.status == "needs_input"
    await orch.execute("dual", "补充资料", birth_patch=PROFILE)
    ready = await orch._memory_store.load("dual")
    assert ready.requirement_result.status == "ready"
    assert dream.invoke.await_args.args[1].available_data[RequiredDataType.DREAM_CONTENT] == query
    ConversationState.model_validate_json(ready.model_dump_json())


@pytest.mark.asyncio
async def test_dual_fanout_really_overlaps():
    arrived = set()
    both = asyncio.Event()

    def make(intent):
        async def invoke(*args):
            arrived.add(intent)
            if len(arrived) == 2:
                both.set()
            await asyncio.wait_for(both.wait(), timeout=2)
            return intent.value

        return MagicMock(invoke=invoke)

    dispatcher = DualDomainDispatcher({i: make(i) for i in (IntentType.BAZI, IntentType.DREAM)})
    route = build_routing_result(RouterDecision(primary_intent=IntentType.BAZI, secondary_intents=(IntentType.DREAM,), confidence=1, reason="test"))
    results = await dispatcher.dispatch(route, "query", RequirementContext())
    assert [r.intent for r in results] == [IntentType.BAZI, IntentType.DREAM]


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["不确认", "暂不确认", "我不确认，取消", "先不要确认，我想改一下"])
async def test_negative_confirmation_never_casts(text):
    casting, llm, retrieval = build_mock_services()
    liuyao = LiuyaoAgentAdapter(LiuyaoAgentRuntime(casting, llm, retrieval))
    context = RequirementContext(available_data={RequiredDataType.DECISION_QUESTION: "是否换工作"})
    state = {}
    await liuyao.invoke("开始", context, state)
    await liuyao.invoke(text, context, state)
    assert casting.cast_random.call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["confirm", "cancel", "modify"])
async def test_direct_resume_persists_latest_record(action):
    casting, llm, retrieval = build_mock_services()
    records = MagicMock(save=AsyncMock())
    liuyao = LiuyaoAgentAdapter(LiuyaoAgentRuntime(casting, llm, retrieval), records)
    context = RequirementContext(available_data={RequiredDataType.DECISION_QUESTION: "是否换工作"})
    first = await liuyao.invoke("开始", context, {})
    output = await liuyao.resume(first.thread_id, {"action": action, **({"modification": "加上家庭约束"} if action == "modify" else {})})
    saved = records.save.await_args.args[0]
    assert saved.status == output["question"].status
    assert saved.thread_id == first.thread_id
    assert records.save.await_count == 2
    assert saved.hexagram == output.get("hexagram")


@pytest.mark.asyncio
async def test_new_liuyao_and_confirmation_through_real_orchestrator():
    casting, llm, retrieval = build_mock_services()
    liuyao = LiuyaoAgentAdapter(LiuyaoAgentRuntime(casting, llm, retrieval))
    orch = build_orch({IntentType.LIUYAO: liuyao})
    first = await orch.execute("l", "帮我起一卦，是否换工作")
    assert first.status == "interrupted"
    assert casting.cast_random.call_count == 0
    result = await orch.execute("l", "确认")
    assert result.status == "answered"
    assert result.thread_id == first.thread_id
    assert casting.cast_random.call_count == 1
    state = await orch._memory_store.load("l")
    assert state.pending_interrupt is None


@pytest.mark.asyncio
async def test_rules_only_cannot_pass_gate():
    from scripts.eval_router import evaluate, load_golden

    report = await evaluate(load_golden(), rules_only=True)
    assert not report["passed"]
    assert report["accuracy"] is None
    assert report["evaluated"] < report["total"]


@pytest.mark.asyncio
async def test_clarification_continues_original_question():
    from guanchen_v2.liuyao.policy import ClarificationAssessment

    casting, llm, retrieval = build_mock_services()
    llm.generate_structured.side_effect = [
        ClarificationAssessment(needs_clarification=True, clarification_prompt="请补充具体选项"),
        ClarificationAssessment(needs_clarification=False, clarified_question="是否接受新职位", reality_constraints=[]),
    ]
    liuyao = LiuyaoAgentAdapter(LiuyaoAgentRuntime(casting, llm, retrieval))
    orch = build_orch({IntentType.LIUYAO: liuyao})
    first = await orch.execute("clarify", "帮我起一卦，工作问题")
    assert first.status == "needs_input"
    second = await orch.execute("clarify", "现在有一个新的职位邀请")
    assert second.status == "interrupted"
    assert second.thread_id == first.thread_id
    assert "现在有一个新的职位邀请" in llm.generate_structured.await_args.kwargs["user_prompt"]
    assert casting.cast_random.call_count == 0


@pytest.mark.asyncio
async def test_completed_workflow_uses_new_thread_for_next_question():
    casting, llm, retrieval = build_mock_services()
    liuyao = LiuyaoAgentAdapter(LiuyaoAgentRuntime(casting, llm, retrieval))
    orch = build_orch({IntentType.LIUYAO: liuyao})
    first = await orch.execute("thread", "帮我起一卦，是否换工作")
    await orch.execute("thread", "取消")
    second = await orch.execute("thread", "帮我起一卦，是否搬家")
    assert first.thread_id != second.thread_id
    assert second.status == "interrupted"


@pytest.mark.asyncio
async def test_dual_workflow_resume_only_calls_waiting_agent():
    casting, llm, retrieval = build_mock_services()
    liuyao = LiuyaoAgentAdapter(LiuyaoAgentRuntime(casting, llm, retrieval))
    bazi = adapter()
    orch = build_orch({IntentType.LIUYAO: liuyao, IntentType.BAZI: bazi})
    orch._router._llm_client.generate_structured.side_effect = None
    orch._router._llm_client.generate_structured.return_value = RouterDecision(
        primary_intent=IntentType.BAZI, secondary_intents=(IntentType.LIUYAO,), confidence=1, reason="显式双域"
    )
    first = await orch.execute("multi", "结合八字与六爻，分析工作选择", birth_patch=PROFILE)
    assert first.status == "interrupted"
    await orch.execute("multi", "确认")
    assert bazi.invoke.await_count == 1
    assert casting.cast_random.call_count == 1
