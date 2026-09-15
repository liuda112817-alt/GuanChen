from pathlib import Path

from guanchen_v2.knowledge.ingestion.errors import KnowledgeSourceLoadError
from guanchen_v2.knowledge.ingestion.models import LoadedKnowledgeSource
from guanchen_v2.knowledge.models import KnowledgeDomain, SourceType


class KnowledgeSourceLoader:
    def __init__(self, raw_verified_root: Path) -> None:
        self._root = raw_verified_root

        if not self._root.exists() or not self._root.is_dir():
            raise KnowledgeSourceLoadError(f"根目录不存在或不是文件夹: {self._root}")

    def _resolve_domain(self, path: Path) -> KnowledgeDomain:
        # 约定：其父目录的名称即为 Domain
        domain_str = path.parent.name
        try:
            return KnowledgeDomain(domain_str)
        except ValueError as exc:
            raise KnowledgeSourceLoadError("知识源文件所属领域无效。") from exc

    def _resolve_source_type(self, path: Path) -> SourceType:
        # 规则：属于官方整理笔记的文件以此开头
        if path.name.startswith("guanchen_") and path.name.endswith("_terms.md"):
            return SourceType.PROJECT_NOTE
        return SourceType.PUBLIC_DOMAIN_CLASSIC

    def _extract_source_title(self, text: str, source_path: str) -> str:
        h1_title = None
        has_seen_content = False

        for line in text.splitlines():
            stripped = line.strip()

            if not stripped:
                continue

            if not has_seen_content:
                has_seen_content = True
                if not stripped.startswith("# "):
                    raise KnowledgeSourceLoadError(f"文件 {source_path} 的首个有效内容必须是一级标题 (H1)。")
                h1_title = stripped[2:].strip()
            else:
                if stripped.startswith("# "):
                    raise KnowledgeSourceLoadError(
                        f"文件 {source_path} 中存在多个一级标题 (H1)。\n"
                        "知识库限制单一文件仅对应单一核心古籍。"
                    )

        if not h1_title:
            raise KnowledgeSourceLoadError(f"文件 {source_path} 缺失一级标题 (H1) 或标题内容为空。")

        return h1_title

    def load_file(self, path: Path) -> LoadedKnowledgeSource:
        """加载单一文件，提取元数据并执行严格的 H1 契约验证。"""
        resolved_path = path.resolve()

        try:
            relative_path = resolved_path.relative_to(self._root)
        except ValueError as exc:
            raise KnowledgeSourceLoadError("知识源文件位于允许的语料目录之外。") from exc

        if not resolved_path.is_file() or resolved_path.suffix != ".md":
            raise KnowledgeSourceLoadError(f"目标不是合法的 markdown 文件: {path}")

        try:
            text = resolved_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise KnowledgeSourceLoadError("知识源文件读取失败。") from exc

        source_path = relative_path.as_posix()
        domain = self._resolve_domain(path=resolved_path)
        source_type = self._resolve_source_type(path=resolved_path)
        source_title = self._extract_source_title(text=text, source_path=source_path)

        return LoadedKnowledgeSource(
            source_path=source_path,
            domain=domain,
            source_title=source_title,
            source_type=source_type,
            text=text,
        )

    def load_all(self) -> list[LoadedKnowledgeSource]:
        """扫描所有领域子目录，严格按规加载所有的 MD 知识源。"""
        sources = []
        valid_domains = {d.value for d in KnowledgeDomain}

        try:
            for child in sorted(self._root.iterdir()):
                if not child.is_dir():
                    continue

                if child.name not in valid_domains:
                    raise KnowledgeSourceLoadError(
                        f"发现未知领域目录 '{child.name}'，\n如果这是拼写错误请修正，否则请移除该非法目录。"
                    )

                # 获取该领域目录下的一层 MD 文件
                md_files = sorted(child.glob("*.md"))
                for md_file in md_files:
                    sources.append(self.load_file(md_file))
        except OSError as exc:
            raise KnowledgeSourceLoadError("知识源目录扫描失败。") from exc

        if not sources:
            raise KnowledgeSourceLoadError("未发现任何合法的 Markdown 知识源。")

        return sources
