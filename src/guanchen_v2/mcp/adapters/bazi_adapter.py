import json

import mcp.types as types

from guanchen_v2.bazi.service import BaziService
from guanchen_v2.models.bazi import BirthProfile, Gender
from guanchen_v2.bazi.exceptions import BaziError
from guanchen_v2.mcp.tools.bazi import BaziCalculateInput


class BaziCapabilityAdapter:
    """
    负责将 MCP 标准请求映射到内部 BaziService，并安全封装响应/异常。
    不包含任何业务计算逻辑。
    """
    def __init__(self, service: BaziService) -> None:
        self.service = service

    async def calculate(self, request: BaziCalculateInput) -> types.CallToolResult:
        try:
            # 1. Parameter Conversion
            profile = BirthProfile(
                year=request.year,
                month=request.month,
                day=request.day,
                hour=request.hour,
                minute=request.minute,
                gender=Gender(request.gender)
            )
            
            # 2. Domain Service Invocation (修复此处的真实方法名)
            chart = self.service.calculate(profile)
            
            # 3. Output Schema Contract
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=chart.model_dump_json()
                    )
                ]
            )
            
        except (ValueError, BaziError) as e:
            # 4. Exception Conversion to MCP Protocol Error
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Bazi calculation failed: {str(e)}"
                    )
                ],
                isError=True,
            )