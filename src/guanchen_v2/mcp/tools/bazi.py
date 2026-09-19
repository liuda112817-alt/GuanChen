from guanchen_v2.models.bazi import BirthProfile

BaziCalculateInput = BirthProfile


def get_bazi_tool_definition() -> dict:
    return {
        "name": "calculate_bazi",
        "description": "Calculate a structured Bazi chart from birth information.",
        "inputSchema": BirthProfile.model_json_schema(),
        "permission": "bazi.read",
    }
