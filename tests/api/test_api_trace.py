from unittest.mock import AsyncMock

import pytest

from guanchen_v2.api.contracts import ChatRequest
from guanchen_v2.api.service import ChatApplicationService
from guanchen_v2.observability.integration import get_tracer
from guanchen_v2.router.synthesis import SynthesizedResponse
from guanchen_v2.safety.models import RiskDomain, RiskLevel, SafetyAction, SafetyDecision


@pytest.mark.asyncio
async def test_api_application_trace_sharing():
    """测试 API 层的 Trace 正确透传并成为 Application 和 Safety 的共享 Trace"""

    api_trace_id_in_safety = None
    app_trace_id_in_app = None

    async def mock_evaluate(text):
        nonlocal api_trace_id_in_safety
        tracer = get_tracer()
        if tracer:
            api_trace_id_in_safety = tracer.context.trace_id
        return SafetyDecision(risk_domain=RiskDomain.NONE, risk_level=RiskLevel.SAFE, action=SafetyAction.ALLOW, reason_code="OK")

    class FakeApp:
        async def load_session_state(self, session_id):
            return None

        async def execute(self, session_id, user_query, **kwargs):
            nonlocal app_trace_id_in_app
            tracer = get_tracer()
            if tracer:
                app_trace_id_in_app = tracer.context.trace_id

            return SynthesizedResponse(session_id=session_id, status="answered", content="Test", used_intents=[], citations=[])

    app_mock = FakeApp()
    safety_mock = AsyncMock()
    safety_mock.evaluate.side_effect = mock_evaluate

    service = ChatApplicationService(app_mock, safety_mock)

    # 外部没有任何 trace
    await service.chat(ChatRequest(message="Test trace propagation"))

    assert api_trace_id_in_safety is not None
    assert app_trace_id_in_app is not None
    # 证明 Application 与 API / Safety 完全在同一个 Context Trace_ID 里
    assert api_trace_id_in_safety == app_trace_id_in_app
