from typing import Any

from langchain_core.tools import BaseTool, tool

from guanchen_v2.bazi.service import BaziService
from guanchen_v2.models.bazi import BirthProfile, Gender


def build_calculate_bazi_tool(service: BaziService) -> BaseTool:
    """创建并返回针对 LLM 环境的排盘工具。"""

    @tool("calculate_bazi", args_schema=BirthProfile)
    def calculate_bazi(
        year: int,
        month: int,
        day: int,
        hour: int,
        minute: int,
        gender: Gender,
        birth_place_text: str | None = None,
    ) -> dict[str, Any]:
        """
        根据完整的公历出生年月日时分与性别执行确定性八字排盘，返回四柱、日主、十神、藏干和大运基础结果。
        仅用于排盘事实计算，不负责命理解读。
        出生资料缺失时不要调用；出生地文本在 v2.0 不参与计算。
        """
        # 将展平的参数重组为领域模型。这里由 Pydantic schema 先行验证。
        profile = BirthProfile(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            gender=gender,
            birth_place_text=birth_place_text,
        )

        # 调用业务服务进行计算
        chart = service.calculate(profile)

        # 强制转换为 JSON 兼容的字典结构，防止不可控的文本拼接
        return chart.model_dump(mode="json")

    return calculate_bazi
