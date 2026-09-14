from guanchen_v2.knowledge.ingestion.models import LoadedKnowledgeSource
from guanchen_v2.knowledge.ingestion.normalizer import KnowledgeSourceNormalizer
from guanchen_v2.knowledge.models import KnowledgeDomain, SourceType


def test_nfkc_normalization():
    """N1: 测试 NFKC 转换"""
    source = LoadedKnowledgeSource(
        source_path="test.md",
        domain=KnowledgeDomain.BAZI,
        source_title="《測試》",
        source_type=SourceType.PUBLIC_DOMAIN_CLASSIC,
        text="正文：ＡＢＣ１２３\n",
    )
    normalizer = KnowledgeSourceNormalizer()
    res = normalizer.normalize(source)
    assert "ABC123" in res.text
    assert "《測試》" in res.source_title


def test_paragraph_preservation():
    """N2: 绝不破坏段落边界"""
    text = "第一段。\n\n第二段。"
    source = LoadedKnowledgeSource(
        source_path="test.md",
        domain=KnowledgeDomain.BAZI,
        source_title="《测试》",
        source_type=SourceType.PUBLIC_DOMAIN_CLASSIC,
        text=text,
    )
    normalizer = KnowledgeSourceNormalizer()
    res = normalizer.normalize(source)
    assert res.text == text


def test_metadata_preservation():
    """N3: 保持元数据不变，仅 normalize title 和 text"""
    source = LoadedKnowledgeSource(
        source_path="a/b.md",
        domain=KnowledgeDomain.YIJING,
        source_title="《测试》",
        source_type=SourceType.PROJECT_NOTE,
        text="内容",
    )
    normalizer = KnowledgeSourceNormalizer()
    res = normalizer.normalize(source)
    assert res.source_path == "a/b.md"
    assert res.domain == KnowledgeDomain.YIJING
    assert res.source_type == SourceType.PROJECT_NOTE
