from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)

NonBlankText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class DreamElements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    people: list[NonBlankText] = Field(default_factory=list)
    scenes: list[NonBlankText] = Field(default_factory=list)
    objects: list[NonBlankText] = Field(default_factory=list)
    actions: list[NonBlankText] = Field(default_factory=list)
    emotions: list[NonBlankText] = Field(default_factory=list)
    anomalies: list[NonBlankText] = Field(default_factory=list)
    subjective_feelings: list[NonBlankText] = Field(default_factory=list)


class RealityBackground(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recent_events: list[NonBlankText] = Field(default_factory=list)

    ongoing_contexts: list[NonBlankText] = Field(default_factory=list)

    stressors: list[NonBlankText] = Field(default_factory=list)

    user_associations: list[NonBlankText] = Field(default_factory=list)


class InterpretationStatus(StrEnum):
    NOT_STARTED = "not_started"
    CURRENT = "current"
    STALE = "stale"


class DreamInterpretationState(BaseModel):
    status: InterpretationStatus = InterpretationStatus.NOT_STARTED
    last_interpreted_revision: int | None = None


class DreamRecord(BaseModel):
    dream_id: UUID = Field(default_factory=uuid4)
    raw_descriptions: list[str] = Field(default_factory=list)
    elements: DreamElements = Field(default_factory=DreamElements)
    reality_background: RealityBackground = Field(default_factory=RealityBackground)
    interpretation_state: DreamInterpretationState = Field(default_factory=DreamInterpretationState)
    revision: int = 1


class DreamField(StrEnum):
    PEOPLE = "elements.people"
    SCENES = "elements.scenes"
    OBJECTS = "elements.objects"
    ACTIONS = "elements.actions"
    EMOTIONS = "elements.emotions"
    ANOMALIES = "elements.anomalies"
    SUBJECTIVE_FEELINGS = "elements.subjective_feelings"

    RECENT_EVENTS = "reality_background.recent_events"
    ONGOING_CONTEXTS = "reality_background.ongoing_contexts"
    STRESSORS = "reality_background.stressors"
    USER_ASSOCIATIONS = "reality_background.user_associations"


class DreamCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: DreamField = Field(description="需要修正的当前梦境状态字段")
    old_value: NonBlankText = Field(description="CURRENT DREAM CONTEXT 中实际存在的旧值")
    new_value: NonBlankText | None = Field(default=None, description="明确替代值；明确删除时为 null")


class DreamPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    element_additions: DreamElements = Field(
        default_factory=DreamElements, description="本轮新增的梦境要素，不包含当前上下文已存在的信息"
    )
    background_additions: RealityBackground = Field(
        default_factory=RealityBackground, description="本轮新增的用户明确现实背景"
    )
    corrections: list[DreamCorrection] = Field(
        default_factory=list, description="用户本轮明确提出的已有状态更正或删除"
    )


class DreamTurnBoundary(StrEnum):
    SAME = "same"
    NEW = "new"
    NEEDS_CLARIFICATION = "needs_clarification"


class DreamContextStatus(StrEnum):
    UPDATED = "updated"
    NEEDS_CLARIFICATION = "needs_clarification"


class DreamContextResult(BaseModel):
    status: DreamContextStatus
    record: DreamRecord
    patch: DreamPatch | None = None
    clarification_question: str | None = None
    started_new_dream: bool = False


class DreamRetrievalAspect(StrEnum):
    SYMBOL = "symbol"
    EMOTION = "emotion"
    REALITY_CONTEXT = "reality_context"


class DreamRetrievalQuery(BaseModel):
    aspect: DreamRetrievalAspect
    query: NonBlankText
