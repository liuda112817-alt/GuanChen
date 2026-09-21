import asyncio
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from sqlalchemy import text

from guanchen_v2.api.errors import APIApplicationError, api_application_error_handler, unexpected_error_handler, validation_error_handler
from guanchen_v2.api.reliability import AdmissionMiddleware, Reliability
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
        if settings.app_env == "production" and settings.redis_url is None:
            raise RuntimeError("Production requires GUANCHEN_REDIS_URL")
        # 复用现有 Application 管理的资源（DB Pool, Checkpointer 等）
        async with AsyncExitStack() as stack:
            redis = None
            if settings.redis_url is not None:
                redis = Redis.from_url(settings.redis_url.get_secret_value(), socket_timeout=3, socket_connect_timeout=3)
                stack.push_async_callback(redis.aclose)
                await redis.ping()
                app.state.reliability = Reliability(
                    redis, rate_limit=settings.api_rate_limit, max_concurrent=settings.api_max_concurrent,
                    timeout=settings.api_timeout_seconds,
                )
            app.state.trust_proxy = settings.api_trust_proxy
            domain_app = await stack.enter_async_context(open_application(settings))

            async def readiness():
                async with asyncio.timeout(4):
                    async with domain_app.session_factory() as session:
                        await session.execute(text("SELECT 1"))
                        count = await session.scalar(text("SELECT count(*) FROM knowledge_chunks"))
                        if not count:
                            raise RuntimeError("Empty corpus")
                    if redis is not None:
                        await redis.ping()

            app.state.readiness = readiness
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
        CORSMiddleware, allow_origins=cors_origins, allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"]
    )
    app.add_middleware(AdmissionMiddleware)

    app.add_exception_handler(APIApplicationError, api_application_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)

    app.include_router(chat_router, prefix="/api/v1")

    return app


app = create_app()
