from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class IntentType(StrEnum):
    BAZI = "bazi"
    DREAM = "dream"
    LIUYAO = "liuyao"
    KNOWLEDGE = "knowledge"
    CHITCHAT = "chitchat"
    OUT_OF_SCOPE = "out_of_scope"


class RequiredDataType(StrEnum):
    BIRTH_PROFILE = "birth_profile"
    DREAM_CONTENT = "dream_content"
    DECISION_QUESTION = "decision_question"


INTENT_REQUIRED_DATA: dict[IntentType, tuple[RequiredDataType, ...]] = {
    IntentType.BAZI: (RequiredDataType.BIRTH_PROFILE,),
    IntentType.DREAM: (RequiredDataType.DREAM_CONTENT,),
    IntentType.LIUYAO: (RequiredDataType.DECISION_QUESTION,),
    IntentType.KNOWLEDGE: (),
    IntentType.CHITCHAT: (),
    IntentType.OUT_OF_SCOPE: (),
}

NonBlankRouteText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class RoutingResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    primary_intent: IntentType

    secondary_intents: tuple[IntentType, ...] = Field(
        default_factory=tuple,
        max_length=1,
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    required_data: tuple[RequiredDataType, ...] = Field(
        default_factory=tuple,
    )

    reason: NonBlankRouteText

    @model_validator(mode="after")
    def validate_invariants(self) -> "RoutingResult":
        if self.primary_intent in self.secondary_intents:
            raise ValueError("primary_intent 不能出现在 secondary_intents 中")

        non_combinable = {IntentType.CHITCHAT, IntentType.OUT_OF_SCOPE}

        if self.primary_intent in non_combinable and self.secondary_intents:
            raise ValueError(f"当 primary_intent 为 {self.primary_intent.value} 时，secondary_intents 必须为空")

        for sec in self.secondary_intents:
            if sec in non_combinable:
                raise ValueError(f"secondary_intents 不能包含 {sec.value}")

        expected_reqs = set(INTENT_REQUIRED_DATA[self.primary_intent])
        for sec in self.secondary_intents:
            expected_reqs.update(INTENT_REQUIRED_DATA[sec])

        actual_reqs = self.required_data

        if len(actual_reqs) != len(set(actual_reqs)):
            raise ValueError("required_data 不允许包含重复项")

        if set(actual_reqs) != expected_reqs:
            expected_sorted = sorted([e.value for e in expected_reqs])
            actual_sorted = sorted([a.value for a in actual_reqs])
            raise ValueError(f"required_data 必须严格匹配意图所要求的数据集合。预期: {expected_sorted}，实际: {actual_sorted}")

        return self
