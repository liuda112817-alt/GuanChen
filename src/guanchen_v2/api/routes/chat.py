from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse

from guanchen_v2.api.contracts import (
    ChatRequest,
    ChatResponse,
    CitationDetailResponse,
    ProfileResponse,
    ProfileUpdateRequest,
    ResumeRequest,
    SessionDetailResponse,
    SessionResponse,
)
from guanchen_v2.api.dependencies import get_chat_service
from guanchen_v2.api.service import ChatApplicationService
from guanchen_v2.api.streaming import stream_events

router = APIRouter(tags=["conversation"])


async def chat_session(request, payload, authorization):
    access = request.app.state.session_access
    if payload.session_id:
        await access.authorize(payload.session_id, authorization)
        return payload, None
    created = await access.create()
    return payload.model_copy(update={"session_id": created.session_id}), created.session_token


def streaming(operation, session_id, token=None):
    return StreamingResponse(
        stream_events(operation, session_id, token),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-store", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(request: Request):
    return await request.app.state.session_access.create()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    service: ChatApplicationService = Depends(get_chat_service),
):
    payload, token = await chat_session(request, payload, authorization)
    result = await service.chat(payload)
    result.session_token = token
    return result


@router.post("/chat/stream", response_class=StreamingResponse)
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    service: ChatApplicationService = Depends(get_chat_service),
):
    payload, token = await chat_session(request, payload, authorization)
    return streaming(lambda: service.chat(payload), payload.session_id, token)


@router.post("/resume", response_model=ChatResponse)
async def resume(
    payload: ResumeRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    service: ChatApplicationService = Depends(get_chat_service),
):
    await request.app.state.session_access.authorize(payload.session_id, authorization)
    return await service.resume(payload)


@router.post("/resume/stream", response_class=StreamingResponse)
async def resume_stream(
    payload: ResumeRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    service: ChatApplicationService = Depends(get_chat_service),
):
    await request.app.state.session_access.authorize(payload.session_id, authorization)
    return streaming(lambda: service.resume(payload), payload.session_id)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def session(
    session_id: str, request: Request, authorization: str | None = Header(default=None), service: ChatApplicationService = Depends(get_chat_service)
):
    await request.app.state.session_access.authorize(session_id, authorization)
    return await service.session(session_id)


@router.get("/sessions/{session_id}/profile", response_model=ProfileResponse)
async def profile(
    session_id: str, request: Request, authorization: str | None = Header(default=None), service: ChatApplicationService = Depends(get_chat_service)
):
    await request.app.state.session_access.authorize(session_id, authorization)
    return await service.profile(session_id)


@router.patch("/profile", response_model=ProfileResponse)
async def update_profile(
    payload: ProfileUpdateRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    service: ChatApplicationService = Depends(get_chat_service),
):
    await request.app.state.session_access.authorize(payload.session_id, authorization)
    return await service.update_profile(payload)


@router.get("/sessions/{session_id}/citations/{chunk_id}", response_model=CitationDetailResponse)
async def citation(
    session_id: str,
    chunk_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
    service: ChatApplicationService = Depends(get_chat_service),
):
    await request.app.state.session_access.authorize(session_id, authorization)
    return await service.citation(session_id, chunk_id)
