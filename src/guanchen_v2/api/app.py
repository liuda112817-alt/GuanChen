from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from guanchen_v2.api.errors import APIApplicationError, api_application_error_handler, unexpected_error_handler, validation_error_handler
from guanchen_v2.api.routes.chat import router as chat_router
from guanchen_v2.api.service import ChatApplicationService
from guanchen_v2.api.sessions import SessionAccess
from guanchen_v2.config.settings import Settings
from guanchen_v2.memory.implementations.postgres import PostgresMemoryStore
from guanchen_v2.memory.selector import MemorySelector
from guanchen_v2.safety.llm_classifier import LLMSafetyClassifier
from guanchen_v2.safety.rules import SafetyRuleEngine
from guanchen_v2.safety.service import SafetyService


@asynccontextmanager
async def lifespan(app: FastAPI):
    from guanchen_v2.application.factory import open_application

    if not hasattr(app.state, "chat_service"):
        settings = Settings()
        # 复用现有 Application 管理的资源（DB Pool, Checkpointer 等）
        async with open_application(settings) as domain_app:
            classifier = LLMSafetyClassifier(domain_app.llm)
            safety_service = SafetyService(SafetyRuleEngine(), classifier)
            store = PostgresMemoryStore(domain_app.session_factory)
            app.state.session_access = SessionAccess(store)
            app.state.chat_service = ChatApplicationService(
                domain_app,
                safety_service,
                store=store,
                memory=MemorySelector(domain_app.session_factory),
                timeout_seconds=settings.api_timeout_seconds,
            )
            yield
    else:
        yield


def create_app(chat_service: ChatApplicationService | None = None, *, session_store=None, cors_origins=None) -> FastAPI:
    app = FastAPI(title="GuanChen API", lifespan=lifespan if chat_service is None else None)

    if chat_service is not None:
        app.state.chat_service = chat_service
        if session_store is None:
            raise ValueError("Injected services require an explicit session_store")
        app.state.session_access = SessionAccess(session_store)

    if cors_origins is None:
        # This transport config does not require model credentials during import.
        from guanchen_v2.config.settings import APISettings

        cors_origins = APISettings().api_cors_origins
    app.add_middleware(
        CORSMiddleware, allow_origins=cors_origins, allow_methods=["GET", "POST", "PATCH"], allow_headers=["Authorization", "Content-Type"]
    )

    app.add_exception_handler(APIApplicationError, api_application_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)

    app.include_router(chat_router, prefix="/api/v1")

    return app


app = create_app()
