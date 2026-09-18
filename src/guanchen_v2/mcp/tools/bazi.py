from pydantic import BaseModel, Field
from guanchen_v2.mcp.security.permissions import Permission


class BaziCalculateInput(BaseModel):
    year: int = Field(..., description="Birth year (e.g., 1990)")
    month: int = Field(..., description="Birth month (1-12)")
    day: int = Field(..., description="Birth day (1-31)")
    hour: int = Field(..., description="Birth hour (0-23)")
    minute: int = Field(..., description="Birth minute (0-59)")
    gender: str = Field(..., description="Gender: 'male' or 'female'")


def get_bazi_tool_definition() -> dict:
    return {
        "name": "bazi.calculate",
        "description": "Calculate a structured Bazi chart from birth information.",
        "inputSchema": BaziCalculateInput.model_json_schema(),
        "permission": Permission.BAZI_READ.value
    }