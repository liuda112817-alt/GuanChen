from unittest.mock import AsyncMock

import pytest

from guanchen_v2.safety.classifier import SafetyClassification
from guanchen_v2.safety.llm_classifier import LLMSafetyClassifier
from guanchen_v2.safety.models import RiskDomain, RiskLevel, SafetyAction


@pytest.mark.asyncio
async def test_llm_classifier_calls_generate_structured():
    mock_llm = AsyncMock()
    mock_llm.generate_structured.return_value = SafetyClassification(
        risk_domain=RiskDomain.MEDICAL, risk_level=RiskLevel.HIGH_RISK, recommended_action=SafetyAction.SAFE_RESPONSE, reason_code="MOCK"
    )

    classifier = LLMSafetyClassifier(mock_llm)
    result = await classifier.classify("医生让我做手术")

    assert mock_llm.generate_structured.call_count == 1
    kwargs = mock_llm.generate_structured.call_args.kwargs
    assert kwargs["schema"] == SafetyClassification
    assert "医生让我做手术" in kwargs["user_prompt"]
    assert result.risk_domain == RiskDomain.MEDICAL
