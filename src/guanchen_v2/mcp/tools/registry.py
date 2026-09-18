import mcp.types as types
from mcp.server import Server
from pydantic import ValidationError

from guanchen_v2.mcp.tools.bazi import BaziCalculateInput, get_bazi_tool_definition
from guanchen_v2.mcp.adapters.bazi_adapter import BaziCapabilityAdapter


class MCPToolRegistry:
    """
    管理所有的 Capability Adapters，并向 MCP Server 注册 Tool List 与 Dispatch 规则。
    """
    def __init__(self, bazi_adapter: BaziCapabilityAdapter) -> None:
        self.bazi_adapter = bazi_adapter

    def register(self, server: Server) -> None:
        
        @server.list_tools()
        async def list_tools() -> list[types.Tool]:
            bazi_def = get_bazi_tool_definition()
            return [
                types.Tool(
                    name=bazi_def["name"],
                    description=bazi_def["description"],
                    inputSchema=bazi_def["inputSchema"]
                )
            ]

        @server.call_tool()
        async def call_tool(name: str, arguments: dict) -> types.CallToolResult:
            if name == "bazi.calculate":
                try:
                    request = BaziCalculateInput(**arguments)
                    return await self.bazi_adapter.calculate(request)
                except ValidationError as e:
                    return types.CallToolResult(
                        content=[
                            types.TextContent(
                                type="text",
                                text=f"Invalid arguments for {name}:\n{str(e)}"
                            )
                        ],
                        isError=True
                    )

            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Tool {name} is not implemented"
                    )
                ],
                isError=True
            )