from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class RiskDomain(StrEnum):
    NONE = "none"
    SELF_HARM = "self_harm"
    MEDICAL = "medical"
    LEGAL = "legal"
    INVESTMENT = "investment"


class RiskLevel(StrEnum):
    SAFE = "safe"
    SENSITIVE = "sensitive"
    HIGH_RISK = "high_risk"
    CRISIS = "crisis"


class SafetyAction(StrEnum):
    ALLOW = "allow"
    ALLOW_WITH_BOUNDARY = "allow_with_boundary"
    SAFE_RESPONSE = "safe_response"
    REQUIRE_CLASSIFIER = "require_classifier"


class SafetyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_domain: RiskDomain
    risk_level: RiskLevel
    action: SafetyAction
    reason_code: str

    user_message: str | None = None
    classifier_used: bool = False
