from typing import Protocol

from pydantic import BaseModel, ConfigDict, model_validator

from guanchen_v2.safety.models import RiskDomain, RiskLevel, SafetyAction


class SafetyClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_domain: RiskDomain
    risk_level: RiskLevel
    recommended_action: SafetyAction
    reason_code: str

    @model_validator(mode="after")
    def validate_final_action(self) -> "SafetyClassification":
        if self.recommended_action == SafetyAction.REQUIRE_CLASSIFIER:
            raise ValueError("Safety classifier must return a final action")
        return self


class SafetyClassifier(Protocol):
    async def classify(self, text: str) -> SafetyClassification: ...
