"""Stage 8 必测 2：LangGraph HITL 跨进程恢复（PostgreSQL checkpointer）。

验收点：
- 六爻流程 interrupt 后模拟进程重建，再用同 thread_id resume；
- LangGraph interrupted workflow 可跨进程 resume（官方 AsyncPostgresSaver）。
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from psycopg_pool import AsyncConnectionPool

from guanchen_v2.liuyao.casting import HexagramCastingService
from guanchen_v2.liuyao.policy import ClarificationAssessment
from guanchen_v2.liuyao.retrieval import LiuyaoRetrievalBuilder
from guanchen_v2.liuyao.state import create_initial_liuyao_state
from guanchen_v2.liuyao.workflow import LiuyaoAgentRuntime
from guanchen_v2.llm.client import LLMClient
from guanchen_v2.memory.checkpointer import to_psycopg_conninfo
from guanchen_v2.models.liuyao import (
    CastingMethod,
    CoinToss,
    DecisionQuestionStatus,
    DecisionReflection,
    HexagramIdentity,
    HexagramLine,
    HexagramResult,
    LineValue,
    YinYang,
)
from tests.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.integration


def build_mock_services():
    casting = MagicMock(spec=HexagramCastingService)

    lines = tuple(
        HexagramLine(
            position=i,
            value=LineValue.YOUNG_YANG,
            polarity=YinYang.YANG,
            moving=False,
            heavenly_stem="甲",
            earthly_branch="子",
            element="水",
            six_relative="父母",
        )
        for i in range(1, 7)
    )
    mock_hex = HexagramResult(
        casting_method=CastingMethod.SYSTEM_THREE_COIN,
        lines=lines,
        primary_hexagram=HexagramIdentity(name="乾", upper_trigram="乾", lower_trigram="乾"),
        changed_hexagram=None,
        moving_line_positions=[],
        coin_tosses=[
            CoinToss(
                position=i,
                # 3+2+2=7 => 少阳（Young Yang），与 line_value 严格一致
                coins=("head", "tail", "tail"),
                line_value=LineValue.YOUNG_YANG,
            )
            for i in range(1, 7)
        ],
    )
    casting.cast_random.return_value = mock_hex
    casting.cast_manual.return_value = mock_hex

    llm = MagicMock(spec=LLMClient)

    async def mock_generate_structured(*args, **kwargs):
        schema = kwargs.get("schema")
        if schema == ClarificationAssessment:
            return ClarificationAssessment(
                needs_clarification=False,
                clarified_question="确认要离职吗？",
                reality_constraints=[],
            )
        if schema == DecisionReflection:
            return DecisionReflection(
                situation_summary="情况",
                traditional_reflection="推演",
                reality_check="现实",
                decision_options=["选项"],
                uncertainty_note="免责",
            )
        raise ValueError(f"Unknown schema: {schema}")

    llm.generate_structured = AsyncMock(side_effect=mock_generate_structured)

    retrieval = MagicMock(spec=LiuyaoRetrievalBuilder)
    retrieval.retrieve = AsyncMock(return_value=[])

    return casting, llm, retrieval


async def open_saver() -> tuple[AsyncPostgresSaver, AsyncConnectionPool]:
    pool = AsyncConnectionPool(
        conninfo=to_psycopg_conninfo(TEST_DATABASE_URL),
        kwargs={"autocommit": True},
        open=False,
    )
    await pool.open()
    saver = AsyncPostgresSaver(pool)
    await saver.setup()
    return saver, pool


@pytest.mark.asyncio
async def test_liuyao_hitl_cross_process_resume(db_env):
    """进程 A 挂起 -> 进程彻底重建 -> 进程 B 用同 thread_id resume 完成全流程。"""
    casting, llm, retrieval = build_mock_services()
    thread_id = "liuyao_cross_process_resume_1"
    config = {"configurable": {"thread_id": thread_id}}

    # ====== 进程 A：首次执行，停在 confirmation interrupt ======
    saver_a, pool_a = await open_saver()
    runtime_a = LiuyaoAgentRuntime(
        casting_service=casting,
        llm_client=llm,
        retrieval_builder=retrieval,
        checkpointer=saver_a,
    )
    graph_a = runtime_a.build_graph()

    initial = create_initial_liuyao_state("我该不该辞职")
    await graph_a.ainvoke(initial, config)

    state_a = await graph_a.aget_state(config)
    assert state_a.next == ("confirmation",)
    assert state_a.values["question"].status == DecisionQuestionStatus.PENDING_CONFIRMATION
    assert casting.cast_random.call_count == 0  # 确认前禁止起卦

    # 进程 A 关闭（模拟服务彻底重启）
    await pool_a.close()

    # ====== 进程 B：全新 runtime + 全新 saver，同一数据库 / 同一 thread_id ======
    saver_b, pool_b = await open_saver()
    runtime_b = LiuyaoAgentRuntime(
        casting_service=casting,
        llm_client=llm,
        retrieval_builder=retrieval,
        checkpointer=saver_b,
    )
    graph_b = runtime_b.build_graph()

    final_state = await graph_b.ainvoke(
        Command(resume={"action": "confirm"}),
        config,
    )

    # 验证：基于同一个 thread 恢复了图状态并跑完全部节点
    assert final_state["question"].status == DecisionQuestionStatus.CONFIRMED
    assert final_state["hexagram"] is not None
    assert final_state["final_response"] is not None
    assert casting.cast_random.call_count == 1

    # 进程 B 的 saver 能看到同一个 thread（未新建线程）
    threads = [c async for c in saver_b.alist({"configurable": {"thread_id": thread_id}})]
    assert any(t.config["configurable"]["thread_id"] == thread_id for t in threads)

    await pool_b.close()


@pytest.mark.asyncio
async def test_liuyao_cancel_after_restart(db_env):
    """进程重建后拒绝确认（cancel）也能正确走到 END。"""
    casting, llm, retrieval = build_mock_services()
    thread_id = "liuyao_cross_process_cancel_1"
    config = {"configurable": {"thread_id": thread_id}}

    saver_a, pool_a = await open_saver()
    runtime_a = LiuyaoAgentRuntime(casting, llm, retrieval, checkpointer=saver_a)
    graph_a = runtime_a.build_graph()
    await graph_a.ainvoke(create_initial_liuyao_state("要不要投资"), config)
    await pool_a.close()

    saver_b, pool_b = await open_saver()
    runtime_b = LiuyaoAgentRuntime(casting, llm, retrieval, checkpointer=saver_b)
    graph_b = runtime_b.build_graph()

    final_state = await graph_b.ainvoke(Command(resume={"action": "cancel"}), config)

    assert final_state["question"].status == DecisionQuestionStatus.CANCELLED
    assert casting.cast_random.call_count == 0  # 取消后绝不触发起卦
    await pool_b.close()
