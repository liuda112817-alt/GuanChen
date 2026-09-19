from types import SimpleNamespace

import mcp.types as types
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
async def test_mcp_runtime_trace_valid_execution(
    captured_events,
):
    """
    正常 MCP 调用：

    MCP REQUEST
        ↓
    MCP TOOL_CALL
        ↓
    Bazi SERVICE_CALL

    三层必须共享同一个 trace_id。
    """

    app = GuanChenMCPServer()

    call_tool_handler = app.server.request_handlers[
        types.CallToolRequest
    ]

    response = await call_tool_handler(
        types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(
                name="bazi.calculate",
                arguments={
                    "year": 1990,
                    "month": 1,
                    "day": 1,
                    "hour": 12,
                    "minute": 30,
                    "gender": "male",
                },
            ),
        )
    )

    assert response.root.isError is not True

    assert len(captured_events) >= 3

    trace_ids = {
        event.trace_id
        for event in captured_events
    }

    assert len(trace_ids) == 1

    components = {
        event.component
        for event in captured_events
    }

    assert "mcp" in components
    assert "bazi" in components

    event_types = {
        event.event_type
        for event in captured_events
    }

    assert "REQUEST" in event_types
    assert "TOOL_CALL" in event_types
    assert "SERVICE_CALL" in event_types

    assert all(
        event.status == "SUCCESS"
        for event in captured_events
    )

    # Runtime Metrics
    assert (
        app.metrics.get_counter(
            "mcp_REQUEST_total"
        )
        == 1
    )

    assert (
        app.metrics.get_counter(
            "mcp_TOOL_CALL_total"
        )
        == 1
    )

    assert (
        app.metrics.get_counter(
            "bazi_SERVICE_CALL_total"
        )
        == 1
    )

    assert (
        app.metrics.get_counter(
            "bazi_error_total"
        )
        == 0
    )


@pytest.mark.asyncio
async def test_mcp_runtime_trace_invalid_execution(
    captured_events,
):
    """
    Bazi Adapter 返回 isError=True 时：

    bazi SERVICE_CALL -> FAILED
    mcp TOOL_CALL     -> FAILED
    mcp REQUEST       -> FAILED

    即使 Adapter 自己捕获 ValueError，
    error metric 也必须正确增长。
    """

    app = GuanChenMCPServer()

    call_tool_handler = app.server.request_handlers[
        types.CallToolRequest
    ]

    response = await call_tool_handler(
        types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(
                name="bazi.calculate",
                arguments={
                    "year": 1990,
                    "month": 1,
                    "day": 1,
                    "hour": 12,
                    "minute": 30,
                    "gender": "invalid_gender",
                },
            ),
        )
    )

    assert response.root.isError is True

    failed_events = [
        event
        for event in captured_events
        if event.status == "FAILED"
    ]

    assert failed_events

    assert any(
        event.component == "bazi"
        and event.event_type == "SERVICE_CALL"
        and event.status == "FAILED"
        for event in failed_events
    )

    assert any(
        event.component == "mcp"
        and event.event_type == "TOOL_CALL"
        and event.status == "FAILED"
        for event in failed_events
    )

    assert any(
        event.component == "mcp"
        and event.event_type == "REQUEST"
        and event.status == "FAILED"
        for event in failed_events
    )

    # 关键验证：
    # Result-based failure 同样必须计入 error_total。
    assert (
        app.metrics.get_counter(
            "bazi_error_total"
        )
        == 1
    )


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
        state = ConversationState(
            session_id=session_id
        )

        turn = {
            "conversation": state,
            "query": user_query,
            "birth_patch": None,
            "new_task": False,
        }

        await self.orchestrator._route(
            turn
        )

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

    fake_session_runtime = FakeSessionRuntime(
        orchestrator
    )

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

    application_events = [
        event
        for event in captured_events
        if event.component == "application"
        and event.event_type == "REQUEST"
    ]

    router_events = [
        event
        for event in captured_events
        if event.component == "router"
        and event.event_type == "ROUTE"
    ]

    assert len(application_events) == 1
    assert len(router_events) == 1

    # Application Root 和真实 Router
    # 必须继承相同 TraceContext。
    assert (
        application_events[0].trace_id
        == router_events[0].trace_id
    )

    assert application_events[0].trace_id.startswith(
        "app_"
    )

    assert application_events[0].status == "SUCCESS"
    assert router_events[0].status == "SUCCESS"

    # 验证 Application-scoped MetricsCollector
    # 同时收到 Root 和 Router 指标。
    assert (
        app.metrics.get_counter(
            "application_REQUEST_total"
        )
        == 1
    )

    assert (
        app.metrics.get_counter(
            "router_ROUTE_total"
        )
        == 1
    )

    assert (
        app.metrics.get_average_observation(
            "application_REQUEST_latency_ms"
        )
        > 0
    )

    assert (
        app.metrics.get_average_observation(
            "router_ROUTE_latency_ms"
        )
        > 0
    )