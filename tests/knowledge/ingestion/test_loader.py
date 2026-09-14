import pytest

from guanchen_v2.knowledge.ingestion.errors import KnowledgeSourceLoadError
from guanchen_v2.knowledge.ingestion.loader import KnowledgeSourceLoader
from guanchen_v2.knowledge.models import KnowledgeDomain, SourceType


@pytest.fixture
def temp_raw_root(tmp_path):
    root = tmp_path / "raw_verified"
    root.mkdir()
    return root


def test_loader_happy_path(temp_raw_root):
    """Test 1: 完美合规路径验证，且证明 Loader 绝未对文本做任何偷偷篡改！"""
    bazi_dir = temp_raw_root / "bazi"
    bazi_dir.mkdir()
    sample = bazi_dir / "sample.md"

    # 强化！提供带有各类空白符的原始内容
    original_text = "# 《测试经典》\n\n## 第一章\n正文  \t \n\n"
    sample.write_text(original_text, encoding="utf-8")

    loader = KnowledgeSourceLoader(temp_raw_root)
    sources = loader.load_all()

    assert len(sources) == 1
    src = sources[0]

    assert src.domain == KnowledgeDomain.BAZI
    assert src.source_title == "《测试经典》"
    assert src.source_type == SourceType.PUBLIC_DOMAIN_CLASSIC
    assert src.source_path == "bazi/sample.md"
    # Loader Does Not Transform 防线
    assert src.text == original_text


def test_project_note_resolution(temp_raw_root):
    bazi_dir = temp_raw_root / "bazi"
    bazi_dir.mkdir()
    sample = bazi_dir / "guanchen_bazi_terms.md"
    sample.write_text("# 术语", encoding="utf-8")
    loader = KnowledgeSourceLoader(temp_raw_root)
    src = loader.load_all()[0]
    assert src.source_type == SourceType.PROJECT_NOTE


def test_source_path_cross_platform_contract(temp_raw_root):
    bazi_dir = temp_raw_root / "bazi"
    bazi_dir.mkdir()
    sample = bazi_dir / "test.md"
    sample.write_text("# 标题", encoding="utf-8")
    loader = KnowledgeSourceLoader(temp_raw_root)
    src = loader.load_file(sample)
    assert "\\" not in src.source_path
    assert "/" in src.source_path


def test_missing_h1_fails(temp_raw_root):
    bazi_dir = temp_raw_root / "bazi"
    bazi_dir.mkdir()
    sample = bazi_dir / "bad.md"
    sample.write_text("## 二级标题\n什么也没有", encoding="utf-8")
    loader = KnowledgeSourceLoader(temp_raw_root)
    with pytest.raises(KnowledgeSourceLoadError, match="首个有效内容必须是"):
        loader.load_file(sample)


def test_empty_h1_fails(temp_raw_root):
    bazi_dir = temp_raw_root / "bazi"
    bazi_dir.mkdir()
    sample = bazi_dir / "bad2.md"
    sample.write_text("#   \n\n正文", encoding="utf-8")
    loader = KnowledgeSourceLoader(temp_raw_root)
    with pytest.raises(KnowledgeSourceLoadError, match="首个有效内容必须是"):
        loader.load_file(sample)


def test_multiple_h1_fails(temp_raw_root):
    bazi_dir = temp_raw_root / "bazi"
    bazi_dir.mkdir()
    sample = bazi_dir / "bad3.md"
    sample.write_text("# 《第一本书》\n\n# 《第二本书》", encoding="utf-8")
    loader = KnowledgeSourceLoader(temp_raw_root)
    with pytest.raises(KnowledgeSourceLoadError, match="存在多个一级标题"):
        loader.load_file(sample)


def test_invalid_utf8_translation(temp_raw_root):
    bazi_dir = temp_raw_root / "bazi"
    bazi_dir.mkdir()
    sample = bazi_dir / "gbk.md"
    sample.write_bytes("这是一个古籍测试".encode("gbk"))
    loader = KnowledgeSourceLoader(temp_raw_root)
    with pytest.raises(KnowledgeSourceLoadError, match="文件读取失败") as exc_info:
        loader.load_file(sample)
    assert isinstance(exc_info.value.__cause__, UnicodeDecodeError)


def test_only_md_files_discovered(temp_raw_root):
    bazi_dir = temp_raw_root / "bazi"
    bazi_dir.mkdir()
    (bazi_dir / "a.md").write_text("# A", encoding="utf-8")
    (bazi_dir / "b.txt").write_text("# B", encoding="utf-8")
    (bazi_dir / "c.pdf").write_text("PDF", encoding="utf-8")
    loader = KnowledgeSourceLoader(temp_raw_root)
    sources = loader.load_all()
    assert len(sources) == 1
    assert sources[0].source_path == "bazi/a.md"


def test_unknown_domain_directory_fails(temp_raw_root):
    unknown_dir = temp_raw_root / "unknown_domain"
    unknown_dir.mkdir()
    loader = KnowledgeSourceLoader(temp_raw_root)
    with pytest.raises(KnowledgeSourceLoadError, match="发现未知领域目录"):
        loader.load_all()


def test_path_outside_root_fails(temp_raw_root, tmp_path):
    """Test 新增: Blocker 1 极度致命！防止解析外部恶意或未授权文件"""
    loader = KnowledgeSourceLoader(temp_raw_root)

    evil_dir = tmp_path / "evil_bazi"
    evil_dir.mkdir()
    evil_file = evil_dir / "evil.md"
    evil_file.write_text("# 《黑客书》", encoding="utf-8")

    with pytest.raises(KnowledgeSourceLoadError, match="位于允许的语料目录之外") as exc_info:
        loader.load_file(evil_file)

    assert isinstance(exc_info.value.__cause__, ValueError)


def test_content_before_h1_fails(temp_raw_root):
    """Test 新增: H1 置顶约束，不能容忍废话或垃圾格式前置"""
    bazi_dir = temp_raw_root / "bazi"
    bazi_dir.mkdir()

    sample = bazi_dir / "bad_structure.md"
    sample.write_text("这里是一段介绍或者废话\n\n# 《测试经典》", encoding="utf-8")

    loader = KnowledgeSourceLoader(temp_raw_root)
    with pytest.raises(KnowledgeSourceLoadError, match="首个有效内容必须是"):
        loader.load_file(sample)
