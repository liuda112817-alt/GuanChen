from guanchen_v2.safety.models import RiskLevel, SafetyAction
from guanchen_v2.safety.rules import SafetyRuleEngine
from tests.safety.fixtures import AMBIGUOUS_CASES, CRISIS_CASES, MEDICAL_HIGH_RISK_CASES, SAFE_CASES


def test_rule_engine_allows_safe_cases():
    engine = SafetyRuleEngine()
    for case in SAFE_CASES:
        result = engine.evaluate(case)
        assert result is not None  # 不允许被错当成敏感词
        assert result.action == SafetyAction.ALLOW


def test_rule_engine_blocks_crisis():
    engine = SafetyRuleEngine()
    for case in CRISIS_CASES:
        result = engine.evaluate(case)
        assert result is not None
        assert result.risk_level == RiskLevel.CRISIS
        assert result.action == SafetyAction.SAFE_RESPONSE


def test_rule_engine_delegates_sensitive_cases():
    engine = SafetyRuleEngine()

    for case in MEDICAL_HIGH_RISK_CASES[:2]:
        result = engine.evaluate(case)
        assert result.action == SafetyAction.SAFE_RESPONSE
        assert result.reason_code == "RULE_EXTREME_MEDICAL_DECISION"

    assert engine.evaluate(MEDICAL_HIGH_RISK_CASES[2]).action == SafetyAction.REQUIRE_CLASSIFIER

    for case in AMBIGUOUS_CASES:
        result = engine.evaluate(case)
        assert result is not None
        assert result.action == SafetyAction.REQUIRE_CLASSIFIER
