import asyncio

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from guanchen_v2.observability.context import TraceContext
from guanchen_v2.observability.integration import reset_tracer, set_tracer
from guanchen_v2.observability.llm_callback import ModelTraceCallback
from guanchen_v2.observability.models import CallBudgetExceeded
from guanchen_v2.observability.tracer import Tracer


@pytest.mark.asyncio
async def test_native_model_callback_blocks_excess_calls_and_isolates_parallel_traces():
    callback = ModelTraceCallback()
    model = FakeListChatModel(responses=["ok"], callbacks=[callback])

    async def request():
        tracer = Tracer(TraceContext.create())
        tracer.run.model_call_limit = 1
        marker = set_tracer(tracer)
        try:
            await model.ainvoke("synthetic secret never recorded")
            with pytest.raises(CallBudgetExceeded):
                await model.ainvoke("budget exceeded")
            assert tracer.run.model_calls == 1
            assert len(tracer.run.steps) == 1
            assert "synthetic secret" not in str(tracer.run)
            return tracer.run.trace_id
        finally:
            reset_tracer(marker)

    ids = await asyncio.gather(request(), request())
    assert len(set(ids)) == 2
    assert not callback.pending


def test_exception_body_not_in_trace_or_logs(monkeypatch):
    events = []
    monkeypatch.setattr("guanchen_v2.observability.tracer.log_event", events.append)
    tracer = Tracer(TraceContext.create())
    with pytest.raises(ValueError):
        with tracer.span("private", "NODE"):
            raise ValueError("secret birth data")
    assert "secret birth data" not in str(events)
    assert tracer.run.steps[0].error == "ValueError"


def test_tool_budget_rejects_before_execution():
    tracer = Tracer(TraceContext.create())
    tracer.run.tool_call_limit = 0
    with pytest.raises(CallBudgetExceeded):
        with tracer.span("cast_hexagram", "TOOL"):
            pytest.fail("Tool body must not run")
