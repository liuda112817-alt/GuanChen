import mcp_types as types

from guanchen_v2.bazi.service import BaziService
from guanchen_v2.mcp.tools.bazi import BaziCalculateInput
from guanchen_v2.observability.decorators import trace


class BaziCapabilityAdapter:
    def __init__(self, service: BaziService) -> None:
        self.service = service

    @trace(component="bazi", event_type="SERVICE_CALL")
    async def calculate(self, request: BaziCalculateInput) -> types.CallToolResult:
        chart = self.service.calculate(request)
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=chart.model_dump_json())], structured_content=chart.model_dump(mode="json")
        )
