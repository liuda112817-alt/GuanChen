from contextvars import ContextVar

import mcp_types as types
from pydantic import ValidationError

from guanchen_v2.mcp.security.audit import log_audit_event
from guanchen_v2.observability.context import TraceContext
from guanchen_v2.observability.integration import get_tracer, reset_tracer, set_tracer
from guanchen_v2.observability.tracer import Tracer

# stdio inherits local process trust; HTTP middleware replaces it.
access_context = ContextVar("mcp_access", default=("local_stdio", ("bazi.read", "knowledge.read", "liuyao.read")))


class ToolRegistry:
    def __init__(self, metrics=None):
        self.handlers = {}
        self.metadata = {}
        self.metrics = metrics

    def register(self, name, handler, metadata):
        if name in self.handlers:
            raise ValueError("Duplicate MCP tool")
        self.handlers[name] = handler
        self.metadata[name] = metadata

    async def dispatch(self, name, arguments, client_id, client_permissions):
        existing = get_tracer()
        tracer = existing or Tracer(TraceContext.create(prefix="mcp"), metrics=self.metrics)
        token = set_tracer(tracer)
        try:
            with tracer.span("mcp", "DISPATCH" if existing else "REQUEST") as root:
                with tracer.span("mcp", "TOOL_CALL", {"tool_name": name}) as span:
                    try:
                        if name not in self.handlers:
                            raise ValueError("Unknown tool")
                        required = self.metadata[name].get("permission")
                        if required and required not in client_permissions:
                            raise PermissionError("Permission denied")
                        result = await self.handlers[name](arguments)
                    except Exception as exc:
                        message = "Input validation error" if isinstance(exc, (ValidationError, ValueError)) else type(exc).__name__
                        if isinstance(exc, PermissionError):
                            message = "Permission denied"
                        span.metadata["error"] = type(exc).__name__
                        result = types.CallToolResult(content=[types.TextContent(type="text", text=message)], is_error=True)
                    if result.is_error:
                        root.status = span.status = "FAILED"
                    log_audit_event(client_id, name, span.status)
                    return result
        finally:
            reset_tracer(token)

    async def call(self, name, arguments):
        client_id, permissions = access_context.get()
        return await self.dispatch(name, arguments, client_id, permissions)
