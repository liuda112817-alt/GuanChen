from unittest.mock import MagicMock

import pytest

from guanchen_v2.knowledge.embeddings import BgeEmbeddingAdapter
from guanchen_v2.knowledge.models import KnowledgeDomain, RetrievalFilter, SourceType
from guanchen_v2.knowledge.persistence.database import async_session, engine, init_db
from guanchen_v2.knowledge.persistence.models import KnowledgeChunkRow, KnowledgeDocumentRow
from guanchen_v2.knowledge.retrieval.dense import DenseRetriever
from guanchen_v2.knowledge.retrieval.sparse import SparseRetriever

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def setup_database():
    await init_db()
    yield
    from guanchen_v2.knowledge.persistence.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _seed_data(
    session, chunk_id: str, domain: str, source_type: str, text: str, score_tier: float
):
    doc_id = f"doc_{chunk_id}"
    doc = KnowledgeDocumentRow(
        document_id=doc_id,
        domain=domain,
        source_title="T",
        source_type=source_type,
        section="S",
        text=text,
    )
    # 为 Dense 控制打分：Query 为 [1, 0...]。
    # score_tier = 1 -> vec=[1, 0...] 距离0，最高分
    # score_tier = 0.5 -> vec=[√0.5, √0.5...] 中等分
    # score_tier = 0 -> vec=[0, 1...] 距离1，最低分
    import math

    if score_tier == 1.0:
        vec = [0.0] * 512
        vec[0] = 1.0
    elif score_tier == 0.5:
        vec = [0.0] * 512
        vec[0] = math.sqrt(0.5)
        vec[1] = math.sqrt(0.5)
    else:
        vec = [0.0] * 512
        vec[1] = 1.0

    chunk = KnowledgeChunkRow(
        chunk_id=chunk_id,
        document_id=doc_id,
        domain=domain,
        source_title="T",
        source_type=source_type,
        section="S",
        text=text,
        embedding=vec,
    )
    session.add(doc)
    session.add(chunk)


@pytest.mark.asyncio
async def test_filter_must_happen_before_limit():
    """【绝对核心】证明过滤器没有把本该排上号的合法文档挤出局。"""
    async with async_session() as session:
        # 六爻的文档靠得极近（极其相关）
        await _seed_data(
            session, "L1", "liuyao", "project_note", "相关词汇极高 相关词汇", score_tier=1.0
        )
        await _seed_data(
            session, "L2", "liuyao", "project_note", "相关词汇极高 相关词汇", score_tier=1.0
        )
        await _seed_data(
            session, "L3", "liuyao", "project_note", "相关词汇极高 相关词汇", score_tier=1.0
        )
        # 八字的文档相较之下距离较远（或命中词较少）
        await _seed_data(session, "B1", "bazi", "project_note", "相关词汇", score_tier=0.5)
        await _seed_data(session, "B2", "bazi", "project_note", "相关词汇", score_tier=0.5)
        await session.commit()

    # 查询：强制只要 八字 (bazi)，且只要 2 条。
    filters = RetrievalFilter(domains=frozenset({KnowledgeDomain.BAZI}))

    # 1. 验证 Dense
    adapter = MagicMock(spec=BgeEmbeddingAdapter)
    q_vec = [0.0] * 512
    q_vec[0] = 1.0
    adapter.embed_query.return_value = q_vec
    dense = DenseRetriever(adapter)

    d_hits = await dense.search("...", limit=2, filters=filters)
    # 绝不能是空列表（如果 Limit 在过滤之前，那前三名全是六爻被吃掉，剩0条就是巨大Bug）
    assert len(d_hits) == 2
    assert all(h.domain == KnowledgeDomain.BAZI for h in d_hits)

    # 2. 验证 Sparse
    sparse = SparseRetriever()
    await sparse.rebuild_index()
    s_hits = sparse.search("相关词汇", limit=2, filters=filters)

    assert len(s_hits) == 2
    assert all(h.domain == KnowledgeDomain.BAZI for h in s_hits)


@pytest.mark.asyncio
async def test_filter_cross_field_and_same_field_or_semantics():
    """证明跨字段 AND，同字段 OR 的共享契约。"""
    async with async_session() as session:
        # 满足条件：八字 + 经典
        await _seed_data(session, "A", "bazi", "public_domain_classic", "特定文本", 1.0)
        # 满足条件：易经 + 经典
        await _seed_data(session, "B", "yijing", "public_domain_classic", "特定文本", 1.0)
        # 不满足条件：八字 + 个人笔记 (跨字段 AND 失败)
        await _seed_data(session, "C", "bazi", "project_note", "特定文本", 1.0)
        await session.commit()

    # 条件： (bazi OR yijing) AND (classic)
    filters = RetrievalFilter(
        domains=frozenset({KnowledgeDomain.BAZI, KnowledgeDomain.YIJING}),
        source_types=frozenset({SourceType.PUBLIC_DOMAIN_CLASSIC}),
    )

    # 因为 Dense/Sparse 都共用这一契约，抽一个查验即可 (以 Sparse 为例)
    sparse = SparseRetriever()
    await sparse.rebuild_index()
    s_hits = sparse.search("特定文本", limit=10, filters=filters)

    assert len(s_hits) == 2
    returned_ids = {h.chunk_id for h in s_hits}
    assert "A" in returned_ids
    assert "B" in returned_ids
    assert "C" not in returned_ids  # C 被铁面无私地拦截了


@pytest.mark.asyncio
async def test_filter_no_match_returns_empty_safely():
    """证明空匹配不会引发崩溃，只是返回空数组。"""
    async with async_session() as session:
        await _seed_data(session, "C1", "bazi", "project_note", "绝密行动", 1.0)
        await session.commit()

    # 故意刁难：找一本根本没入库的书
    filters = RetrievalFilter(source_titles=frozenset({"《神鬼传奇》"}))

    sparse = SparseRetriever()
    await sparse.rebuild_index()
    s_hits = sparse.search("绝密行动", limit=5, filters=filters)
    assert s_hits == []
