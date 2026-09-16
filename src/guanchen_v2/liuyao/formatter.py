from guanchen_v2.models.liuyao import CastingMethod, HexagramResult


def format_hexagram_facts_for_prompt(hexagram: HexagramResult) -> str:
    parts = []

    method_str = "手工指定" if hexagram.casting_method == CastingMethod.MANUAL_SIX_LINES else "系统三枚硬币"
    parts.append(f"起卦方式：{method_str}")

    p_hex = hexagram.primary_hexagram
    p_name = f" ({p_hex.name}卦)" if p_hex.name else ""
    parts.append(f"\n本卦：上{p_hex.upper_trigram} 下{p_hex.lower_trigram}{p_name}")

    if hexagram.changed_hexagram:
        c_hex = hexagram.changed_hexagram
        c_name = f" ({c_hex.name}卦)" if c_hex.name else ""
        parts.append(f"变卦：上{c_hex.upper_trigram} 下{c_hex.lower_trigram}{c_name}")

    if hexagram.moving_line_positions:
        moves = "、".join([f"第{pos}爻" for pos in hexagram.moving_line_positions])
        parts.append(f"动爻位置：{moves}")
    else:
        parts.append("动爻位置：无动爻 (静卦)")

    parts.append("\n六爻确定性事实 (初爻 -> 上爻)：")
    for line in hexagram.lines:
        line_parts = [f"第{line.position}爻: {line.polarity.value}", "动" if line.moving else "静"]
        if line.heavenly_stem and line.earthly_branch:
            line_parts.append(f"干支={line.heavenly_stem}{line.earthly_branch}")
        if line.element:
            line_parts.append(f"五行={line.element}")
        if line.six_relative:
            line_parts.append(f"六亲={line.six_relative}")
        if line.is_shi:
            line_parts.append("[世爻]")
        if line.is_ying:
            line_parts.append("[应爻]")

        parts.append(" | ".join(line_parts))

    return "\n".join(parts)


def format_evidence_for_prompt(results: list) -> str:
    if not results:
        return "当前未检索到相关传统证据支持。"

    parts = []
    for idx, res in enumerate(results, 1):
        parts.append(f"[Evidence {idx}]\nchunk_id: {res.chunk_id}\nsource_title: {res.source_title}\ntext: {res.text}\n")
    return "\n".join(parts)
