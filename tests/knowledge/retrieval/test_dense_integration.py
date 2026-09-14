import math
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import DBAPIError

from guanchen_v2.knowledge.embeddings import BgeEmbeddingAdapter
from guanchen_v2.knowledge.errors import KnowledgeEmbeddingError, KnowledgeRetrievalError
from guanchen_v2.knowledge.persistence.database import async_session, engine, init_db
from guanchen_v2.knowledge.persistence.models import KnowledgeChunkRow, KnowledgeDocumentRow
from guanchen_v2.knowledge.retrieval.dense import DenseRetriever

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def setup_database():
    """每次测试前重建并清空 Schema。"""
    await init_db()
    yield
    from guanchen_v2.knowledge.persistence.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _seed_data(session, chunk_id: str, vector: list[float]):
    """由于 FK 约束，每次插入 Chunk 都必须伴生 Document"""
    doc_id = f"doc_{chunk_id}"
    doc = KnowledgeDocumentRow(
        document_id=doc_id,
        domain="bazi",
        source_title="T",
        source_type="project_note",
        section="S",
        text="T",
    )
    chunk = KnowledgeChunkRow(
        chunk_id=chunk_id,
        document_id=doc_id,
        domain="bazi",
        source_title="T",
        source_type="project_note",
        section="S",
        text="T",
        embedding=vector,
    )
    session.add(doc)
    session.add(chunk)


def _mock_adapter_with_query_vector(q_vector: list[float]):
    adapter = MagicMock(spec=BgeEmbeddingAdapter)
    adapter.embed_query.return_value = q_vector
    return adapter


@pytest.mark.asyncio
async def test_dense_retrieval_cosine_mathematics():
    """
    【绝对核心测试】真实 pgvector 库的余弦相似度运算验证！
    Q = [1, 0, ...],
    A = [1, 0, ...], 理论相似度: 1.0
    B = [√0.5, √0.5, 0...], 理论相似度: ~0.707
    C = [0, 1, ...], 理论相似度: 0.0
    """
    # 构造完美数学几何关系的向量
    q_vec = [0.0] * 512
    q_vec[0] = 1.0

    vec_a = [0.0] * 512
    vec_a[0] = 1.0
    vec_b = [0.0] * 512
    vec_b[0] = math.sqrt(0.5)
    vec_b[1] = math.sqrt(0.5)
    vec_c = [0.0] * 512
    vec_c[1] = 1.0

    async with async_session() as session:
        await _seed_data(session, "chunk_c", vec_c)
        await _seed_data(session, "chunk_a", vec_a)
        await _seed_data(session, "chunk_b", vec_b)
        await session.commit()

    retriever = DenseRetriever(_mock_adapter_with_query_vector(q_vec))
    hits = await retriever.search("哪怕传入天书，Mock 也会返回强行指定的 q_vec", limit=3)

    # 因为 Limit 没超，必须找齐 3 个
    assert len(hits) == 3

    # 排序与相关性必须按余弦几何铁律倒置
    assert hits[0].chunk_id == "chunk_a"
    assert math.isclose(hits[0].score, 1.0, rel_tol=1e-5)

    assert hits[1].chunk_id == "chunk_b"
    assert math.isclose(hits[1].score, 0.707106, rel_tol=1e-5)

    assert hits[2].chunk_id == "chunk_c"
    assert math.isclose(hits[2].score, 0.0, rel_tol=1e-5)


@pytest.mark.asyncio
async def test_dense_retrieval_limit_contract():
    """验证 Limit 参数的边界拦截与正确截断效果"""
    vec = [0.0] * 512
    vec[0] = 1.0

    async with async_session() as session:
        await _seed_data(session, "c1", vec)
        await _seed_data(session, "c2", vec)
        await _seed_data(session, "c3", vec)
        await session.commit()

    retriever = DenseRetriever(_mock_adapter_with_query_vector(vec))

    # 限制 2 条，哪怕有 3 条完全一样的，也绝不逾越
    hits = await retriever.search("query", limit=2)
    assert len(hits) == 2

    # 输入保护
    with pytest.raises(KnowledgeRetrievalError, match="必须大于 0"):
        await retriever.search("query", limit=0)
    with pytest.raises(KnowledgeRetrievalError, match="必须大于 0"):
        await retriever.search("query", limit=-1)


@pytest.mark.asyncio
async def test_dense_retrieval_tie_breaking_determinism():
    """验证平局打破机制：当多条内容距离完全相同时，必须由 chunk_id 强制排定次序"""
    vec = [0.0] * 512
    vec[0] = 1.0

    async with async_session() as session:
        # 为了打破偶然因素，我们乱序打入数据库
        await _seed_data(session, "chunk_z", vec)
        await _seed_data(session, "chunk_a", vec)
        await _seed_data(session, "chunk_x", vec)
        await session.commit()

    retriever = DenseRetriever(_mock_adapter_with_query_vector(vec))
    hits = await retriever.search("query", limit=3)

    # 余弦分数理论上必定是完全相等的
    assert hits[0].score == hits[1].score == hits[2].score

    # 但结果绝不允许任何随机漂移，必须严格按 chunk_id 的字典序升序！
    assert hits[0].chunk_id == "chunk_a"
    assert hits[1].chunk_id == "chunk_x"
    assert hits[2].chunk_id == "chunk_z"


# ---------------------------------------------------------
# Mock 隔离测试区 (验证 Error Boundary 原样穿透与底线转换)
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_error_boundary_passes_embedding_errors_raw():
    """确保 Embedding 层炸毁时，原样向上抛出，保留正确的业务领域故障属性"""
    adapter = MagicMock(spec=BgeEmbeddingAdapter)
    adapter.embed_query.side_effect = KnowledgeEmbeddingError("来自嵌入模型的错误")

    retriever = DenseRetriever(adapter)
    with pytest.raises(KnowledgeEmbeddingError, match="来自嵌入模型的错误"):
        await retriever.search("query", limit=5)


@pytest.mark.asyncio
async def test_error_boundary_translates_database_crashes():
    """确保数据库炸毁时，彻底拦截并转译为业务侧的 KnowledgeRetrievalError"""
    adapter = MagicMock(spec=BgeEmbeddingAdapter)
    adapter.embed_query.return_value = [0.1] * 512
    retriever = DenseRetriever(adapter)

    # 我们拦截最高层的 SQLAlchemy execute 语句让它抛一个底层内部异常
    with patch("guanchen_v2.knowledge.retrieval.dense.async_session") as mock_session_maker:

        class FakeSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def execute(self, stmt):
                raise DBAPIError("SELECT", "params", Exception("DB down"))

        mock_session_maker.return_value = FakeSession()

        with pytest.raises(KnowledgeRetrievalError, match="知识向量检索失败") as exc_info:
            await retriever.search("query", limit=5)

        assert isinstance(exc_info.value.__cause__, DBAPIError)
