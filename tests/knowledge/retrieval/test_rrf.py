import math

import pytest

from guanchen_v2.knowledge.errors import KnowledgeRetrievalError
from guanchen_v2.knowledge.models import (
    DenseSearchHit,
    KnowledgeDomain,
    SourceType,
    SparseSearchHit,
)
from guanchen_v2.knowledge.retrieval.rrf import ReciprocalRankFusion


def _create_dense(chunk_id: str, score: float, text: str = "统一内容") -> DenseSearchHit:
    return DenseSearchHit(
        chunk_id=chunk_id,
        document_id="doc_1",
        domain=KnowledgeDomain.BAZI,
        source_title="《渊海子平》",
        source_type=SourceType.PUBLIC_DOMAIN_CLASSIC,
        section="第一卷",
        text=text,
        score=score,
    )


def _create_sparse(chunk_id: str, score: float, text: str = "统一内容") -> SparseSearchHit:
    return SparseSearchHit(
        chunk_id=chunk_id,
        document_id="doc_1",
        domain=KnowledgeDomain.BAZI,
        source_title="《渊海子平》",
        source_type=SourceType.PUBLIC_DOMAIN_CLASSIC,
        section="第一卷",
        text=text,
        score=score,
    )


def test_rrf_joint_support_boosts_ranking():
    """【绝对核心】证明被双边同时支持的内容必定获得超额的排名奖励！"""
    dense_hits = [
        _create_dense("A", 0.99),  # rank 1
        _create_dense("B", 0.88),  # rank 2
        _create_dense("C", 0.77),  # rank 3
    ]
    sparse_hits = [
        _create_sparse("B", 10.5),  # rank 1
        _create_sparse("D", 8.2),  # rank 2
        _create_sparse("A", 5.1),  # rank 3
    ]

    rrf = ReciprocalRankFusion()
    hits = rrf.fuse(dense_hits, sparse_hits, limit=5)

    # 候选池必须是 A, B, C, D 四个的并集 (Union)
    assert len(hits) == 4

    # 因为 B 拿到了 1/62 + 1/61，而 A 是 1/61 + 1/63，B 必然会挤掉 A 成为总榜冠军！
    assert hits[0].chunk_id == "B"
    assert math.isclose(hits[0].score, (1.0 / 62) + (1.0 / 61))
    assert hits[0].dense_rank == 2
    assert hits[0].sparse_rank == 1

    assert hits[1].chunk_id == "A"
    assert math.isclose(hits[1].score, (1.0 / 61) + (1.0 / 63))


def test_rrf_is_immune_to_raw_scores():
    """证明原生打分再夸张，只要在各阵营名次不变，最终结果必须坚若磐石。"""
    # 极度普通的打分
    d_normal = [_create_dense("A", 0.99), _create_dense("B", 0.88)]
    s_normal = [_create_sparse("B", 10.5), _create_sparse("C", 8.2)]

    # 极度畸形的打分 (但名次没变)
    d_crazy = [_create_dense("A", -99.9), _create_dense("B", -999.0)]
    s_crazy = [_create_sparse("B", 10000.5), _create_sparse("C", 0.0001)]

    rrf = ReciprocalRankFusion()
    hits_normal = rrf.fuse(d_normal, s_normal, limit=5)
    hits_crazy = rrf.fuse(d_crazy, s_crazy, limit=5)

    for hn, hc in zip(hits_normal, hits_crazy):
        assert hn.chunk_id == hc.chunk_id
        assert math.isclose(hn.score, hc.score)


def test_rrf_single_source_survival():
    """证明如果某一阵营全军覆没，单一阵营依然可以撑起场子。"""
    hits = ReciprocalRankFusion().fuse([_create_dense("A", 0.9)], [], limit=5)
    assert len(hits) == 1
    assert hits[0].dense_rank == 1
    assert hits[0].sparse_rank is None


def test_rrf_tie_breaking_determinism():
    """同分平局下，字典序升序铁律！"""
    # A 和 Z 都是仅在各自榜单排第一，得分都是 1/61
    d_hits = [_create_dense("chunk_z", 0.9)]
    s_hits = [_create_sparse("chunk_a", 10.0)]

    hits = ReciprocalRankFusion().fuse(d_hits, s_hits, limit=5)
    assert math.isclose(hits[0].score, hits[1].score)
    assert hits[0].chunk_id == "chunk_a"
    assert hits[1].chunk_id == "chunk_z"


def test_rrf_invariants_blocker():
    """铁幕测试：禁止单阵营重复交卷、禁止跨阵营造假元数据！"""
    rrf = ReciprocalRankFusion()

    # 1. 阵营内部串票拦截
    with pytest.raises(KnowledgeRetrievalError, match="Dense 内出现了重复提交"):
        rrf.fuse([_create_dense("A", 0.9), _create_dense("A", 0.8)], [], limit=5)

    # 2. 跨阵营数据不一致拦截
    d_mismatch = [_create_dense("A", 0.9, text="正统旧版数据")]
    s_mismatch = [_create_sparse("A", 10.0, text="被篡改的新版数据")]
    with pytest.raises(KnowledgeRetrievalError, match="元数据出现脏乱分歧"):
        rrf.fuse(d_mismatch, s_mismatch, limit=5)

    # 3. Limit 保护
    with pytest.raises(KnowledgeRetrievalError, match="大于 0"):
        rrf.fuse([], [], limit=-1)
