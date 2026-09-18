import logging
from typing import Awaitable, Callable

import mcp.types as types
from mcp.server import Server
from pydantic import ValidationError

from guanchen_v2.mcp.security.audit import log_audit_event

logger = logging.getLogger(__name__)

HandlerType = Callable[[dict], Awaitable[types.CallToolResult]]


class ToolRegistry:
    """可扩展的 MCP Tool Registry。负责元数据注册、鉴权拦截与路由分发。"""

    def __init__(self) -> None:
        self.handlers: dict[str, HandlerType] = {}
        self.metadata: dict[str, dict] = {}

    def register(self, name: str, handler: HandlerType, metadata: dict) -> None:
        self.handlers[name] = handler
        self.metadata[name] = metadata
        logger.info(f"Registered MCP Tool: {name}")

    async def dispatch(self, name: str, arguments: dict, client_id: str, client_permissions: list[str]) -> types.CallToolResult:
        # 1. Existence Check
        if name not in self.handlers:
            error_msg = f"Tool {name} is not registered."
            log_audit_event(client_id, name, "FAILED", error_msg)
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=error_msg)],
                isError=True
            )

        # 2. Permission Check
        required_permission = self.metadata[name].get("permission")
        if required_permission and required_permission not in client_permissions:
            error_msg = f"Permission denied for tool {name}. Required: {required_permission}"
            log_audit_event(client_id, name, "FAILED", error_msg)
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=error_msg)],
                isError=True
            )

        # 3. Execution & Audit
        try:
            handler = self.handlers[name]
            result = await handler(arguments)
            
            if getattr(result, "isError", False):
                log_audit_event(client_id, name, "FAILED", "Adapter returned error")
            else:
                log_audit_event(client_id, name, "SUCCESS")
                
            return result

        except ValidationError as e:
            error_msg = f"Input validation error: {str(e)}"
            log_audit_event(client_id, name, "FAILED", error_msg)
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=error_msg)],
                isError=True
            )
        except Exception as e:
            error_msg = f"Internal execution error: {str(e)}"
            log_audit_event(client_id, name, "FAILED", error_msg)
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=error_msg)],
                isError=True
            )

    def bind_to_server(self, server: Server) -> None:
        @server.list_tools()
        async def list_tools() -> list[types.Tool]:
            return [
                types.Tool(
                    name=meta["name"],
                    description=meta["description"],
                    inputSchema=meta["inputSchema"]
                )
                for meta in self.metadata.values()
            ]

        @server.call_tool()
        async def call_tool(name: str, arguments: dict) -> types.CallToolResult:
            # Task 4 当前仅建立 Permission 检查入口，不实现真实的 Identity 鉴权体系。
            # 给客户端赋予所有基础能力权限以确保流程畅通。
            default_client = "anonymous_agent"
            default_permissions = ["bazi.read", "knowledge.read", "liuyao.read"]
            return await self.dispatch(name, arguments, default_client, default_permissions)