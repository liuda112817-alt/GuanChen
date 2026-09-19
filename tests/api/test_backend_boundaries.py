import asyncio
import json

import httpx
import pytest

from guanchen_v2.api.app import create_app
from guanchen_v2.api.contracts import ChatRequest, ChatResponse, ChatStatus, ResumeRequest
from guanchen_v2.api.errors import APIApplicationError
from guanchen_v2.api.service import ChatApplicationService
from guanchen_v2.api.sessions import SessionAccess
from guanchen_v2.api.streaming import stream_events
from guanchen_v2.application.progress import emit_progress
from guanchen_v2.core.session.models import PendingInterrupt
from guanchen_v2.memory.implementations.inmemory import InMemoryMemoryStore
from guanchen_v2.router.synthesis import SynthesizedResponse
from guanchen_v2.safety.rules import SafetyRuleEngine
from guanchen_v2.safety.service import SafetyService


class Runtime:
    metrics = None

    def __init__(self, store):
        self.store = store
        self.calls = 0
        self.answer = "文化参考"

    async def load_session_state(self, session_id):
        return await self.store.load(session_id)

    async def execute(self, session_id, user_query, **kwargs):
        self.calls += 1
        state = await self.store.load(session_id)
        state.pending_interrupt = None
        await self.store.update(state)
        return SynthesizedResponse(session_id=session_id, used_intents=(), content=self.answer)


@pytest.fixture
async def backend():
    store = InMemoryMemoryStore()
    runtime = Runtime(store)
    service = ChatApplicationService(runtime, SafetyService(SafetyRuleEngine()), store=store)
    app = create_app(service, session_store=store)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, service, runtime, store


async def test_session_access_survives_new_access_object_and_rejects_other_token(backend):
    client, service, runtime, store = backend
    first = (await client.post("/api/v1/sessions")).json()
    second = (await client.post("/api/v1/sessions")).json()
    path = "/api/v1/sessions/" + first["session_id"]
    assert (await client.get(path)).status_code == 401
    assert (await client.get(path, headers={"Authorization": "Bearer " + second["session_token"]})).status_code == 401
    await SessionAccess(store).authorize(first["session_id"], "Bearer " + first["session_token"])
    result = await client.get(path, headers={"Authorization": "Bearer " + first["session_token"]})
    assert result.status_code == 200
    assert "access_hash" not in result.text and first["session_token"] not in result.text
    denied = await client.post("/api/v1/chat", json={"session_id": first["session_id"], "message": "你好"})
    assert denied.status_code == 401 and runtime.calls == 0


async def test_anonymous_chat_issues_credential_and_sse_contract(backend):
    client, _, runtime, _ = backend
    response = await client.post("/api/v1/chat/stream", json={"message": "你好"})
    assert response.status_code == 200
    frames = [x for x in response.text.split("\n\n") if x]
    events = [x.splitlines()[1].removeprefix("event: ") for x in frames]
    assert events == ["start", "token", "done"]
    start = json.loads(frames[0].split("data: ")[1])
    done = json.loads(frames[-1].split("data: ")[1])
    assert start["session_id"] == done["session_id"]
    assert start["session_token"] == done["session_token"]
    assert done["trace_id"] and runtime.calls == 1


async def test_crisis_and_unsafe_output_never_stream_raw_answer(backend):
    client, _, runtime, _ = backend
    response = await client.post("/api/v1/chat/stream", json={"message": "我想自杀"})
    assert '"blocked"' in response.text and runtime.calls == 0
    runtime.answer = "你今年一定会死于癌症。"
    response = await client.post("/api/v1/chat/stream", json={"message": "帮我看看八字"})
    assert runtime.answer not in response.text
    assert "OUTPUT_ASSERTION_BLOCKED" in response.text


async def test_stale_and_concurrent_resume_cast_only_once(backend):
    client, service, runtime, store = backend
    created = await SessionAccess(store).create()
    state = await store.load(created.session_id)
    state.pending_interrupt = PendingInterrupt(agent="liuyao", interrupt_type="INTERRUPTED", payload={"thread_id": "thread"})
    state.metadata.extra["active_interrupt"] = {"confirmation_id": "revision"}
    await store.update(state)
    req = ResumeRequest(session_id=created.session_id, thread_id="thread", confirmation_id="revision", action="confirm")
    results = await asyncio.gather(service.resume(req), service.resume(req), return_exceptions=True)
    assert runtime.calls == 1
    assert sum(isinstance(r, APIApplicationError) and r.status_code == 409 for r in results) == 1
    denied = await client.post("/api/v1/resume", json=req.model_dump())
    assert denied.status_code == 401


