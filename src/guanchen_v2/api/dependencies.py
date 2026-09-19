from fastapi import Request

from guanchen_v2.api.service import ChatApplicationService


def get_chat_service(request: Request) -> ChatApplicationService:
    return request.app.state.chat_service
