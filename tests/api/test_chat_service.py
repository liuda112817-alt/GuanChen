from unittest.mock import AsyncMock

import pytest

from guanchen_v2.agents.bazi.models import BaziBirthDataPatch
from guanchen_v2.api.contracts import ChatRequest, ChatStatus
from guanchen_v2.api.errors import APIApplicationError
from guanchen_v2.api.service import ChatApplicationService
from guanchen_v2.router.synthesis import SynthesizedResponse
from guanchen_v2.safety.models import RiskDomain, RiskLevel, SafetyAction, SafetyDecision


@pytest.mark.asyncio
async def test_service_blocked_by_safety():
    app_mock = AsyncMock()
    app_mock.load_session_state.return_value = None
    app_mock.metrics = None  # 防止触发 AsyncMock 未等待的协程警告
    safety_mock = AsyncMock()
    safety_mock.evaluate.return_value = SafetyDecision(
        risk_domain=RiskDomain.MEDICAL,
        risk_level=RiskLevel.HIGH_RISK,
        action=SafetyAction.SAFE_RESPONSE,
        reason_code="BLOCKED_MOCK",
        user_message="Safety Blocked",
    )
    service = ChatApplicationService(app_mock, safety_mock)

    resp = await service.chat(ChatRequest(message="test"))
    assert resp.status == ChatStatus.BLOCKED
    assert resp.safety.action == SafetyAction.SAFE_RESPONSE
    app_mock.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_allow_calls_execute():
    app_mock = AsyncMock()
    app_mock.metrics = None

    async def mock_execute(**kwargs):
        return SynthesizedResponse(
            session_id=kwargs.get("session_id", "s1"), status="answered", content="answer content", used_intents=[], citations=[]
        )

    app_mock.execute.side_effect = mock_execute
    app_mock.load_session_state.return_value = None

    safety_mock = AsyncMock()
    safety_mock.evaluate.return_value = SafetyDecision(
        risk_domain=RiskDomain.NONE, risk_level=RiskLevel.SAFE, action=SafetyAction.ALLOW, reason_code="ALLOW_MOCK"
    )
    service = ChatApplicationService(app_mock, safety_mock)

    resp = await service.chat(ChatRequest(message="hello"))
    assert resp.status == ChatStatus.ANSWERED
    assert resp.content == "answer content"
    app_mock.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_service_allow_with_boundary_appends_message():
    app_mock = AsyncMock()
    app_mock.metrics = None

    async def mock_execute(**kwargs):
        return SynthesizedResponse(
            session_id=kwargs.get("session_id", "s1"), status="answered", content="answer content", used_intents=[], citations=[]
        )

    app_mock.execute.side_effect = mock_execute
    app_mock.load_session_state.return_value = None

    safety_mock = AsyncMock()
    safety_mock.evaluate.return_value = SafetyDecision(
        risk_domain=RiskDomain.MEDICAL,
        risk_level=RiskLevel.SENSITIVE,
        action=SafetyAction.ALLOW_WITH_BOUNDARY,
        reason_code="BOUNDARY_MOCK",
        user_message="Boundary message",
    )
    service = ChatApplicationService(app_mock, safety_mock)

    resp = await service.chat(ChatRequest(message="hello"))
    assert resp.status == ChatStatus.ANSWERED
    assert "answer content\n\n---\n\nBoundary message" in resp.content


@pytest.mark.asyncio
async def test_service_runtime_error_wraps_in_api_error():
    app_mock = AsyncMock()
    app_mock.load_session_state.return_value = None
    app_mock.metrics = None
    app_mock.execute.side_effect = RuntimeError("App failed")

    safety_mock = AsyncMock()
    safety_mock.evaluate.return_value = SafetyDecision(
        risk_domain=RiskDomain.NONE, risk_level=RiskLevel.SAFE, action=SafetyAction.ALLOW, reason_code="OK"
    )

    service = ChatApplicationService(app_mock, safety_mock)
    with pytest.raises(APIApplicationError) as exc:
        await service.chat(ChatRequest(message="hello"))
    assert exc.value.code == "RUNTIME_ERROR"


@pytest.mark.asyncio
async def test_service_generates_session_id_and_forwards_arguments():
    app_mock = AsyncMock()
    app_mock.metrics = None

    async def mock_execute(**kwargs):
        return SynthesizedResponse(session_id=kwargs["session_id"], status="answered", content="answer", used_intents=[], citations=[])

    app_mock.execute.side_effect = mock_execute
    app_mock.load_session_state.return_value = None

    safety_mock = AsyncMock()
    safety_mock.evaluate.return_value = SafetyDecision(
        risk_domain=RiskDomain.NONE, risk_level=RiskLevel.SAFE, action=SafetyAction.ALLOW, reason_code="OK"
    )

    service = ChatApplicationService(app_mock, safety_mock)
    patch = BaziBirthDataPatch(year=2000)
    req = ChatRequest(message="hello", new_task=True, birth_profile=patch)

    resp = await service.chat(req)

    called_kwargs = app_mock.execute.call_args.kwargs
    generated_session = called_kwargs["session_id"]

    assert generated_session is not None
    assert called_kwargs["new_task"] is True
    assert called_kwargs["birth_patch"] == patch
    assert resp.session_id == generated_session


@pytest.mark.asyncio
async def test_service_rejects_runtime_session_mismatch():
    app_mock = AsyncMock()
    app_mock.load_session_state.return_value = None
    app_mock.metrics = None
    app_mock.execute.return_value = SynthesizedResponse(
        session_id="malicious_hacked_id", status="answered", content="answer", used_intents=[], citations=[]
    )
    safety_mock = AsyncMock()
    safety_mock.evaluate.return_value = SafetyDecision(
        risk_domain=RiskDomain.NONE, risk_level=RiskLevel.SAFE, action=SafetyAction.ALLOW, reason_code="OK"
    )

    service = ChatApplicationService(app_mock, safety_mock)
    req = ChatRequest(session_id="correct_api_session", message="hello")

    with pytest.raises(APIApplicationError) as exc:
        await service.chat(req)

    # 断言真正的引发原因
    assert "inconsistent session_id" in str(exc.value.__cause__)
