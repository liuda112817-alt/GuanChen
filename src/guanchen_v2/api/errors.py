from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from guanchen_v2.api.contracts import APIErrorResponse
from guanchen_v2.observability.integration import get_tracer


def _get_trace_id() -> str | None:
    tracer = get_tracer()
    if not tracer:
        return None
    # 兼容处理各种可能的 Tracer 结构
    if hasattr(tracer, "run") and hasattr(tracer.run, "trace_id"):
        return tracer.run.trace_id
    if hasattr(tracer, "context") and hasattr(tracer.context, "trace_id"):
        return tracer.context.trace_id
    return getattr(tracer, "trace_id", None)


class APIApplicationError(Exception):
    def __init__(self, code: str, message: str, trace_id: str | None, status_code: int = 500):
        self.code = code
        self.message = message
        self.trace_id = trace_id
        self.status_code = status_code
        super().__init__(message)


async def api_application_error_handler(request: Request, exc: APIApplicationError):
    return JSONResponse(status_code=exc.status_code, content=APIErrorResponse(code=exc.code, message=exc.message, trace_id=exc.trace_id).model_dump())


async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422, content=APIErrorResponse(code="INVALID_REQUEST", message="Request validation failed.", trace_id=_get_trace_id()).model_dump()
    )


async def unexpected_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=APIErrorResponse(code="RUNTIME_ERROR", message="请求处理失败。", trace_id=_get_trace_id()).model_dump(),
    )
