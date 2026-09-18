"""Stage 8 系统验收测试。

覆盖规划冻结的 Stage 8 验收场景：
- 应用重启后会话状态（含 Agent States）仍可恢复；
- 多轮对话跨重启完整保留；
- 六爻 HITL 中断 -> 恢复 -> 完成（编排层 + 持久化）；
- 会话隔离（不同 session 互不串扰）；
- Memory Selector 集成：八字长期记忆预填，重启后无需重复询问。
"""
import json
import uuid
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from guanchen_v2.application.orchestrator import ConversationOrchestrator
from guanchen_v2.memory.implementations.postgres import PostgresMemoryStore
from guanchen_v2.memory.selector import MemorySelector
from guanchen_v2.models.bazi import BirthProfile, Gender
from guanchen_v2.router.contracts import IntentType, RequiredDataType, RoutingResult
from guanchen_v2.router.dispatch import SingleAgentDispatcher
from guanchen_v2.router.dual_dispatch import DualDomainDispatcher
from guanchen_v2.router.requirements import RequirementStatus
from guanchen_v2.router.synthesis import SynthesizedResponse
from guanchen_v2.router.synthesizer import AgentSynthesizer

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# 测试替身
# ---------------------------------------------------------------------------

class FakeRouter:
    """按路由表返回 RoutingResult，required_data 由路由表控制。"""

    def __init__(self, table: dict[str, RoutingResult]) -> None:
        self._table = table

    async def route(self, query: str) -> RoutingResult:
        return self._table[query]


@dataclass
class FakeOutput:
    content: str
    thread_id: str | None = None

    def model_dump_json(self) -> str:
        return json.dumps({"content": self.content, "thread_id": self.thread_id})


class FakeSingleAdapter:
    def __init__(self, output: FakeOutput) -> None:
        self._output = output
        self.invocation_count = 0
        self.invoked_profiles: list[BirthProfile] = []

    async def invoke(self, query: str, context, agent_state: dict | None = None):
        self.invocation_count += 1
        profile = context.available_data.get(RequiredDataType.BIRTH_PROFILE)
        if profile is not None:
            self.invoked_profiles.append(profile)
        return self._output


class FakeLiuyaoAdapter:
    """模拟：首轮中断并保存 thread 引用，次轮（同会话）恢复完成。"""

    async def invoke(self, query: str, context, agent_state: dict | None = None):
        agent_state = agent_state or {}
        if agent_state.get("thread_id"):
            # Resume 流程
            agent_state["status"] = "COMPLETED"
            return FakeOutput(
                content="卦象推演完成",
                thread_id=agent_state["thread_id"],
            )

        thread_id = f"liuyao_t_{uuid.uuid4().hex[:8]}"
        agent_state["thread_id"] = thread_id
        agent_state["status"] = "INTERRUPTED"
        agent_state["pending_node"] = "confirmation"
        return FakeOutput(content="请确认问题", thread_id=thread_id)


def build_orchestrator(
    factory,
    routing_table: dict[str, RoutingResult],
    adapters: dict,
    memory_selector: MemorySelector | None = None,
) -> ConversationOrchestrator:
    memory_store = PostgresMemoryStore(factory)
    router = FakeRouter(routing_table)
    single = SingleAgentDispatcher(adapters)
    dual = DualDomainDispatcher(adapters)
    llm = MagicMock()
    llm.generate_structured = AsyncMock(
        return_value=SynthesizedResponse(content="系统合并回复", used_intents=())
    )
    synthesizer = AgentSynthesizer(llm)
    return ConversationOrchestrator(
        memory_store=memory_store,
        router=router,
        single_dispatcher=single,
        dual_dispatcher=dual,
        synthesizer=synthesizer,
        memory_selector=memory_selector,
    )


def knowledge_routing() -> RoutingResult:
    return RoutingResult(
        primary_intent=IntentType.KNOWLEDGE,
        confidence=1.0,
        required_data=(),
        reason="知识查询",
    )


def liuyao_routing() -> RoutingResult:
    return RoutingResult(
        primary_intent=IntentType.LIUYAO,
        confidence=1.0,
        required_data=(RequiredDataType.DECISION_QUESTION,),
        reason="六爻决策",
    )


def bazi_routing() -> RoutingResult:
    return RoutingResult(
        primary_intent=IntentType.BAZI,
        confidence=1.0,
        required_data=(RequiredDataType.BIRTH_PROFILE,),
        reason="八字分析",
    )


