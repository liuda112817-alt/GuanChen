from unittest.mock import patch

import pytest
from sqlalchemy import delete

from guanchen_v2.knowledge.errors import KnowledgeRetrievalError
from guanchen_v2.knowledge.persistence.database import async_session, engine, init_db
from guanchen_v2.knowledge.persistence.models import KnowledgeChunkRow, KnowledgeDocumentRow
from guanchen_v2.knowledge.retrieval.sparse import SparseRetriever

# 只有涉及真实 DB 重建及第三方库索引运算的才标记为 integration
pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def setup_database():
    """每次测试前重建并清空 Schema。"""
    await init_db()
    yield
    from guanchen_v2.knowledge.persistence.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _seed_data(session, chunk_id: str, title: str, section: str, text: str):
    doc_id = f"doc_{chunk_id}"
    doc = KnowledgeDocumentRow(
        document_id=doc_id,
        domain="bazi",
        source_title=title,
        source_type="project_note",
        section=section,
        text=text,
    )
    chunk = KnowledgeChunkRow(
        chunk_id=chunk_id,
        document_id=doc_id,
        domain="bazi",
        source_title=title,
        source_type="project_note",
        section=section,
        text=text,
        embedding=[0.1] * 512,
    )
    session.add(doc)
    session.add(chunk)


@pytest.mark.asyncio
async def test_sparse_lexical_match_and_zero_dropping():
    """验证真实的词汇命中排名，及 0 分绝不强凑人数的黄金准则。"""
    async with async_session() as session:
        await _seed_data(session, "c1", "《渊海子平》", "第一卷", "月令为提纲，不可轻忽。")
        await _seed_data(session, "c2", "《滴天髓》", "论用神", "用神发用，格局乃成。")
        await _seed_data(session, "c3", "无关文档", "无关章节", "这是一个风和日丽的下午。")
        await session.commit()

    retriever = SparseRetriever()
    await retriever.rebuild_index()

    hits = retriever.search("月令提纲", limit=5)
    # 词汇只命中了 c1，其余得分为 0，必须被坚决剔除！
    assert len(hits) == 1
    assert hits[0].chunk_id == "c1"


@pytest.mark.asyncio
async def test_sparse_metadata_is_searchable():
    """验证 Title 和 Section 确确实实参与了 Sparse 检索打分，而不仅是 Text。"""
    async with async_session() as session:
        # 正文中完全没有查询词，只在 Title 和 Section 中出现
        await _seed_data(session, "c1", "绝密行动文件", "代号九五二七", "今日天气真不错。")
        await _seed_data(session, "c2", "普通日记", "随笔", "今天也什么都没发生。")
        await session.commit()

    retriever = SparseRetriever()
    await retriever.rebuild_index()

    hits_title = retriever.search("绝密行动", limit=5)
    assert len(hits_title) == 1
    assert hits_title[0].chunk_id == "c1"

    hits_section = retriever.search("九五二七", limit=5)
    assert len(hits_section) == 1
    assert hits_section[0].chunk_id == "c1"


@pytest.mark.asyncio
async def test_sparse_rebuild_synchronizes_with_db_snapshot():
    """【绝对核心】证明重建过程是真的在实时抓取 DB 当前状态，一旦更新，旧索引灰飞烟灭。"""
    async with async_session() as session:
        await _seed_data(session, "old_chunk", "古籍", "上卷", "包含古老秘诀的旧文本。")
        await session.commit()

    retriever = SparseRetriever()
    await retriever.rebuild_index()
    assert len(retriever.search("古老秘诀", limit=5)) == 1

    # 物理抹除旧文档，并插入新文档
    async with async_session() as session:
        await session.execute(
            delete(KnowledgeChunkRow).where(KnowledgeChunkRow.chunk_id == "old_chunk")
        )
        await _seed_data(session, "new_chunk", "新编", "下卷", "包含现代科学的新见解。")
        await session.commit()

    # 执行关键的原子刷新
    await retriever.rebuild_index()

    # 验证检索，证实旧世界的崩塌与新世界的建立
    assert len(retriever.search("古老秘诀", limit=5)) == 0  # 旧内容彻底下线
    assert len(retriever.search("现代科学", limit=5)) == 1
    assert retriever.search("现代科学", limit=5)[0].chunk_id == "new_chunk"


@pytest.mark.asyncio
async def test_sparse_atomic_rebuild_fallback_on_failure():
    """验证如果正在执行重组时崩溃，原有的有效索引绝不被摧毁，且错误被精准隔离。"""
    async with async_session() as session:
        await _seed_data(session, "c1", "A", "B", "有效的初版数据")
        await session.commit()

    retriever = SparseRetriever()
    await retriever.rebuild_index()
    assert len(retriever.search("有效", limit=5)) == 1

    # 拦截 Jieba 引发崩溃，这应该被隔离在 Phase B，绝不会被报成数据库错误
    with patch(
        "guanchen_v2.knowledge.retrieval.sparse.jieba.lcut",
        side_effect=Exception("Jieba 分词器内存溢出！"),
    ):
        with pytest.raises(KnowledgeRetrievalError, match="Jieba 分词与 BM25s 第三方构建过程崩溃"):
            await retriever.rebuild_index()

    # 初版索引必须安然无恙并照常服务
    hits_after_crash = retriever.search("有效", limit=5)
    assert len(hits_after_crash) == 1
    assert hits_after_crash[0].chunk_id == "c1"
