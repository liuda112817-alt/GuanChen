import pytest
from pydantic import ValidationError

from guanchen_v2.knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDomain,
    SourceType,
    generate_deterministic_chunk_id,
)


def test_document_rejects_empty_text_or_whitespace():
    """测试文本规范：阻断纯空格或被剔除后为空的垃圾文本"""
    with pytest.raises(ValidationError, match="不能为空"):
        KnowledgeDocument(
            document_id="doc_1",
            domain=KnowledgeDomain.BAZI,
            source_title="书籍",
            source_type=SourceType.PUBLIC_DOMAIN_CLASSIC,
            section="章一",
            text="   \n   \t  ",
        )


def test_deterministic_chunk_id_consistency():
    """核心：相同来源、章节和内容，必须产生完全一致的 ID。"""
    id1 = generate_deterministic_chunk_id("doc1", "sec1", "这是一段相同的文本")
    id2 = generate_deterministic_chunk_id("doc1", "sec1", "这是一段相同的文本")
    assert id1 == id2


def test_deterministic_chunk_id_change_awareness():
    """核心：内容发生变动（哪怕只是一个字）或源头改变，指纹必定改变"""
    base_id = generate_deterministic_chunk_id("doc1", "sec1", "一段文本")
    assert base_id != generate_deterministic_chunk_id("doc1", "sec1", "一段文本，加了个字")
    assert base_id != generate_deterministic_chunk_id("doc1", "sec2", "一段文本")


def test_knowledge_chunk_from_document_part_happy_path():
    """验证官方构造路径能够无缝组合各类元数据，并正确挂载 Deterministic ID"""
    chunk = KnowledgeChunk.from_document_part(
        document_id="yuanhai_ziping__juan_01",
        domain=KnowledgeDomain.BAZI,
        source_title="《渊海子平》",
        source_type=SourceType.PUBLIC_DOMAIN_CLASSIC,
        section="卷一",
        text="   天干者，甲乙丙丁也。   \n\n  ",
    )

    # 元数据应清洗并透传
    assert chunk.document_id == "yuanhai_ziping__juan_01"
    assert chunk.domain == KnowledgeDomain.BAZI
    # 因为保存时只做基础 strip，不会压缩换行，所以 \n\n 应该被保全
    assert chunk.text == "天干者，甲乙丙丁也。"

    # ID 仍由底层的 canonicalize 计算得出，不受外层空格影响
    expected_id = generate_deterministic_chunk_id(
        "yuanhai_ziping__juan_01", "卷一", "天干者，甲乙丙丁也。   \n\n  "
    )
    assert chunk.chunk_id == expected_id


def test_chunk_id_whitespace_semantics():
    """验证 Chunk ID canonicalization 语义：纯空白符变化哈希不变，但有意义的分割保留"""
    # 这三者都被化简成 "甲 乙"，因此 ID 完全相同
    id1 = generate_deterministic_chunk_id("doc1", "sec1", "甲   乙")
    id2 = generate_deterministic_chunk_id("doc1", "sec1", "甲\t乙")
    id3 = generate_deterministic_chunk_id("doc1", "sec1", "甲\n乙")
    assert id1 == id2 == id3

    # 原生单空格自然也等于化简后的单空格
    id4 = generate_deterministic_chunk_id("doc1", "sec1", "甲 乙")
    assert id1 == id4

    # 但完全粘连的词汇是另一种语义，ID 必须不同！
    id5 = generate_deterministic_chunk_id("doc1", "sec1", "甲乙")
    assert id1 != id5


def test_knowledge_domain_includes_dream():
    assert KnowledgeDomain.DREAM.value == "dream"
    assert KnowledgeDomain("dream") is KnowledgeDomain.DREAM