async def test_pending_unsafe_question_cannot_be_laundered_by_confirmation(backend):
    _, service, runtime, store = backend
    created = await SessionAccess(store).create()
    state = await store.load(created.session_id)
    state.pending_query = "我想自杀"
    await store.update(state)
    result = await service.chat(ChatRequest(session_id=created.session_id, message="继续"))
    assert result.status == "blocked" and runtime.calls == 0


async def test_blocked_turn_keeps_card_cancellable_and_rejects_old_revision(backend):
    _, service, runtime, store = backend
    created = await SessionAccess(store).create()
    state = await store.load(created.session_id)
    state.pending_interrupt = PendingInterrupt(agent="liuyao", interrupt_type="INTERRUPTED", payload={"thread_id": "thread"})
    state.metadata.extra["active_interrupt"] = {
        "type": "confirmation",
        "thread_id": "thread",
        "prompt": "请确认",
        "confirmation_id": "current",
    }
    await store.update(state)
    blocked = await service.chat(ChatRequest(session_id=created.session_id, message="我想自杀"))
    assert blocked.status == "blocked" and runtime.calls == 0
    restored = await service.session(created.session_id)
    assert restored.interrupt.confirmation_id == "current"
    with pytest.raises(APIApplicationError) as exc:
        await service.resume(ResumeRequest(session_id=created.session_id, thread_id="thread", confirmation_id="old", action="confirm"))
    assert exc.value.status_code == 409
    await service.resume(ResumeRequest(session_id=created.session_id, thread_id="thread", confirmation_id="current", action="cancel"))
    assert runtime.calls == 1


async def test_confirmation_must_use_revision_checked_resume(backend):
    _, service, runtime, store = backend
    created = await SessionAccess(store).create()
    state = await store.load(created.session_id)
    state.pending_interrupt = PendingInterrupt(agent="liuyao", interrupt_type="INTERRUPTED", payload={"thread_id": "thread"})
    await store.update(state)
    with pytest.raises(APIApplicationError) as exc:
        await service.chat(ChatRequest(session_id=created.session_id, message="确认"))
    assert exc.value.code == "RESUME_REQUIRED" and runtime.calls == 0


async def test_progress_is_live_and_disconnect_cancels_work():
    release = asyncio.Event()
    cancelled = asyncio.Event()

    async def operation():
        try:
            emit_progress("tool_start", {"tool": "calculate_bazi"})
            await release.wait()
            return ChatResponse(session_id="s", status=ChatStatus.ANSWERED, content="result")
        finally:
            cancelled.set()

    stream = stream_events(operation, "s")
    assert "event: start" in await anext(stream)
    assert "event: tool_start" in await asyncio.wait_for(anext(stream), 1)
    assert not release.is_set()
    await stream.aclose()
    assert cancelled.is_set()


async def test_stream_error_has_no_done_or_internal_exception():
    async def operation():
        raise RuntimeError("secret password")

    frames = [frame async for frame in stream_events(operation, "s")]
    assert "event: error" in frames[-1]
    assert "secret" not in "".join(frames) and "event: done" not in "".join(frames)


async def test_timeout_cancels_runtime(backend):
    _, service, runtime, store = backend
    created = await SessionAccess(store).create()
    cancelled = asyncio.Event()

    async def execute(**kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    runtime.execute = execute
    service.timeout_seconds = 0.01
    with pytest.raises(APIApplicationError, match="超时") as exc:
        await service.chat(ChatRequest(session_id=created.session_id, message="你好"))
    assert exc.value.status_code == 504 and cancelled.is_set()


async def test_cors_allows_configured_bolt_origin_only(backend):
    client, _, _, _ = backend
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    }
    assert (await client.options("/api/v1/chat/stream", headers=headers)).status_code == 200
    headers["Origin"] = "https://unconfigured.example"
    assert (await client.options("/api/v1/chat/stream", headers=headers)).status_code == 400
