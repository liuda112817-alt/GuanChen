from types import SimpleNamespace

import pytest

from guanchen_v2.application.factory import GuanChenApplication
from guanchen_v2.application.orchestrator import ConversationOrchestrator
from guanchen_v2.core.session.models import ConversationState
from guanchen_v2.mcp.server import GuanChenMCPServer
from guanchen_v2.router.contracts import IntentType
from guanchen_v2.router.core import RouterDecision, build_routing_result


@pytest.fixture
def captured_events(monkeypatch):
    """
    直接捕获 Tracer 生成的 ObservabilityEvent。

    不依赖 logging propagation，
    因此生产环境可以安全保持：

        logger.propagate = False

    同时 Runtime Test 只负责验证：
    - trace_id
    - component
    - event_type
    - status

    logger JSON 序列化由 test_logger.py 单独负责。
    """
    events = []

    def capture_event(event):
        events.append(event)
        return "{}"

    monkeypatch.setattr(
        "guanchen_v2.observability.tracer.log_event",
        capture_event,
    )

    return events


@pytest.mark.asyncio
async def test_mcp_runtime_trace_valid_execution(captured_events):
    app = GuanChenMCPServer()
    result = await app._registry.call("calculate_bazi", {"year": 1990, "month": 1, "day": 1, "hour": 12, "minute": 30, "gender": "male"})
    assert not result.is_error
    assert len({e.trace_id for e in captured_events}) == 1
    assert {e.event_type for e in captured_events} >= {"REQUEST", "TOOL_CALL", "SERVICE_CALL", "TOOL"}


@pytest.mark.asyncio
async def test_mcp_runtime_trace_invalid_execution(captured_events):
    app = GuanChenMCPServer()
    result = await app._registry.call("calculate_bazi", {"gender": "invalid"})
    assert result.is_error
    assert app.metrics.get_counter("mcp_error_total") == 2
    assert all(e.status == "FAILED" for e in captured_events)


class FakeRouter:
    """
    Application Runtime Test 用 Router。

    不执行 LLM，仅返回固定 RoutingResult。
    """

    async def route(self, query: str):
        return build_routing_result(
            RouterDecision(
                primary_intent=IntentType.CHITCHAT,
                confidence=1.0,
                reason="observability test route",
            )
        )


class FakeSessionRuntime:
    """
    用真实 ConversationOrchestrator._route 验证 Router Trace，
    但避免在单元测试中启动 DB / Agent / LLM。
    """

    def __init__(
        self,
        orchestrator: ConversationOrchestrator,
    ):
        self.orchestrator = orchestrator

    async def execute(
        self,
        session_id,
        user_query,
        **kwargs,
    ):
        state = ConversationState(session_id=session_id)

        turn = {
            "conversation": state,
            "query": user_query,
            "birth_patch": None,
            "new_task": False,
        }

        await self.orchestrator._route(turn)

        return SimpleNamespace(
            status="routed",
            session_id=session_id,
        )


@pytest.mark.asyncio
async def test_real_application_and_router_share_trace(
    monkeypatch,
    captured_events,
):
    """
    验证真实：

        GuanChenApplication.execute
            ↓
        ConversationOrchestrator._route

    使用同一 trace_id。

    不创建平行的 Demo ApplicationOrchestrator。
    """

    app = GuanChenApplication(
        settings=object(),
        session_factory=object(),
        checkpointer=object(),
        retrieval=object(),
        # 显式传入 object，
        # 防止测试期间创建真实 LLMClient。
        llm=object(),
    )

    orchestrator = ConversationOrchestrator(
        memory_store=None,
        router=FakeRouter(),
        single_dispatcher=None,
        dual_dispatcher=None,
        synthesizer=None,
        memory_selector=None,
    )

    fake_session_runtime = FakeSessionRuntime(orchestrator)

    monkeypatch.setattr(
        app,
        "for_session",
        lambda session_id: fake_session_runtime,
    )

    result = await app.execute(
        None,
        "observability runtime test",
    )

    assert result.status == "routed"

    application_events = [event for event in captured_events if event.component == "application" and event.event_type == "REQUEST"]

    router_events = [event for event in captured_events if event.component == "router" and event.event_type == "ROUTE"]

    assert len(application_events) == 1
    assert len(router_events) == 1

    # Application Root 和真实 Router
    # 必须继承相同 TraceContext。
    assert application_events[0].trace_id == router_events[0].trace_id

    assert application_events[0].trace_id.startswith("app_")

    assert application_events[0].status == "SUCCESS"
    assert router_events[0].status == "SUCCESS"

    # 验证 Application-scoped MetricsCollector
    # 同时收到 Root 和 Router 指标。
    assert app.metrics.get_counter("application_REQUEST_total") == 1

    assert app.metrics.get_counter("router_ROUTE_total") == 1

    assert app.metrics.get_average_observation("application_REQUEST_latency_ms") > 0

    assert app.metrics.get_average_observation("router_ROUTE_latency_ms") > 0
