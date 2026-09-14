import pytest

from guanchen_v2.knowledge.errors import KnowledgeRetrievalError
from guanchen_v2.knowledge.models import (
    Citation,
    KnowledgeDomain,
    RerankedSearchHit,
    RrfSearchHit,
    SourceType,
)
from guanchen_v2.knowledge.retrieval.assembler import RetrievalResultAssembler


def _create_rrf(chunk_id: str, score: float) -> RrfSearchHit:
    return RrfSearchHit(
        chunk_id=chunk_id,
        document_id="doc1",
        domain=KnowledgeDomain.BAZI,
        source_title="T",
        source_type=SourceType.PROJECT_NOTE,
        section="S",
        text="TXT",
        score=score,
        dense_rank=1,
        sparse_rank=2,
    )


def _create_reranked(chunk_id: str, reranker_score: float, rrf_rank: int) -> RerankedSearchHit:
    return RerankedSearchHit(
        chunk_id=chunk_id,
        document_id="doc1",
        domain=KnowledgeDomain.BAZI,
        source_title="T",
        source_type=SourceType.PROJECT_NOTE,
        section="S",
        text="TXT",
        score=reranker_score,
        rrf_score=0.9,
        rrf_rank=rrf_rank,
        dense_rank=1,
        sparse_rank=2,
    )


def test_assembler_from_rrf_preserves_order_and_sets_none():
    """证明 Assembler 不会再自作主张对分数进行排序。"""
    # 故意打乱分数，证明我们只信任位置 (Position)
    hits = [
        _create_rrf("A", 0.1),
        _create_rrf("B", 0.9),
    ]

    results = RetrievalResultAssembler().from_rrf(hits)

    assert len(results) == 2

    assert results[0].chunk_id == "A"
    assert results[0].rank == 1
    assert results[0].rrf_rank == 1
    assert results[0].reranker_score is None  # 完美证明没有开重排

    assert results[1].chunk_id == "B"
    assert results[1].rank == 2


def test_assembler_from_reranked_preserves_old_ranks():
    """证明重排后，旧有的 RRF 名次作为重要探针被原样刻录保留。"""
    hits = [
        _create_reranked("A", reranker_score=9.9, rrf_rank=17),  # 从底层杀上来的黑马
        _create_reranked("B", reranker_score=1.1, rrf_rank=1),  # 被挤下来的前冠军
    ]

    results = RetrievalResultAssembler().from_reranked(hits)

    assert results[0].chunk_id == "A"
    assert results[0].rank == 1  # 当前最终第一名
    assert results[0].rrf_rank == 17  # 探针完美保留

    assert results[1].chunk_id == "B"
    assert results[1].rank == 2
    assert results[1].rrf_rank == 1


def test_assembler_fails_fast_on_duplicates():
    """防伪测试：决不允许两个相同的 chunk_id 出现在同一个最终大名单里。"""
    hits = [_create_rrf("A", 0.9), _create_rrf("A", 0.8)]

    with pytest.raises(KnowledgeRetrievalError, match="发现了重复的 chunk_id"):
        RetrievalResultAssembler().from_rrf(hits)


def test_citation_mapping_is_clean():
    """证明 Citation 不带正文、不带算法分，只带血缘。"""
    hit = _create_rrf("C123", 0.9)
    res = RetrievalResultAssembler().from_rrf([hit])[0]

    citation = Citation.from_retrieval_result(res)

    assert citation.chunk_id == "C123"
    assert citation.document_id == "doc1"
    assert citation.source_title == "T"
    assert citation.section == "S"

    # 彻底杜绝越权获取正文或算法分数
    assert not hasattr(citation, "text")
    assert not hasattr(citation, "score")
    assert not hasattr(citation, "rank")


def test_assembler_empty_lists():
    assert RetrievalResultAssembler().from_rrf([]) == []
    assert RetrievalResultAssembler().from_reranked([]) == []
