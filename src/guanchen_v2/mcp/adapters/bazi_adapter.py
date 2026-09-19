import json
import mcp.types as types
from guanchen_v2.bazi.service import BaziService
from guanchen_v2.models.bazi import BirthProfile, Gender
from guanchen_v2.bazi.exceptions import BaziError
from guanchen_v2.mcp.tools.bazi import BaziCalculateInput
from guanchen_v2.observability.decorators import trace

class BaziCapabilityAdapter:
    def __init__(self, service: BaziService) -> None:
        self.service = service

    @trace(component="bazi", event_type="SERVICE_CALL")
    async def calculate(self, request: BaziCalculateInput) -> types.CallToolResult:
        try:
            profile = BirthProfile(
                year=request.year, month=request.month, day=request.day,
                hour=request.hour, minute=request.minute, gender=Gender(request.gender)
            )
            chart = self.service.calculate(profile)
            return types.CallToolResult(content=[types.TextContent(type="text", text=chart.model_dump_json())])
            
        except (ValueError, BaziError) as e:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Bazi calculation failed: {str(e)}")],
                isError=True,
            )
