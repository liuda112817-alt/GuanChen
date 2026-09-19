import asyncio
import json
import time
import uuid
import weakref
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import select

from guanchen_v2.agents.bazi.models import BaziAgentInput, InvalidBaziInput, ReadyForBazi
from guanchen_v2.agents.bazi.requirements import check_bazi_requirements
from guanchen_v2.api.contracts import (
    ChatRequest,
    ChatResponse,
    ChatStatus,
    CitationDetailResponse,
    ProfileResponse,
    ProfileUpdateRequest,
    ResumeRequest,
    SessionDetailResponse,
)
from guanchen_v2.api.errors import APIApplicationError
from guanchen_v2.api.mapper import ChatResponseMapper
from guanchen_v2.knowledge.persistence.models import KnowledgeChunkRow
from guanchen_v2.observability.context import TraceContext
from guanchen_v2.observability.events import ObservabilityEvent
from guanchen_v2.observability.integration import get_tracer, reset_tracer, set_tracer
from guanchen_v2.observability.logger import log_event
from guanchen_v2.observability.tracer import Tracer
from guanchen_v2.safety.models import RiskDomain, RiskLevel, SafetyAction, SafetyDecision
from guanchen_v2.safety.output import protect_response


class ChatApplicationService:
    def __init__(self, application, safety_service, *, store=None, memory=None, timeout_seconds=180):
        self._application = application
        self._safety_service = safety_service
        self._mapper = ChatResponseMapper()
        self.store = store
        self.memory = memory
        self.timeout_seconds = timeout_seconds
        self._locks = weakref.WeakValueDictionary()

    def lock(self, session_id):
        return self._locks.setdefault(session_id, asyncio.Lock())

    async def chat(self, request: ChatRequest) -> ChatResponse:
        session_id = request.session_id or str(uuid.uuid4())
        async with self.lock(session_id):
            return await self._traced_chat(request, session_id)

    async def resume(self, request: ResumeRequest) -> ChatResponse:
        async with self.lock(request.session_id):
            state = await self._application.load_session_state(request.session_id)
            pending = state.pending_interrupt if state else None
            latest_confirmation = state.metadata.extra.get("active_interrupt") if state else None
            if (
                not pending
                or pending.interrupt_type != "INTERRUPTED"
                or pending.payload.get("thread_id") != request.thread_id
                or not latest_confirmation
                or latest_confirmation.get("confirmation_id") != request.confirmation_id
            ):
                raise APIApplicationError("STALE_INTERRUPT", "该确认已失效，请读取最新会话状态。", None, 409)
            payload = {"action": request.action.value}
            if request.modification:
                payload["modification"] = request.modification
            return await self._traced_chat(
                ChatRequest(session_id=request.session_id, message=json.dumps(payload, ensure_ascii=False)),
                request.session_id,
                resuming=True,
            )

    async def _traced_chat(self, request, session_id, *, resuming=False):
        tracer = get_tracer()
        token = None
        if tracer is None:
            tracer = Tracer(context=TraceContext.create(prefix="api"), metrics=getattr(self._application, "metrics", None))
            token = set_tracer(tracer)
        started = time.perf_counter()
        try:
            async with asyncio.timeout(self.timeout_seconds):
                with tracer.span(component="api", event_type="REQUEST"):
                    response = await self._execute_chat(request, session_id, resuming=resuming)
                    response.trace_id = tracer.run.trace_id
                    tracer.run.status = response.status.value
                    if self.store is not None:
                        state = await self.store.load(session_id)
                        state.metadata.extra["last_response"] = response.model_dump(mode="json", exclude={"session_token"})
                        if response.interrupt is not None:
                            state.metadata.extra["active_interrupt"] = response.interrupt.model_dump(mode="json")
                        elif response.status != ChatStatus.BLOCKED:
                            state.metadata.extra.pop("active_interrupt", None)
                        await self.store.update(state)
                    return response
        except TimeoutError as exc:
            tracer.run.status = "FAILED"
            raise APIApplicationError("REQUEST_TIMEOUT", "请求超时，请读取会话状态后重试。", tracer.run.trace_id, 504) from exc
        except asyncio.CancelledError:
            tracer.run.status = "CANCELLED"
            raise
        except Exception as exc:
            tracer.run.status = "FAILED"
            if isinstance(exc, APIApplicationError):
                raise
            raise APIApplicationError("RUNTIME_ERROR", "请求处理失败。", tracer.run.trace_id, 500) from exc
        finally:
            if token is not None:
                tracer.run.latency_ms = (time.perf_counter() - started) * 1000
                reset_tracer(token)
                log_event(
                    ObservabilityEvent(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        trace_id=tracer.run.trace_id,
                        component="api",
                        event_type="RUN",
                        status=tracer.run.status,
                        duration_ms=tracer.run.latency_ms,
                        metadata=asdict(tracer.run),
                    )
                )

    async def _execute_chat(self, request, session_id, *, resuming=False):
        state = await self._application.load_session_state(session_id)
        safety_text = request.message
        cancelling = resuming and json.loads(request.message).get("action") == "cancel"
        if state is not None and not request.new_task and not cancelling:
            context = []
            if isinstance(state.pending_query, str):
                context.append(state.pending_query)
            if state.pending_interrupt:
                latest = state.agent_states.liuyao.get("latest_output", {})
                question = latest.get("question", {}) if isinstance(latest, dict) else {}
                context.extend(str(question.get(k, "")) for k in ("original_question", "clarified_question"))
                if isinstance(state.current_query, str):
                    context.append(state.current_query)
            safety_text = "\n".join([*context, request.message])
        decision = await self._safety_service.evaluate(safety_text)
        if decision.action == SafetyAction.SAFE_RESPONSE:
            return ChatResponse(
                session_id=session_id, status=ChatStatus.BLOCKED, content=decision.user_message or "请求被安全策略中止。", safety=decision
            )

        if state and state.pending_interrupt and state.pending_interrupt.interrupt_type == "INTERRUPTED" and not resuming and not request.new_task:
            raise APIApplicationError("RESUME_REQUIRED", "请使用最新确认卡片继续、修改或取消。", None, 409)
        result = await self._application.execute(
            session_id=session_id,
            user_query=request.message,
            birth_patch=request.birth_profile,
            new_task=request.new_task,
        )
        if result.session_id != session_id:
            raise ValueError("Runtime returned inconsistent session_id")
        result = protect_response(result)
        if result.output_blocked:
            return ChatResponse(
                session_id=session_id,
                status=ChatStatus.BLOCKED,
                content=result.content,
                safety=SafetyDecision(
                    risk_domain=RiskDomain.NONE,
                    risk_level=RiskLevel.HIGH_RISK,
                    action=SafetyAction.SAFE_RESPONSE,
                    reason_code="OUTPUT_ASSERTION_BLOCKED",
                ),
            )
        state = await self._application.load_session_state(session_id)
        return self._mapper.map(result=result, safety=decision, state=state)

    async def session(self, session_id):
        async with self.lock(session_id):
            state = await self.store.load(session_id)
            if state is None:
                raise APIApplicationError("SESSION_NOT_FOUND", "会话不存在。", None, 404)
            return SessionDetailResponse(
                session_id=session_id,
                messages=[{"role": m.role, "content": m.content} for m in state.messages],
                last_response=state.metadata.extra.get("last_response"),
                interrupt=state.metadata.extra.get("active_interrupt") if state.pending_interrupt else None,
            )

    async def profile(self, session_id):
        async with self.lock(session_id):
            state = await self.store.load(session_id)
            if state is None:
                raise APIApplicationError("SESSION_NOT_FOUND", "会话不存在。", None, 404)
            profile = await self.memory.load_birth_profile(session_id)
            return ProfileResponse(session_id=session_id, birth_profile=profile, supplied_fields=state.birth_data)

    async def update_profile(self, request: ProfileUpdateRequest):
        async with self.lock(request.session_id):
            state = await self.store.load(request.session_id)
            if state is None:
                raise APIApplicationError("SESSION_NOT_FOUND", "会话不存在。", None, 404)
            previous = await self.memory.load_birth_profile(request.session_id)
            fields = previous.model_dump() if previous else {}
            fields.update(state.birth_data)
            fields.update(request.birth_profile.model_dump(exclude_unset=True))
            fields = {k: v for k, v in fields.items() if k in type(request.birth_profile).model_fields}
            checked = check_bazi_requirements(BaziAgentInput(question="更新出生资料", **fields))
            if isinstance(checked, InvalidBaziInput) or (previous and not isinstance(checked, ReadyForBazi)):
                raise APIApplicationError("INVALID_PROFILE", "出生资料不合法，请检查日期和必填字段。", None, 422)
            state.birth_data = fields
            profile = checked.profile if isinstance(checked, ReadyForBazi) else None
            if profile is not None:
                await self.memory.ensure_user(request.session_id)
                await self.memory.persist_birth_profile(request.session_id, profile)
            await self.store.update(state)
            return ProfileResponse(session_id=request.session_id, birth_profile=profile, supplied_fields=fields)

    async def citation(self, session_id, chunk_id):
        async with self.lock(session_id):
            state = await self.store.load(session_id)
            if state is None:
                raise APIApplicationError("SESSION_NOT_FOUND", "会话不存在。", None, 404)
            citations = state.metadata.extra.get("last_response", {}).get("citations", [])
            citation = next((c for c in citations if c["chunk_id"] == chunk_id), None)
            if citation is None:
                raise APIApplicationError("CITATION_NOT_FOUND", "当前会话回答中没有该引用。", None, 404)
            async with self._application.session_factory() as session:
                chunk = (await session.execute(select(KnowledgeChunkRow).where(KnowledgeChunkRow.chunk_id == chunk_id))).scalar_one_or_none()
            if chunk is None:
                raise APIApplicationError("CITATION_NOT_FOUND", "引用已不可用。", None, 404)
            return CitationDetailResponse(**citation, text=chunk.text)
