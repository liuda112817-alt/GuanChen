"""Stage 8 域记录持久化：DreamRecord / DecisionRecord 跨进程可恢复。"""
from unittest.mock import MagicMock

import pytest

from guanchen_v2.dream.retrieval import DreamRetrievalService
from guanchen_v2.dream.runtime import DreamAgentRuntime
from guanchen_v2.llm.client import LLMClient
from guanchen_v2.memory.stores import (
    PostgresDecisionRecordStore,
    PostgresDreamRecordStore,
)
from guanchen_v2.models.dream import DreamContextStatus, DreamRecord
from guanchen_v2.models.liuyao import (
    DecisionQuestion,
    DecisionQuestionStatus,
    DecisionRecord,
)

pytestmark = pytest.mark.integration


def make_decision_record(thread_id: str = "liuyao_thread_x") -> DecisionRecord:
    return DecisionRecord(
        question=DecisionQuestion(
            original_question="要不要换工作",
            clarified_question="今年要不要换工作",
            status=DecisionQuestionStatus.CONFIRMED,
        ),
        thread_id=thread_id,
        status=DecisionQuestionStatus.CONFIRMED,
        final_response="参考推演",
    )


@pytest.mark.asyncio
async def test_dream_record_round_trip_across_restart(postgres_session_factory):
    """DreamRecord 写入 -> 新 store 实例（模拟重启）读取，内容完整。"""
    user_id = "user-dream-1"
    store_a = PostgresDreamRecordStore(user_id, postgres_session_factory)

    record = DreamRecord()
    record.raw_descriptions.append("梦见在旧教学楼里迷路")
    record.elements.objects.append("旧教学楼")
    record.elements.emotions.append("焦虑")

    await store_a.save(record)

    # 模拟应用重启：全新 store 实例 + 全新 repository
    store_b = PostgresDreamRecordStore(user_id, postgres_session_factory)
    recovered = await store_b.load_latest()

    assert recovered is not None
    assert recovered.dream_id == record.dream_id
    assert recovered.raw_descriptions == record.raw_descriptions
    assert recovered.elements.objects == ["旧教学楼"]
    assert recovered.elements.emotions == ["焦虑"]


@pytest.mark.asyncio
async def test_decision_record_round_trip_across_restart(postgres_session_factory):
    """DecisionRecord 写入 -> 新 store 实例读取（含 thread_id 引用）。"""
    user_id = "user-decision-1"
    store_a = PostgresDecisionRecordStore(user_id, postgres_session_factory)

    record = make_decision_record(thread_id="liuyao_thread_recovery")
    await store_a.save(record)

    store_b = PostgresDecisionRecordStore(user_id, postgres_session_factory)
    recovered = await store_b.load_latest()

    assert recovered is not None
    assert recovered.record_id == record.record_id
    assert recovered.thread_id == "liuyao_thread_recovery"
    assert recovered.question.clarified_question == "今年要不要换工作"
    assert recovered.status == DecisionQuestionStatus.CONFIRMED


@pytest.mark.asyncio
async def test_dream_runtime_restores_record_after_restart(postgres_session_factory):
    """解梦运行时重启后自动恢复当前 DreamRecord 并继续多轮会话（硬门禁）。"""

    class FakeContextService:
        """每轮仅追加描述并进入澄清态（避免触发解释链路，专注验证记忆恢复）。"""

        async def apply_turn(self, user_text, current_record=None):
            record = current_record if current_record is not None else DreamRecord()
            record.raw_descriptions.append(user_text)
            return MagicMock(
                status=DreamContextStatus.NEEDS_CLARIFICATION,
                record=record,
                patch=None,
                clarification_question="请补充更多梦境细节",
                started_new_dream=False,
            )

    context_service = FakeContextService()
    retrieval = MagicMock(spec=DreamRetrievalService)
    retrieval.retrieve.return_value = []
    llm = MagicMock(spec=LLMClient)

    user_id = "user-dream-runtime-1"
    store = PostgresDreamRecordStore(user_id, postgres_session_factory)

    # 进程 A：第一轮
    runtime_a = DreamAgentRuntime(
        context_service=context_service,
        retrieval_service=retrieval,
        llm_client=llm,
        record_store=store,
    )
    result_a = await runtime_a.handle_turn("梦见一条大蛇")
    assert result_a.record.raw_descriptions == ["梦见一条大蛇"]

    # 进程 B：完全新的 runtime（同一 store 绑定同一 user）
    runtime_b = DreamAgentRuntime(
        context_service=context_service,
        retrieval_service=retrieval,
        llm_client=llm,
        record_store=PostgresDreamRecordStore(user_id, postgres_session_factory),
    )
    result_b = await runtime_b.handle_turn("蛇变成了龙")

    # 恢复后继续：raw_descriptions 包含上一轮的梦境描述
    assert result_b.record.raw_descriptions == ["梦见一条大蛇", "蛇变成了龙"]
