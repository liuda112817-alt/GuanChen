from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from guanchen_v2.core.session.enums import SessionStatus
from guanchen_v2.core.session.validators import (
    validate_json_serializable,
    validate_namespace_isolation,
)
from guanchen_v2.router.contracts import RoutingResult
from guanchen_v2.router.dual_requirements import DualRequirementCheckResult
from guanchen_v2.router.requirements import RequirementCheckResult


class MessageState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1)
    content: str = Field(min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in {"user", "assistant", "system"}:
            raise ValueError("Message role 必须是 user, assistant 或 system")
        return v

    @model_validator(mode="after")
    def validate_runtime_objects(self) -> "MessageState":
        validate_json_serializable(self.metadata, path="MessageState.metadata")
        return self


class SessionMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trace_id: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_rules(self) -> "SessionMetadata":
        if "user_personality" in self.extra or "user_preference_prediction" in self.extra:
            raise ValueError("禁止在 metadata 保存 user_personality 或 user_preference_prediction 等用户画像预测信息")

        validate_json_serializable(self.extra, path="SessionMetadata.extra")
        return self


class PendingInterrupt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: str = Field(min_length=1)
    interrupt_type: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_payload(self) -> "PendingInterrupt":
        validate_json_serializable(self.payload, path="PendingInterrupt.payload")
        return self


class AgentStateContainer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bazi: dict[str, Any] = Field(default_factory=dict)
    dream: dict[str, Any] = Field(default_factory=dict)
    liuyao: dict[str, Any] = Field(default_factory=dict)
    knowledge: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_isolation(self) -> "AgentStateContainer":
        validate_json_serializable(self.bazi, path="AgentState.bazi")
        validate_json_serializable(self.dream, path="AgentState.dream")
        validate_json_serializable(self.liuyao, path="AgentState.liuyao")
        validate_json_serializable(self.knowledge, path="AgentState.knowledge")

        validate_namespace_isolation()
        return self


class ConversationState(BaseModel):
    """一个用户 session 在生命周期内为 Application Layer 保存恢复所需状态的统一容器"""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    status: SessionStatus = SessionStatus.ACTIVE
    messages: list[MessageState] = Field(default_factory=list)
    current_query: str | None = None

    routing_result: RoutingResult | None = None
    requirement_result: RequirementCheckResult | DualRequirementCheckResult | None = None

    agent_states: AgentStateContainer = Field(default_factory=AgentStateContainer)
    pending_interrupt: PendingInterrupt | None = None
    pending_query: str | None = None
    birth_data: dict[str, Any] = Field(default_factory=dict)
    metadata: SessionMetadata = Field(default_factory=SessionMetadata)
