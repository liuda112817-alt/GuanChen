from unittest.mock import MagicMock, patch

import pytest

from guanchen_v2.knowledge.errors import KnowledgeRerankerError, KnowledgeRetrievalError
from guanchen_v2.knowledge.models import KnowledgeDomain, RrfSearchHit, SourceType
from guanchen_v2.knowledge.rerank_adapter import BgeRerankerAdapter
from guanchen_v2.knowledge.retrieval.rerank import KnowledgeReranker


def _create_rrf_hit(chunk_id: str, rrf_score: float) -> RrfSearchHit:
    return RrfSearchHit(
        chunk_id=chunk_id,
        document_id="doc",
        domain=KnowledgeDomain.BAZI,
        source_title="T",
        source_type=SourceType.PROJECT_NOTE,
        section="S",
        text="内容",
        score=rrf_score,
        dense_rank=None,
        sparse_rank=None,
    )


# ---------------------------------------------------------
# Part 1: KnowledgeReranker 业务边界断言
# ---------------------------------------------------------


def test_reranker_limit_must_happen_after_scoring():
    """【绝对核心】必须保证先洗牌后截断！原先排位低的也能逆风翻盘！"""
    hits = [
        _create_rrf_hit("RRF_王牌", 0.9),
        _create_rrf_hit("RRF_亚军", 0.8),
        _create_rrf_hit("RRF_黑马", 0.1),
    ]

    adapter = MagicMock(spec=BgeRerankerAdapter)
    # 给黑马打最高分
    adapter.score_pairs.return_value = [1.1, -2.5, 99.9]
    reranker = KnowledgeReranker(adapter)

    results = reranker.rerank("Query", hits, limit=2)
    assert len(results) == 2
    assert results[0].chunk_id == "RRF_黑马"


def test_reranker_passage_construction_exact_format():
    """保证交给大模型的文本是精准的三段式融合体。"""
    hit = _create_rrf_hit("A", 0.5)
    adapter = MagicMock(spec=BgeRerankerAdapter)
    adapter.score_pairs.return_value = [0.8]

    KnowledgeReranker(adapter).rerank("找线索", [hit], limit=5)

    adapter.score_pairs.assert_called_once()
    pairs = adapter.score_pairs.call_args[0][0]
    assert pairs == [("找线索", "T\nS\n内容")]


def test_reranker_tie_breaking_prioritizes_rrf_history():
    """当大模型打分无法区分时，必须坚决沿用原先 RRF 给出的光荣名次！"""
    hits = [_create_rrf_hit("A", 0.8), _create_rrf_hit("B", 0.5)]
    adapter = MagicMock(spec=BgeRerankerAdapter)
    adapter.score_pairs.return_value = [9.9, 9.9]

    results = KnowledgeReranker(adapter).rerank("Q", hits, limit=5)
    assert results[0].chunk_id == "A"
    assert results[1].chunk_id == "B"


def test_reranker_is_immune_to_raw_rrf_score():
    """【新补充】证明原生的 RRF 分数有多高都没用，大模型不看，打分也不受它影响。"""
    hits_normal = [_create_rrf_hit("A", 0.9), _create_rrf_hit("B", 0.8)]
    hits_crazy = [_create_rrf_hit("A", 999.9), _create_rrf_hit("B", -999.9)]

    adapter = MagicMock(spec=BgeRerankerAdapter)
    # 不管 RRF 分多少，大模型只根据自己看到的文本，给出固定的 5.0 和 10.0
    adapter.score_pairs.return_value = [5.0, 10.0]

    res_normal = KnowledgeReranker(adapter).rerank("Q", hits_normal, limit=5)
    res_crazy = KnowledgeReranker(adapter).rerank("Q", hits_crazy, limit=5)

    # 只要 RRF 的顺序没变，模型打分没变，输出排序必须一模一样 (此时 B 大获全胜)
    assert res_normal[0].chunk_id == res_crazy[0].chunk_id == "B"


def test_reranker_empty_hits_safeguard():
    """【新补充】空候选时，大模型应该能舒舒服服地睡大觉，不被唤醒。"""
    adapter = MagicMock(spec=BgeRerankerAdapter)
    res = KnowledgeReranker(adapter).rerank("Q", [], limit=5)

    assert res == []
    adapter.score_pairs.assert_not_called()


def test_reranker_error_boundaries_safeguards():
    """非法参数验证。"""
    hit = _create_rrf_hit("A", 0.5)
    reranker = KnowledgeReranker(MagicMock())

    with pytest.raises(KnowledgeRetrievalError):
        reranker.rerank("  ", [hit], limit=5)

    with pytest.raises(KnowledgeRetrievalError):
        reranker.rerank("Q", [hit], limit=0)


# ---------------------------------------------------------
# Part 2: BgeRerankerAdapter 异形张量防线断言
# ---------------------------------------------------------


@patch("guanchen_v2.knowledge.rerank_adapter.CrossEncoder")
def test_adapter_intercepts_shape_mismatches(mock_ce):
    """【新补充】防范第三方返回数量不对等或多维嵌套张量。"""
    mock_model = MagicMock()
    mock_ce.return_value = mock_model
    adapter = BgeRerankerAdapter()

    pairs = [("Q", "P1"), ("Q", "P2")]

    # 场景 1：数量不对齐 (给了 2 个返回 1 个)
    mock_model.predict.return_value = [1.5]
    with pytest.raises(KnowledgeRerankerError, match="评分数量与输入对数量不匹配"):
        adapter.score_pairs(pairs)

    # 场景 2：二元分类格式 (多维列表)，试图 float([1.2, 0.4]) 时引发爆炸
    mock_model.predict.return_value = [[1.2, 0.4], [0.9, 0.1]]
    with pytest.raises(KnowledgeRerankerError, match="非标量结构或无法转为浮点数"):
        adapter.score_pairs(pairs)


@patch("guanchen_v2.knowledge.rerank_adapter.CrossEncoder")
def test_adapter_intercepts_infinite_numbers(mock_ce):
    """【新补充】防范大模型彻底丧失理智，抛出无穷大或 NaN。"""
    mock_model = MagicMock()
    mock_ce.return_value = mock_model
    adapter = BgeRerankerAdapter()

    pairs = [("Q", "P")]
    mock_model.predict.return_value = [float("inf")]

    with pytest.raises(KnowledgeRerankerError, match="非法的无穷数值打分"):
        adapter.score_pairs(pairs)