# ---------------------------------------------------------------------------
# 验收测试
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_normal_agent_recovery(postgres_session_factory):
    """知识问答流程：写入状态 -> 新 Orchestrator 实例（模拟重启）恢复。"""
    session_id = f"acc-knowledge-{uuid.uuid4().hex[:8]}"
    adapter = FakeSingleAdapter(FakeOutput(content="知识库回答"))

    orch_a = build_orchestrator(
        postgres_session_factory,
        {"今天天气如何": knowledge_routing()},
        {IntentType.KNOWLEDGE: adapter},
    )
    await orch_a.execute(session_id, "今天天气如何")

    orch_b = build_orchestrator(
        postgres_session_factory,
        {"今天天气如何": knowledge_routing()},
        {IntentType.KNOWLEDGE: adapter},
    )
    state_b = await orch_b._memory_store.load(session_id)

    assert state_b is not None
    roles = [m.role for m in state_b.messages]
    assert roles == ["user", "assistant"]
    assert state_b.routing_result is not None
    assert state_b.routing_result.primary_intent == IntentType.KNOWLEDGE
    assert adapter.invocation_count == 1


@pytest.mark.asyncio
async def test_multi_turn_conversation(postgres_session_factory):
    """多轮对话：4 条消息完整保留，且新 Orchestrator 可恢复并继续。"""
    session_id = f"acc-multiturn-{uuid.uuid4().hex[:8]}"
    adapter = FakeSingleAdapter(FakeOutput(content="回复"))
    table = {
        "八卦是什么": knowledge_routing(),
        "再讲细一点": knowledge_routing(),
    }

    orch_a = build_orchestrator(postgres_session_factory, table, {IntentType.KNOWLEDGE: adapter})
    await orch_a.execute(session_id, "八卦是什么")
    await orch_a.execute(session_id, "再讲细一点")

    orch_b = build_orchestrator(postgres_session_factory, table, {IntentType.KNOWLEDGE: adapter})
    state_b = await orch_b._memory_store.load(session_id)

    assert state_b is not None
    assert len(state_b.messages) == 4
    assert state_b.messages[0].content == "八卦是什么"
    assert state_b.messages[2].content == "再讲细一点"
    assert [m.role for m in state_b.messages] == ["user", "assistant", "user", "assistant"]


@pytest.mark.asyncio
async def test_liuyao_interrupt_resume_after_reload(postgres_session_factory):
    """
    六爻 HITL 恢复：应用重启后，凭持久化的 DecisionRecord + Agent State 恢复中断流程。
    （六爻读取当前 DecisionRecord：Memory Selector 注入问题种子 -> READY -> resume）
    """
    from guanchen_v2.core.session.models import ConversationState
    from guanchen_v2.models.liuyao import (
        DecisionQuestion,
        DecisionQuestionStatus,
        DecisionRecord,
    )

    session_id = f"acc-liuyao-{uuid.uuid4().hex[:8]}"
    selector = MemorySelector(postgres_session_factory)
    liuyao_adapter = FakeLiuyaoAdapter()
    table = {"确认": liuyao_routing()}
    adapters = {IntentType.LIUYAO: liuyao_adapter}

    # 模拟“首轮已发生并中断”：持久化未完成的 DecisionRecord + 线程引用
    thread_id = f"liuyao_t_{uuid.uuid4().hex[:8]}"
    record = DecisionRecord(
        question=DecisionQuestion(
            original_question="我该不该跳槽",
            clarified_question="我该不该跳槽",
            status=DecisionQuestionStatus.PENDING_CONFIRMATION,
        ),
        thread_id=thread_id,
        status=DecisionQuestionStatus.PENDING_CONFIRMATION,
    )
    await selector.persist_decision_record(session_id, record)

    ms = PostgresMemoryStore(postgres_session_factory)
    await ms.save(ConversationState(session_id=session_id))
    state_pre = await ms.load(session_id)
    state_pre.agent_states.liuyao["thread_id"] = thread_id
    state_pre.agent_states.liuyao["status"] = "INTERRUPTED"
    state_pre.agent_states.liuyao["pending_node"] = "confirmation"
    await ms.update(state_pre)

    # 模拟重启：全新 Orchestrator，同一 session，同一 Memory Selector
    orch = build_orchestrator(
        postgres_session_factory,
        table,
        adapters,
        memory_selector=selector,
    )
    await orch.execute(session_id, "确认")

    state_after = await ms.load(session_id)
    assert state_after.agent_states.liuyao["status"] == "COMPLETED"
    assert state_after.agent_states.liuyao["thread_id"] == thread_id
    assert len(state_after.messages) == 2  # 本轮 user + assistant


