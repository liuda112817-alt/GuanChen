import pytest

from guanchen_v2.knowledge.rerank_adapter import BgeRerankerAdapter

pytestmark = pytest.mark.smoke


def test_real_model_smoke_adapter():
    """
    这只是个证明模型能下载、能启动、能生成分数的冒烟测试，不管排序质量好坏。
    只有当你显式执行 pytest -m smoke 时，它才会去下载上 GB 的模型。
    """
    adapter = BgeRerankerAdapter()

    try:
        # 给模型送过去两套文本对
        pairs = [
            ("八字里的月令是什么？", "月令为提纲，不可轻忽。\n\n这正是在说八字的重点"),
            ("八字里的月令是什么？", "今天去吃了红烧肉，非常美味。"),
        ]

        scores = adapter.score_pairs(pairs)

        # 证明返回结果是干净、无污染、无越界的纯浮点数
        assert len(scores) == 2
        assert isinstance(scores[0], float)
        assert isinstance(scores[1], float)

    except Exception as e:
        pytest.fail(f"真实大模型冒烟测试失败：{e}")
