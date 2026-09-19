import logging
from typing import Awaitable, Callable

import mcp.types as types
from mcp.server import Server
from pydantic import ValidationError

from guanchen_v2.mcp.security.audit import log_audit_event
from guanchen_v2.observability.context import TraceContext
from guanchen_v2.observability.tracer import Tracer
from guanchen_v2.observability.integration import set_tracer, reset_tracer, get_tracer
from guanchen_v2.observability.metrics import MetricsCollector

logger = logging.getLogger(__name__)

HandlerType = Callable[[dict], Awaitable[types.CallToolResult]]

class ToolRegistry:
    def __init__(self, metrics: MetricsCollector | None = None) -> None:
        self.handlers: dict[str, HandlerType] = {}
        self.metadata: dict[str, dict] = {}
        self.metrics = metrics

    def register(self, name: str, handler: HandlerType, metadata: dict) -> None:
        self.handlers[name] = handler
        self.metadata[name] = metadata
        logger.info(f"Registered MCP Tool: {name}")

    async def dispatch(self, name: str, arguments: dict, client_id: str, client_permissions: list[str]) -> types.CallToolResult:
        tracer = get_tracer()
        
        async def _do_dispatch():
            if name not in self.handlers:
                error_msg = f"Tool {name} is not registered."
                log_audit_event(client_id, name, "FAILED", error_msg)
                return types.CallToolResult(content=[types.TextContent(type="text", text=error_msg)], isError=True)

            required_permission = self.metadata[name].get("permission")
            if required_permission and required_permission not in client_permissions:
                error_msg = f"Permission denied for tool {name}. Required: {required_permission}"
                log_audit_event(client_id, name, "FAILED", error_msg)
                return types.CallToolResult(content=[types.TextContent(type="text", text=error_msg)], isError=True)

            try:
                handler = self.handlers[name]
                result = await handler(arguments)
                
                if getattr(result, "isError", False) is True:
                    log_audit_event(client_id, name, "FAILED", "Adapter returned error")
                else:
                    log_audit_event(client_id, name, "SUCCESS")
                return result

            except ValidationError as e:
                error_msg = f"Input validation error: {str(e)}"
                log_audit_event(client_id, name, "FAILED", error_msg)
                return types.CallToolResult(content=[types.TextContent(type="text", text=error_msg)], isError=True)
            except Exception as e:
                error_msg = f"Internal execution error: {str(e)}"
                log_audit_event(client_id, name, "FAILED", error_msg)
                return types.CallToolResult(content=[types.TextContent(type="text", text=error_msg)], isError=True)

        if tracer:
            with tracer.span("mcp", "TOOL_CALL", {"tool_name": name}) as span:
                result = await _do_dispatch()
                if getattr(result, "isError", False) is True:
                    span.status = "FAILED"
                return result
        else:
            return await _do_dispatch()

    def bind_to_server(self, server: Server) -> None:
        @server.list_tools()
        async def list_tools() -> list[types.Tool]:
            return [
                types.Tool(name=meta["name"], description=meta["description"], inputSchema=meta["inputSchema"])
                for meta in self.metadata.values()
            ]

        @server.call_tool()
        async def call_tool(name: str, arguments: dict) -> types.CallToolResult:
            ctx = TraceContext.create(prefix="mcp")
            tracer = Tracer(context=ctx, metrics=self.metrics)
            token = set_tracer(tracer)
            
            try:
                # 修正语义：这是 MCP 端的真实入口，用 mcp / REQUEST 表示完整 span
                with tracer.span("mcp", "REQUEST") as span:
                    default_client = "anonymous_agent"
                    default_permissions = ["bazi.read", "knowledge.read", "liuyao.read"]
                    result = await self.dispatch(name, arguments, default_client, default_permissions)
                    if getattr(result, "isError", False) is True:
                        span.status = "FAILED"
                    return result
            finally:
                reset_tracer(token)
