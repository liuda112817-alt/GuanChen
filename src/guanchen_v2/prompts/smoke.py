TEXT_SMOKE_PROMPT = "请回复一句极短的确认信息，比如 'GUANCHEN_OK'，不需要其他标点或解释。"

_STRUCTURED_SMOKE_SOURCE = (
    "观尘 GuanChen v2 固定包含四个领域 Agent："
    "八字分析 Agent、解梦 Agent、六爻决策反思 Agent、传统文化知识 Agent。"
)


def build_structured_smoke_prompt() -> str:
    """构建结构化输出的纯函数。负责将任务指令与来源数据组合成 Prompt。"""
    return (
        "请提取出下列文本中的项目名称以及所有的 Agent 名称列表。\n\n"
        f"来源文本：\n{_STRUCTURED_SMOKE_SOURCE}"
    )
