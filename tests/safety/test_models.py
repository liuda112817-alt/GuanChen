import pytest
from pydantic import ValidationError

from guanchen_v2.safety.classifier import SafetyClassification
from guanchen_v2.safety.models import RiskDomain, RiskLevel, SafetyAction, SafetyDecision


def test_safety_decision_model():
    decision = SafetyDecision(risk_domain=RiskDomain.NONE, risk_level=RiskLevel.SAFE, action=SafetyAction.ALLOW, reason_code="TEST_OK")
    assert decision.risk_domain == "none"
    assert decision.classifier_used is False
    assert decision.user_message is None

    # 确保没有隐式记录用户的 raw text
    assert not hasattr(decision, "prompt")


def test_classifier_cannot_request_classifier_again():
    with pytest.raises(
        ValidationError,
        match="must return a final action",
    ):
        SafetyClassification(
            risk_domain=RiskDomain.MEDICAL,
            risk_level=RiskLevel.SENSITIVE,
            recommended_action=SafetyAction.REQUIRE_CLASSIFIER,
            reason_code="INVALID",
        )
