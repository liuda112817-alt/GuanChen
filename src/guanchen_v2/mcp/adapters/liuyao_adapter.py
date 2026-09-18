import json

import mcp.types as types

from guanchen_v2.liuyao.casting import HexagramCastingService, ManualCastingInput
from guanchen_v2.models.liuyao import LineValue
from guanchen_v2.mcp.tools.liuyao import LiuyaoCastInput


class LiuyaoCapabilityAdapter:
    def __init__(self, service: HexagramCastingService) -> None:
        self.service = service

    async def cast(self, request: LiuyaoCastInput) -> types.CallToolResult:
        try:
            # 1. 根据 MCP 传入的 method 参数进行路由分发
            if request.method == "manual":
                if len(request.manual_records) != 6:
                    raise ValueError("Manual cast requires exactly 6 line values.")
                
                # 转换 MCP List[int] 为领域模型的 Tuple[LineValue, ...]
                lines = tuple(LineValue(v) for v in request.manual_records)
                manual_input = ManualCastingInput(lines=lines)
                result = self.service.cast_manual(manual_input)
            else:
                # 默认为随机起卦
                result = self.service.cast_random()

            # 2. 映射领域模型 HexagramResult 到 MCP 外部契约
            response_data = {
                "ben_gua": result.primary_hexagram.name,
                "bian_gua": result.changed_hexagram.name if result.changed_hexagram else "",
                "dong_yao": result.moving_line_positions
            }

            return types.CallToolResult(
                content=[types.TextContent(type="text", text=json.dumps(response_data, ensure_ascii=False))]
            )

        except Exception as e:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Hexagram casting failed: {str(e)}")],
                isError=True,
            )