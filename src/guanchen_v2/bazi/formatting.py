"""Render deterministic facts without a model translating numeric units."""

from guanchen_v2.models.bazi import BaziChart


def render_bazi_facts(chart: BaziChart) -> str:
    pillars = [("年", chart.year_pillar), ("月", chart.month_pillar), ("日", chart.day_pillar), ("时", chart.hour_pillar)]
    lines = [
        "【排盘事实】",
        "四柱：" + "；".join(f"{label}柱 {pillar.gan_zhi.gan_zhi}" for label, pillar in pillars),
        f"日主：{chart.day_master.value}",
    ]
    for label, pillar in pillars:
        hidden = "、".join(f"{stem.stem.value}（{stem.ten_god.value}）" for stem in pillar.hidden_stems)
        lines.append(f"{label}支藏干：{hidden}")
    offset = chart.da_yun.start_offset
    lines.append(f"起运偏移：{offset.years} 年 {offset.months} 个月 {offset.days} 天 {offset.hours} 小时")
    lines.append(f"起运时间：{chart.da_yun.start_at}")
    return "\n".join(lines)
