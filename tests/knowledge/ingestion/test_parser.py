import pytest

from guanchen_v2.knowledge.ingestion.errors import KnowledgeStructureParseError
from guanchen_v2.knowledge.ingestion.models import NormalizedKnowledgeSource
from guanchen_v2.knowledge.ingestion.parser import MarkdownKnowledgeParser
from guanchen_v2.knowledge.models import KnowledgeDomain, SourceType


@pytest.fixture
def markdown_parser():
    return MarkdownKnowledgeParser()


def _create_source(text: str, source_title: str) -> NormalizedKnowledgeSource:
    return NormalizedKnowledgeSource(
        source_path="test.md",
        domain=KnowledgeDomain.BAZI,
        source_title=source_title,
        source_type=SourceType.PUBLIC_DOMAIN_CLASSIC,
        text=text,
    )


def test_h2_only_structure(markdown_parser):
    """P1: 纯 H2 结构完美剥离"""
    text = "# 《测试》\n\n## 第一卦\n乾正文\n\n## 第二卦\n坤正文"
    docs = markdown_parser.parse(_create_source(text, "《测试》"))
    assert len(docs) == 2
    assert docs[0].section == "第一卦"
    assert docs[0].text == "乾正文"
    assert docs[1].section == "第二卦"
    assert docs[1].text == "坤正文"


def test_nested_h2_h3(markdown_parser):
    """P2: 嵌套层级生成正确的 section path，不生成空父级"""
    text = "# 《书》\n\n## 卷一\n\n### 第一章\nA\n\n### 第二章\nB"
    docs = markdown_parser.parse(_create_source(text, "《书》"))
    assert len(docs) == 2
    assert docs[0].section == "卷一 / 第一章"
    assert docs[0].text == "A"
    assert docs[1].section == "卷一 / 第二章"
    assert docs[1].text == "B"


def test_parent_has_own_content(markdown_parser):
    """P3: 父层级有自己的正文时，绝不能丢失它"""
    text = "# 《书》\n\n## 卷一\n\n卷一说明。\n\n### 第一章\n正文。"
    docs = markdown_parser.parse(_create_source(text, "《书》"))
    assert len(docs) == 2
    assert docs[0].section == "卷一"
    assert docs[0].text == "卷一说明。"
    assert docs[1].section == "卷一 / 第一章"
    assert docs[1].text == "正文。"


def test_root_body(markdown_parser):
    """P4: H1 根节点直属正文。必须被保留并挂载到书名下"""
    text = "# 《书》\n\n总说明。\n\n## 第一章\n正文。"
    docs = markdown_parser.parse(_create_source(text, "《书》"))
    assert len(docs) == 2
    assert docs[0].section == "《书》"
    assert docs[0].text == "总说明。"
    assert docs[1].section == "第一章"
    assert docs[1].text == "正文。"


def test_no_cross_section_contamination(markdown_parser):
    """P5: 跨区无污染，下一章不会沾染上一章"""
    text = "# 《书》\n\n## A\n文本A\n## B\n文本B"
    docs = markdown_parser.parse(_create_source(text, "《书》"))
    assert docs[0].text == "文本A"
    assert docs[1].text == "文本B"


def test_heading_jump_fails(markdown_parser):
    """P6: 破坏物理逻辑的结构跳级"""
    text = "# Book\n\n## A\n\n#### B\n内容"
    with pytest.raises(KnowledgeStructureParseError, match="结构跳级"):
        markdown_parser.parse(_create_source(text, "Book"))


def test_duplicate_path_fails(markdown_parser):
    """P7: 重复路径被拦截防撞"""
    text = "# Book\n\n## 卷一\n\n### 第一章\nA\n\n### 第一章\nB"
    with pytest.raises(KnowledgeStructureParseError, match="重复的 section 路径"):
        markdown_parser.parse(_create_source(text, "Book"))


def test_fenced_heading_ignored(markdown_parser):
    """P8: Fenced 代码块内即使存在标题符号也被无情无视"""
    text = "# Book\n\n## 代码\n```\n# 不是标题\n## 也不算\n```\n结束"
    docs = markdown_parser.parse(_create_source(text, "Book"))
    assert len(docs) == 1
    assert docs[0].section == "代码"
    assert "## 也不算" in docs[0].text


def test_tilde_fenced_heading_ignored(markdown_parser):
    """新增: ~~~ 代码块包裹防御"""
    text = "# Book\n\n## 代码\n~~~\n# 不是标题\n## 也不算\n~~~\n结束"
    docs = markdown_parser.parse(_create_source(text, "Book"))
    assert len(docs) == 1
    assert docs[0].section == "代码"
    assert "## 也不算" in docs[0].text


def test_parser_paragraph_preservation(markdown_parser):
    """新增: Parser 后的 Document 必须完美保留正文段落（空行）边界"""
    text = "# 《测试》\n\n## 第一章\n\n第一段。\n\n第二段。"
    docs = markdown_parser.parse(_create_source(text, "《测试》"))
    assert docs[0].text == "第一段。\n\n第二段。"
