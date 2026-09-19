from unittest.mock import AsyncMock

import pytest

from guanchen_v2.safety.classifier import SafetyClassification
from guanchen_v2.safety.models import RiskDomain, RiskLevel, SafetyAction
from guanchen_v2.safety.rules import SafetyRuleEngine
from guanchen_v2.safety.service import SafetyService
from tests.safety.fixtures import INVESTMENT_HIGH_RISK_CASES, MEDICAL_HIGH_RISK_CASES


@pytest.mark.asyncio
async def test_service_uses_rule_first_for_safe():
    rule_engine = SafetyRuleEngine()
    classifier = AsyncMock()
    service = SafetyService(rule_engine, classifier)

    decision = await service.evaluate("你好，聊聊天")
    assert decision.action == SafetyAction.ALLOW
    assert decision.classifier_used is False
    assert classifier.classify.call_count == 0


@pytest.mark.asyncio
async def test_service_fallback_conservative_when_classifier_absent():
    rule_engine = SafetyRuleEngine()
    service = SafetyService(rule_engine, classifier=None)

    # "病"会触发医疗分类请求，但由于分类器不存在，应触发 fail-closed 逻辑
    decision = await service.evaluate("我体检查出结节，帮我算算是癌吗")
    assert decision.action == SafetyAction.SAFE_RESPONSE
    assert decision.classifier_used is False
    assert decision.user_message == "我不能提供医疗诊断或建议。如果存在健康问题，请及时就医咨询专业医生。"
    assert decision.reason_code == "FALLBACK_CLASSIFIER_UNAVAILABLE"


@pytest.mark.asyncio
@pytest.mark.parametrize("text", MEDICAL_HIGH_RISK_CASES)
async def test_service_evaluates_medical_high_risk(text):
    rule_engine = SafetyRuleEngine()
    classifier = AsyncMock()
    classifier.classify.return_value = SafetyClassification(
        risk_domain=RiskDomain.MEDICAL,
        risk_level=RiskLevel.HIGH_RISK,
        recommended_action=SafetyAction.SAFE_RESPONSE,
        reason_code="MOCK_MEDICAL_CRITICAL",
    )
    service = SafetyService(rule_engine, classifier)

    decision = await service.evaluate(text)
    rule_blocked = rule_engine.evaluate(text).action == SafetyAction.SAFE_RESPONSE
    assert decision.classifier_used is not rule_blocked
    assert classifier.classify.call_count == (0 if rule_blocked else 1)
    assert decision.action == SafetyAction.SAFE_RESPONSE
    assert "医疗诊断" in decision.user_message


@pytest.mark.asyncio
@pytest.mark.parametrize("text", INVESTMENT_HIGH_RISK_CASES)
async def test_service_evaluates_investment_high_risk(text):
    rule_engine = SafetyRuleEngine()
    classifier = AsyncMock()
    classifier.classify.return_value = SafetyClassification(
        risk_domain=RiskDomain.INVESTMENT,
        risk_level=RiskLevel.HIGH_RISK,
        recommended_action=SafetyAction.SAFE_RESPONSE,
        reason_code="MOCK_INVESTMENT_CRITICAL",
    )
    service = SafetyService(rule_engine, classifier)

    decision = await service.evaluate(text)
    assert decision.classifier_used is False
    assert classifier.classify.call_count == 0
    assert decision.action == SafetyAction.SAFE_RESPONSE
    assert "投资建议" in decision.user_message
