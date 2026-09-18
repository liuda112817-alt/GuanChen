import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from guanchen_v2.liuyao.casting import HexagramCastingService
from guanchen_v2.liuyao.policy import ClarificationAssessment
from guanchen_v2.liuyao.retrieval import LiuyaoRetrievalBuilder
from guanchen_v2.liuyao.workflow import LiuyaoAgentRuntime
from guanchen_v2.llm.client import LLMClient
from guanchen_v2.models.liuyao import (
    CastingMethod,
    DecisionReflection,
    HexagramIdentity,
    HexagramLine,
    HexagramResult,
    LineValue,
    YinYang,
)
from guanchen_v2.router.adapters.liuyao import LiuyaoAgentAdapter
from guanchen_v2.router.contracts import RequiredDataType
from guanchen_v2.router.requirements import RequirementContext


@pytest.fixture
def mock_services():
    casting = MagicMock(spec=HexagramCastingService)
    llm = MagicMock(spec=LLMClient)

    async def mock_generate_structured(*args, **kwargs):
        schema = kwargs.get("schema")
        if schema == ClarificationAssessment:
            return ClarificationAssessment(
                needs_clarification=False,
                clarified_question="确认要离职吗？",
                reality_constraints=[]
            )
        elif schema == DecisionReflection:
            return DecisionReflection(
                situation_summary="情况",
                traditional_reflection="推演",
                reality_check="现实",
                decision_options=["选项"],
                uncertainty_note="免责"
            )
        raise ValueError(f"Unknown schema: {schema}")

    llm.generate_structured = AsyncMock(side_effect=mock_generate_structured)
    
    lines = tuple(
        HexagramLine(
            position=i, value=LineValue.YOUNG_YANG, polarity=YinYang.YANG, moving=False,
            heavenly_stem="甲", earthly_branch="子", element="水", six_relative="父母",
            is_shi=False, is_ying=False
        )
        for i in range(1, 7)
    )
    mock_hex = HexagramResult(
        casting_method=CastingMethod.MANUAL_SIX_LINES,
        lines=lines,
        primary_hexagram=HexagramIdentity(name="乾", upper_trigram="乾", lower_trigram="乾"),
        changed_hexagram=None,
        moving_line_positions=[],
        coin_tosses=[]
    )
    
    casting.cast_random.return_value = mock_hex
    casting.cast_manual.return_value = mock_hex
    
    retrieval = MagicMock(spec=LiuyaoRetrievalBuilder)
    retrieval.retrieve = AsyncMock(return_value=[])
    
    return casting, llm, retrieval


@pytest.mark.asyncio
async def test_1_2_3_create_interrupt_resume(mock_services):
    casting, llm, retrieval = mock_services
    shared_saver = InMemorySaver()

    # ====== 阶段一：新请求发起 (Test 1 & Test 2) ======
    runtime1 = LiuyaoAgentRuntime(casting, llm, retrieval, checkpointer=shared_saver)
    adapter1 = LiuyaoAgentAdapter(runtime1)
    
    agent_state = {}
    ctx = RequirementContext(available_data={RequiredDataType.DECISION_QUESTION: "测辞职"})
    
    await adapter1.invoke("测辞职", ctx, agent_state)
    
    # Test 1: 验证 ConversationState 中已经具备了 thread_id
    assert "thread_id" in agent_state
    thread_id = agent_state["thread_id"]
    
    # Test 2: 验证到达确认节点并发生了 Interrupt Persistence
    assert agent_state["status"] == "INTERRUPTED"
    assert agent_state["pending_node"] == "confirmation"

    # ====== 阶段二：模拟进程重启后的第二个恢复请求 (Test 3) ======
    runtime2 = LiuyaoAgentRuntime(casting, llm, retrieval, checkpointer=shared_saver)
    adapter2 = LiuyaoAgentAdapter(runtime2)
    
    confirm_payload = json.dumps({"action": "confirm"})
    await adapter2.invoke(confirm_payload, ctx, agent_state)
    
    # Test 3: Resume 成功恢复后跑完所有节点，Thread 不变
    assert agent_state["status"] == "COMPLETED"
    assert agent_state["thread_id"] == thread_id
    assert "pending_node" not in agent_state


@pytest.mark.asyncio
async def test_4_session_isolation(mock_services):
    """Test 4: Session Isolation (不同 Session 绝对不产生交叉污染的 Thread)"""
    casting, llm, retrieval = mock_services
    runtime = LiuyaoAgentRuntime(casting, llm, retrieval, checkpointer=InMemorySaver())
    adapter = LiuyaoAgentAdapter(runtime)
    
    ctx = RequirementContext(available_data={RequiredDataType.DECISION_QUESTION: "测辞职"})
    
    agent_state_a = {}
    agent_state_b = {}
    
    await adapter.invoke("测辞职 A", ctx, agent_state_a)
    await adapter.invoke("测辞职 B", ctx, agent_state_b)
    
    assert agent_state_a["thread_id"] != agent_state_b["thread_id"]


@pytest.mark.asyncio
async def test_5_missing_thread_recovery(mock_services):
    """Test 5: Missing Thread Recovery (发生意外导致 state 丢失 thread 时，能安全拉起新 thread)"""
    casting, llm, retrieval = mock_services
    runtime = LiuyaoAgentRuntime(casting, llm, retrieval, checkpointer=InMemorySaver())
    adapter = LiuyaoAgentAdapter(runtime)
    
    ctx = RequirementContext(available_data={RequiredDataType.DECISION_QUESTION: "测辞职"})
    agent_state = {}
    
    await adapter.invoke("测辞职", ctx, agent_state)
    original_thread = agent_state["thread_id"]
    
    # 手动破坏 State，模拟信息丢失
    del agent_state["thread_id"]
    
    # 修复验证 3：此时再次调用，应触发重新起步，不会出现 KeyError: 'question' 崩溃
    await adapter.invoke("测辞职", ctx, agent_state)
    new_thread = agent_state["thread_id"]
    
    assert new_thread != original_thread

