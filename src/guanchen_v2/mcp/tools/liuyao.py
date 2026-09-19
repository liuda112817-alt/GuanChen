from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from guanchen_v2.liuyao.casting import ManualCastingInput


class LiuyaoCastInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["random", "manual"] = "random"
    manual: ManualCastingInput | None = None

    @model_validator(mode="after")
    def validate_method(self):
        if (self.method == "manual") != (self.manual is not None):
            raise ValueError("manual input must be supplied exactly when method is manual")
        return self


def get_liuyao_tool_definition() -> dict:
    return {
        "name": "cast_hexagram",
        "description": "Cast once after host confirmation; returns complete HexagramResult facts.",
        "inputSchema": LiuyaoCastInput.model_json_schema(),
        "permission": "liuyao.read",
    }
