import mcp_types as types

from guanchen_v2.liuyao.casting import HexagramCastingService
from guanchen_v2.mcp.tools.liuyao import LiuyaoCastInput
from guanchen_v2.observability.decorators import trace


class LiuyaoCapabilityAdapter:
    def __init__(self, service: HexagramCastingService) -> None:
        self.service = service

    @trace(component="liuyao", event_type="SERVICE_CALL")
    async def cast(self, request: LiuyaoCastInput) -> types.CallToolResult:
        result = self.service.cast_manual(request.manual) if request.method == "manual" else self.service.cast_random()
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=result.model_dump_json())], structured_content=result.model_dump(mode="json")
        )
