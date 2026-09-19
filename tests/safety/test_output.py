import pytest

from guanchen_v2.safety.output import unsafe_output
from guanchen_v2.safety.rules import SafetyRuleEngine


@pytest.mark.parametrize(
    "text",
    [
        "你一定会患癌症",
        "你注定遭遇灾祸",
        "你活不过明年",
        "You will die next year.",
        "不用看医生，停药就行",
        "不能断言死亡，但你明年必遭灾祸",
        "你明年会患癌",
    ],
)
def test_blocks_deterministic_harm(text):
    assert unsafe_output(text)


@pytest.mark.parametrize("text", ["不能断言你一定会患癌症", "请咨询医生，传统文化不能诊断疾病。", "食神是传统术语。"])
def test_safe_education_is_retained(text):
    assert not unsafe_output(text)


@pytest.mark.parametrize("text", ["我 想 自 杀", "I want to kill myself", "我准备跳楼", "我想伤害自己", "今晚就去死"])
def test_crisis_normalization(text):
    assert SafetyRuleEngine().evaluate(text).action == "safe_response"
