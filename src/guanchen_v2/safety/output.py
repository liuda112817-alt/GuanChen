"""Check complete answers before persistence or streaming any text."""

import re
import unicodedata

SAFE_OUTPUT = (
    "本次生成内容包含不适当的确定性判断，已停止展示。传统文化解读只能用于文化参考和现实反思，"
    "不能断言灾祸、死亡或疾病，也不能替代医疗、法律或投资决策。"
)

_ASSERTIONS = re.compile(
    r"(?:必定|必然|一定|注定|肯定|必会|必将|必死|必有|必患|活不过|逃不过|必遭|必得|必亡|必败|必破产|百分之百|100%|guaranteed|definitely|certainly)"
    r"[^。！？\n]{0,28}(?:死|亡|癌|病|灾|祸|伤残|破产|血光|die|death|cancer)"
    r"|(?:你|您)[^。！？\n]{0,12}(?:死期|寿命只有|活不过|命中有癌|必死|必亡)"
    r"|(?:你|您)[^。！？\n]{0,8}(?:会|将)[^。！？\n]{0,12}(?:患癌|死亡|死去|患上|得癌|遭遇灾祸)"
    r"|(?:停药|停止治疗|拒绝治疗|放弃治疗|不用看医生|不要去医院)"
    r"|(?:you|your)[^.!?\n]{0,30}(?:willdie|willgetcancer|deathisinevitable)"
)


def unsafe_output(text: str) -> bool:
    normalized = re.sub(r"[ \t]", "", unicodedata.normalize("NFKC", text)).lower()
    # Ignore explicit negations of deterministic prediction, but not adjacent assertions.
    for sentence in re.split(r"[。！？；;，,\n]", normalized):
        if _ASSERTIONS.search(sentence) and not re.search(r"(?:不能|不得|不会|不应|不要|无法).{0,10}(?:断言|预测|说|认定|认为)", sentence):
            return True
    return False


def protect_response(response):
    if unsafe_output(response.content):
        return response.model_copy(update={"content": SAFE_OUTPUT, "citations": (), "output_blocked": True})
    return response
