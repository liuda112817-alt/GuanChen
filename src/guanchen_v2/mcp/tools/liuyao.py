from pydantic import BaseModel, Field

from guanchen_v2.mcp.security.permissions import Permission


class LiuyaoCastInput(BaseModel):
    question: str = Field(..., description="The decision question being asked.")
    method: str = Field("random", description="Casting method: 'random' or 'manual'")
    manual_records: list[int] = Field(default_factory=list, description="Manual cast values if method is 'manual' (list of 6 ints).")


def get_liuyao_tool_definition() -> dict:
    return {
        "name": "liuyao.cast_hexagram",
        "description": "Cast a Liuyao hexagram based on the given question.",
        "inputSchema": LiuyaoCastInput.model_json_schema(),
        "permission": Permission.LIUYAO_READ.value
    }