@pytest.mark.asyncio
async def test_session_isolation(postgres_session_factory):
    """会话隔离：不同 session 的长期记忆与 Agent State 互不污染。"""
    from guanchen_v2.core.session.models import ConversationState
    from guanchen_v2.models.liuyao import (
        DecisionQuestion,
        DecisionQuestionStatus,
        DecisionRecord,
    )

    selector = MemorySelector(postgres_session_factory)
    liuyao_adapter = FakeLiuyaoAdapter()
    table = {"确认": liuyao_routing()}
    adapters = {IntentType.LIUYAO: liuyao_adapter}

    orch = build_orchestrator(
        postgres_session_factory,
        table,
        adapters,
        memory_selector=selector,
    )
    ms = PostgresMemoryStore(postgres_session_factory)

    session_a = f"acc-iso-a-{uuid.uuid4().hex[:8]}"
    session_b = f"acc-iso-b-{uuid.uuid4().hex[:8]}"

    # Session A：存在中断的六爻决策
    thread_a = f"liuyao_t_{uuid.uuid4().hex[:8]}"
    await selector.persist_decision_record(
        session_a,
        DecisionRecord(
            question=DecisionQuestion(
                original_question="要不要投资",
                clarified_question="要不要投资",
                status=DecisionQuestionStatus.PENDING_CONFIRMATION,
            ),
            thread_id=thread_a,
            status=DecisionQuestionStatus.PENDING_CONFIRMATION,
        ),
    )
    await ms.save(ConversationState(session_id=session_a))
    state_a = await ms.load(session_a)
    state_a.agent_states.liuyao["thread_id"] = thread_a
    state_a.agent_states.liuyao["status"] = "INTERRUPTED"
    await ms.update(state_a)

    await orch.execute(session_a, "确认")
    await orch.execute(session_b, "确认")

    state_a_after = await ms.load(session_a)
    state_b_after = await ms.load(session_b)

    assert state_a_after.agent_states.liuyao["status"] == "COMPLETED"
    # Session B 无任何六爻线程引用（未被 Session A 污染；latest_output 仅为 NEEDS_INPUT 回执）
    assert "thread_id" not in state_b_after.agent_states.liuyao
    assert "status" not in state_b_after.agent_states.liuyao


@pytest.mark.asyncio
async def test_bazi_memory_prefill_after_restart(postgres_session_factory):
    """
    Memory Selector 集成验收：
    - 首次八字请求无出生资料 -> NEEDS_INPUT；
    - 用户明确提供并持久化出生资料（模拟重启）；
    - 再次请求 -> 长期记忆预填 -> 直接 READY，Adapter 收到已恢复的 BirthProfile。
    """
    session_id = f"acc-bazi-{uuid.uuid4().hex[:8]}"
    selector = MemorySelector(postgres_session_factory)
    bazi_adapter = FakeSingleAdapter(FakeOutput(content="八字解析完成"))
    table = {"我的八字怎么样": bazi_routing()}
    adapters = {IntentType.BAZI: bazi_adapter}

    orch_a = build_orchestrator(
        postgres_session_factory,
        table,
        adapters,
        memory_selector=selector,
    )
    await orch_a.execute(session_id, "我的八字怎么样")

    # 首次：没有出生资料 -> 需要用户输入（而非执行 Agent）
    state_a = await orch_a._memory_store.load(session_id)
    assert state_a.requirement_result.status == RequirementStatus.NEEDS_INPUT
    assert bazi_adapter.invocation_count == 0

    # 用户明确提供出生资料（更正语义：后续更正覆盖）
    profile = BirthProfile(
        year=1992, month=8, day=18, hour=10, minute=0, gender=Gender.MALE
    )
    await selector.persist_birth_profile(session_id, profile)

    # 模拟重启：全新 Orchestrator，同一 session，同一 Memory Selector
    orch_b = build_orchestrator(
        postgres_session_factory,
        table,
        adapters,
        memory_selector=selector,
    )
    await orch_b.execute(session_id, "我的八字怎么样")

    state_b = await orch_b._memory_store.load(session_id)
    assert state_b.requirement_result.status == RequirementStatus.READY
    assert bazi_adapter.invocation_count == 1
    assert bazi_adapter.invoked_profiles[0].year == 1992

    # 更正出生时间后再次分析 -> 使用更正后的资料
    corrected = BirthProfile(
        year=1992, month=8, day=18, hour=16, minute=30, gender=Gender.MALE
    )
    await selector.persist_birth_profile(session_id, corrected)

    orch_c = build_orchestrator(
        postgres_session_factory,
        table,
        adapters,
        memory_selector=selector,
    )
    await orch_c.execute(session_id, "我的八字怎么样")

    assert bazi_adapter.invocation_count == 2
    assert bazi_adapter.invoked_profiles[-1].hour == 16
