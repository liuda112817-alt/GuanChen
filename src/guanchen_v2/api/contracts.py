from enum import StrEnum
from typing import Annotated
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from guanchen_v2.agents.bazi.models import BaziBirthDataPatch
from guanchen_v2.models.bazi import BirthProfile
from guanchen_v2.router.contracts import IntentType, RequiredDataType
from guanchen_v2.safety.models import SafetyDecision

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12000)]


class ChatStatus(StrEnum):
    ANSWERED = "answered"
    NEEDS_INPUT = "needs_input"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    ERROR = "error"


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: NonBlankText | None = None
    message: NonBlankText = Field(description="用户输入的请求文本")
    new_task: bool = False
    birth_profile: BaziBirthDataPatch | None = None


class CitationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str
    document_id: str
    source_title: str
    section: str


class InputRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: RequiredDataType
    fields: tuple[str, ...] = ()


class InterruptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    thread_id: NonBlankText
    prompt: str
    confirmation_id: str = Field(default_factory=lambda: uuid4().hex)


class ResumeAction(StrEnum):
    CONFIRM = "confirm"
    CANCEL = "cancel"
    MODIFY = "modify"


class ResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: NonBlankText
    thread_id: NonBlankText
    action: ResumeAction
    confirmation_id: NonBlankText
    modification: NonBlankText | None = None

    @model_validator(mode="after")
    def validate_modification(self):
        if (self.action == ResumeAction.MODIFY) != (self.modification is not None):
            raise ValueError("modification is required only for modify")
        return self


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: NonBlankText
    birth_profile: BaziBirthDataPatch

    @model_validator(mode="after")
    def validate_not_empty(self) -> "ProfileUpdateRequest":
        if not self.birth_profile.model_fields_set:
            raise ValueError("birth_profile must contain at least one field to update")
        return self


class ProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    birth_profile: BirthProfile | None
    supplied_fields: dict = Field(default_factory=dict)


class SessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    session_token: str | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: NonBlankText
    status: ChatStatus
    content: str
    used_intents: tuple[IntentType, ...] = ()
    citations: tuple[CitationResponse, ...] = ()
    required_input: InputRequirement | None = None
    interrupt: InterruptResponse | None = None
    safety: SafetyDecision | None = None
    session_token: str | None = None
    trace_id: str | None = None
    facts: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_state_consistency(self) -> "ChatResponse":
        if self.status == ChatStatus.NEEDS_INPUT and self.required_input is None:
            raise ValueError("required_input must be present when status is NEEDS_INPUT")
        if self.status == ChatStatus.INTERRUPTED and self.interrupt is None:
            raise ValueError("interrupt must be present when status is INTERRUPTED")
        if self.status == ChatStatus.BLOCKED:
            if self.safety is None:
                raise ValueError("safety must be present when status is BLOCKED")
            # 兼容直接比较 Enum 或 提取 string
            if getattr(self.safety.action, "value", self.safety.action) != "safe_response":
                raise ValueError("safety.action must be SAFE_RESPONSE when status is BLOCKED")
        if self.status in {ChatStatus.ANSWERED, ChatStatus.CANCELLED}:
            if self.required_input is not None or self.interrupt is not None:
                raise ValueError(f"{self.status} status should not carry required_input or interrupt")
        return self


class APIErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    trace_id: str | None = None


class SessionDetailResponse(BaseModel):
    session_id: str
    messages: list[dict] = Field(default_factory=list)
    last_response: ChatResponse | None = None
    interrupt: InterruptResponse | None = None


class CitationDetailResponse(CitationResponse):
    text: str
