import pytest

from guanchen_v2.knowledge.ingestion.chunker import KnowledgeDocumentChunker
from guanchen_v2.knowledge.ingestion.errors import KnowledgeChunkingError
from guanchen_v2.knowledge.models import KnowledgeDocument, KnowledgeDomain, SourceType


def _create_doc(title: str, text: str) -> KnowledgeDocument:
    return KnowledgeDocument.from_parser(
        domain=KnowledgeDomain.BAZI,
        source_title=title,
        source_type=SourceType.PUBLIC_DOMAIN_CLASSIC,
        section="测试章节",
        text=text,
    )


def test_short_document_remains_one_chunk():
    """C1: 长度未越界的段落，必须 Bypass 保持绝对完整"""
    doc = _create_doc("《书》", "100个字符的正文。")
    chunker = KnowledgeDocumentChunker(max_chars=800, chunk_overlap=80)
    chunks = chunker.chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].text == "100个字符的正文。"
    # Metadata 全继承
    assert chunks[0].document_id == doc.document_id
    assert chunks[0].source_title == doc.source_title


def test_long_document_splits_with_metadata_inheritance():
    """C2: 长文档切分，且 Metadata 血缘完整继承"""
    text = "A" * 900
    doc = _create_doc("《书》", text)
    chunker = KnowledgeDocumentChunker(max_chars=800, chunk_overlap=80)
    chunks = chunker.chunk_document(doc)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.document_id == doc.document_id
        assert chunk.domain == doc.domain
        assert chunk.section == doc.section


def test_no_cross_document_contamination():
    """C3: 不同 Document 的切片绝不产生交叉感染"""
    doc_a = _create_doc("《书》", "A" * 900)
    doc_b = _create_doc("《测试》", "B" * 900)
    chunker = KnowledgeDocumentChunker(max_chars=800, chunk_overlap=80)

    chunks = chunker.chunk_documents([doc_a, doc_b])
    a_chunks = [c for c in chunks if c.source_title == "《书》"]
    b_chunks = [c for c in chunks if c.source_title == "《测试》"]

    for c in a_chunks:
        assert "A" in c.text and "B" not in c.text
    for c in b_chunks:
        assert "B" in c.text and "A" not in c.text


def test_paragraph_aware_preference():
    """C4: 切片偏好验证，必须优先在段落处（双换行）下刀"""
    # 构造两个段落，单段均不到 100，总长超过 100
    text = "第一大段。" + ("A" * 60) + "\n\n第二大段。" + ("B" * 60)
    doc = _create_doc("《书》", text)
    chunker = KnowledgeDocumentChunker(max_chars=100, chunk_overlap=10)
    chunks = chunker.chunk_document(doc)

    # 因为在 \n\n 处切了，所以第一个块里绝对不该混入第二大段的内容
    assert "第二大段" not in chunks[0].text
    assert chunks[0].text.startswith("第一大段")


def test_deterministic_chunk_ids():
    """C5: 多次重试，生成的 ID 序列必须是恒定的指纹"""
    doc = _create_doc("《书》", "A" * 900)
    chunker = KnowledgeDocumentChunker(max_chars=800, chunk_overlap=80)

    chunks_1 = chunker.chunk_document(doc)
    chunks_2 = chunker.chunk_document(doc)

    ids_1 = [c.chunk_id for c in chunks_1]
    ids_2 = [c.chunk_id for c in chunks_2]
    assert ids_1 == ids_2


def test_whitespace_preservation_in_chunk_text():
    """C6: Chunk 储存的内容绝不被 Canonicalization 破坏段落和多余空格"""
    text = "第一段。   \n\n  第二段。"
    doc = _create_doc("《书》", text)
    chunker = KnowledgeDocumentChunker(max_chars=800, chunk_overlap=80)
    chunk = chunker.chunk_document(doc)[0]

    assert "\n\n" in chunk.text
    assert "第一段。   \n\n  第二段。" == chunk.text


def test_ditiansui_multi_anchor_grouping():
    """C7: 滴天髓多锚点截断组装。不允许混杂！"""
    text = "【经文】A\n【原注】A解\n【经文】B\n【任氏曰】B解"
    doc = _create_doc("《滴天髓阐微》", text)
    chunker = KnowledgeDocumentChunker(max_chars=800, chunk_overlap=80)
    chunks = chunker.chunk_document(doc)

    # 长度充裕，应当划分为两块，每块守着自己的锚
    assert len(chunks) == 2
    assert "【经文】A" in chunks[0].text and "【经文】B" not in chunks[0].text
    assert "【经文】B" in chunks[1].text and "【经文】A" not in chunks[1].text


def test_ditiansui_anchor_retained_after_fallback():
    """C8: 极其核心 - 当注解超长时，切断的残肢必须自带经文头部 context"""
    text = "【经文】何知其人富\n【任氏曰】" + ("释义" * 50)
    doc = _create_doc("《滴天髓阐微》", text)
    # 强行切断
    chunker = KnowledgeDocumentChunker(max_chars=50, chunk_overlap=5)
    chunks = chunker.chunk_document(doc)

    assert len(chunks) > 1
    # 每一个被迫拆分的碎块，开头都必须带回原经文
    for chunk in chunks:
        assert chunk.text.startswith("【经文】何知其人富")
        assert len(chunk.text) > len("【经文】何知其人富")  # 不会产生 verse-only 孤立块


def test_empty_result_impossible():
    """C9: 输入有内容，绝对不能返回空"""
    doc = _create_doc("《书》", "哪怕只有一个字")
    chunker = KnowledgeDocumentChunker(max_chars=800, chunk_overlap=80)
    assert len(chunker.chunk_document(doc)) > 0


def test_invalid_config():
    """C10: 防止程序员乱填切分参数"""
    with pytest.raises(ValueError, match="必须大于 0"):
        KnowledgeDocumentChunker(max_chars=-1)
    with pytest.raises(ValueError, match="不能为负数"):
        KnowledgeDocumentChunker(chunk_overlap=-1)
    with pytest.raises(ValueError, match="严格小于"):
        KnowledgeDocumentChunker(max_chars=100, chunk_overlap=100)


def test_ditiansui_anchor_without_commentary_fails():
    """C11: 发现孤立经文锚点时 Fail Fast，决不静默产生 verse-only chunk"""
    # 只有经文锚点，没有任何后续说明正文
    text = "【经文】此句之后没有任何注解"
    doc = _create_doc("《滴天髓阐微》", text)
    chunker = KnowledgeDocumentChunker(max_chars=800, chunk_overlap=80)

    with pytest.raises(KnowledgeChunkingError, match="缺失关联释义"):
        chunker.chunk_document(doc)
