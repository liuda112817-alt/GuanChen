import math
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from guanchen_v2.knowledge.embeddings import BgeEmbeddingAdapter
from guanchen_v2.knowledge.errors import KnowledgeEmbeddingError
from guanchen_v2.knowledge.models import KnowledgeChunk, KnowledgeDomain, SourceType


def _create_dummy_chunk(chunk_id: str, title: str, section: str, text: str) -> KnowledgeChunk:
    # 使用 model_construct 绕过文本清洗以便专心测试 Adapter 容错
    return KnowledgeChunk.model_construct(
        chunk_id=chunk_id,
        document_id="doc1",
        domain=KnowledgeDomain.BAZI,
        source_title=title,
        source_type=SourceType.PUBLIC_DOMAIN_CLASSIC,
        section=section,
        text=text,
    )


# ---------------------------------------------------------
# Mock 隔离测试区
# ---------------------------------------------------------


@patch("guanchen_v2.knowledge.embeddings.SentenceTransformer")
def test_model_initialization_failure(mock_st_class):
    """验证模型加载失败时抛出正确的项目异常，并保留底层根因"""
    mock_st_class.side_effect = RuntimeError("Disk full")
    with pytest.raises(KnowledgeEmbeddingError, match="Embedding 模型加载失败") as exc_info:
        BgeEmbeddingAdapter()
    assert isinstance(exc_info.value.__cause__, RuntimeError)


@patch("guanchen_v2.knowledge.embeddings.SentenceTransformer")
def test_embed_documents_input_and_order_contract(mock_st_class):
    """核心防线：确保输入不乱序，且输出能够严格按位置对齐 mapping"""
    mock_model = MagicMock()
    mock_st_class.return_value = mock_model

    # 构造极具辨识度的数据以验证是否乱序：
    # Row 0 开头为 1.0, Row 1 开头为 2.0
    row_1 = np.full((512,), 1.0, dtype=np.float32)
    row_2 = np.full((512,), 2.0, dtype=np.float32)
    mock_model.encode.return_value = np.array([row_1, row_2])

    adapter = BgeEmbeddingAdapter()
    chunks = [
        _create_dummy_chunk("c1", "《书1》", "第一章", "正文1"),
        _create_dummy_chunk("c2", "《书2》", "第二章", "正文2"),
    ]
    vectors = adapter.embed_documents(chunks)

    # 验证传入模型的参数
    call_args, _ = mock_model.encode.call_args
    texts_passed = call_args[0]
    assert texts_passed[0] == "《书1》\n第一章\n正文1"
    assert texts_passed[1] == "《书2》\n第二章\n正文2"

    # 验证输出的位置映射是否完美
    assert len(vectors) == 2
    assert vectors[0][0] == 1.0
    assert vectors[1][0] == 2.0


@patch("guanchen_v2.knowledge.embeddings.SentenceTransformer")
def test_embed_documents_fails_on_shape_mismatch(mock_st_class):
    """防御三方库诡异返回：比如只返回了一行，或者维度变成 768"""
    mock_model = MagicMock()
    mock_st_class.return_value = mock_model
    adapter = BgeEmbeddingAdapter()
    chunks = [
        _create_dummy_chunk("c1", "书", "章", "正文"),
        _create_dummy_chunk("c2", "书", "章", "正文"),
    ]

    # 场景1：数量不对 (2个文本只返回1行)
    mock_model.encode.return_value = np.random.rand(1, 512)
    with pytest.raises(KnowledgeEmbeddingError, match="形状异常，预期为 \\(2, 512\\)"):
        adapter.embed_documents(chunks)

    # 场景2：维度不对
    mock_model.encode.return_value = np.random.rand(2, 768)
    with pytest.raises(KnowledgeEmbeddingError, match="形状异常，预期为 \\(2, 512\\)"):
        adapter.embed_documents(chunks)


@patch("guanchen_v2.knowledge.embeddings.SentenceTransformer")
def test_embed_documents_fails_on_empty_chunk_text(mock_st_class):
    adapter = BgeEmbeddingAdapter()
    chunks = [_create_dummy_chunk("c1", "《书》", "章", "   ")]
    with pytest.raises(KnowledgeEmbeddingError, match="尝试对空文本进行 Embedding"):
        adapter.embed_documents(chunks)


@patch("guanchen_v2.knowledge.embeddings.SentenceTransformer")
def test_embed_query_happy_path(mock_st_class):
    mock_model = MagicMock()
    mock_st_class.return_value = mock_model
    mock_model.encode.return_value = np.random.rand(512).astype(np.float32)

    adapter = BgeEmbeddingAdapter()
    vector = adapter.embed_query("八字怎么看？")
    assert isinstance(vector, list)
    assert len(vector) == 512


@patch("guanchen_v2.knowledge.embeddings.SentenceTransformer")
def test_embed_query_fails_on_empty_or_shape_mismatch(mock_st_class):
    mock_model = MagicMock()
    mock_st_class.return_value = mock_model
    adapter = BgeEmbeddingAdapter()

    # 场景1：空 Query
    with pytest.raises(KnowledgeEmbeddingError, match="不能为空"):
        adapter.embed_query("   ")

    # 场景2：返回二维数组 (例如被错误地包裹了一层)
    mock_model.encode.return_value = np.random.rand(1, 512)
    with pytest.raises(KnowledgeEmbeddingError, match="输出了错误的形状.*预期应为 \\(512,\\)"):
        adapter.embed_query("正当查询")


# ---------------------------------------------------------
# 真实模型 Smoke Test
# ---------------------------------------------------------


@pytest.mark.smoke
def test_real_bge_model_smoke():
    """
    真实的模型推理测试。只在明确指定 uv run pytest -m smoke 时运行。
    任何网络/模型加载问题在此处都应该 FAIL，而不是静默 skip。
    """
    from guanchen_v2.knowledge.embeddings import BgeEmbeddingAdapter

    adapter = BgeEmbeddingAdapter()

    chunks = [
        _create_dummy_chunk("1", "书", "章", "真实大模型推理测试 A"),
        _create_dummy_chunk("2", "书", "章", "真实大模型推理测试 B"),
    ]
    vectors = adapter.embed_documents(chunks)
    assert len(vectors) == 2
    assert len(vectors[0]) == 512

    norm = math.sqrt(sum(x * x for x in vectors[0]))
    assert math.isclose(norm, 1.0, rel_tol=1e-5)

    query_vector = adapter.embed_query("测试 Query")
    assert len(query_vector) == 512
    q_norm = math.sqrt(sum(x * x for x in query_vector))
    assert math.isclose(q_norm, 1.0, rel_tol=1e-5)
