from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from guanchen_v2.core.session.enums import SessionStatus
from guanchen_v2.core.session.models import (
    AgentStateContainer,
    ConversationState,
    MessageState,
    PendingInterrupt,
    SessionMetadata,
)
from guanchen_v2.router.contracts import IntentType, RequiredDataType, RoutingResult
from guanchen_v2.router.requirements import RequirementCheckResult, RequirementStatus


def test_1_create_session():
    state = ConversationState(session_id="session-xxx")
    assert state.session_id == "session-xxx"
    assert state.status == SessionStatus.ACTIVE
    assert state.metadata.created_at.tzinfo == timezone.utc

    with pytest.raises(ValidationError):
        ConversationState(session_id=None)

def test_2_serialization_round_trip():
    state = ConversationState(
        session_id="session-123",
        status=SessionStatus.WAITING_INPUT,
        messages=[
            MessageState(
                role="user", 
                content="帮我分析八字", 
                timestamp=datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
            )
        ],
        current_query="帮我分析八字",
        metadata=SessionMetadata(
            trace_id="trace-001",
            extra={"runtime_flag": True}
        )
    )

    json_data = state.model_dump_json()
    restored_state = ConversationState.model_validate_json(json_data)

    assert restored_state.session_id == "session-123"
    assert restored_state.status == SessionStatus.WAITING_INPUT
    assert len(restored_state.messages) == 1
    assert restored_state.messages[0].timestamp.tzinfo == timezone.utc
    assert restored_state.metadata.extra["runtime_flag"] is True

def test_3_agent_namespace_isolation():
    """
    Test 3: 验证结构级的 Namespace 隔离。
    ADR 记录：Application层不再审查 Agent 内部字典的键值对。
    """
    state = ConversationState(
        session_id="test",
        agent_states=AgentStateContainer(
            dream={"record": {"id": 1}},
            liuyao={"step": "cast"}
        )
    )
    assert state.agent_states.dream["record"]["id"] == 1
    
    # 验证 Pydantic ConfigDict 拦截野生高层级命名空间
    with pytest.raises(ValidationError):
        ConversationState(
            session_id="test",
            agent_states={"unknown_agent": {}}
        )

def test_4_reject_runtime_object():
    class ChatModel:
        pass

    with pytest.raises(ValidationError, match="禁止包含 Runtime Object"):
        ConversationState(
            session_id="test",
            agent_states=AgentStateContainer(
                bazi={"client": ChatModel()}
            )
        )

def test_5_pending_interrupt_recovery():
    interrupt = PendingInterrupt(
        agent="liuyao",
        interrupt_type="confirmation_required",
        payload={"question": "是否确认起卦"},
        created_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    )
    state = ConversationState(session_id="test", pending_interrupt=interrupt)
    
    json_str = state.model_dump_json()
    restored = ConversationState.model_validate_json(json_str)
    
    assert restored.pending_interrupt.interrupt_type == "confirmation_required"
    assert restored.pending_interrupt.payload["question"] == "是否确认起卦"
    assert restored.pending_interrupt.created_at.tzinfo == timezone.utc

def test_routing_result_round_trip():
    """Test 8: RoutingResult / RequirementResult serialization"""
    state = ConversationState(
        session_id="test-routing",
        routing_result=RoutingResult(
            primary_intent=IntentType.BAZI,
            secondary_intents=(),
            confidence=0.95,
            required_data=(RequiredDataType.BIRTH_PROFILE,),
            reason="显式请求八字排盘"
        ),
        requirement_result=RequirementCheckResult(
            intent=IntentType.BAZI,
            status=RequirementStatus.NEEDS_INPUT,
            required_data=(RequiredDataType.BIRTH_PROFILE,),
            missing_data=(RequiredDataType.BIRTH_PROFILE,)
        )
    )

    json_str = state.model_dump_json()
    restored = ConversationState.model_validate_json(json_str)

    assert restored.routing_result is not None
    assert restored.routing_result.primary_intent == IntentType.BAZI
    assert restored.routing_result.required_data == (RequiredDataType.BIRTH_PROFILE,)

    assert restored.requirement_result is not None
    assert restored.requirement_result.status == RequirementStatus.NEEDS_INPUT
    assert restored.requirement_result.missing_data == (RequiredDataType.BIRTH_PROFILE,)

