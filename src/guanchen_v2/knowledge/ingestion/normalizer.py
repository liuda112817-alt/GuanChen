import unicodedata

from guanchen_v2.knowledge.ingestion.models import LoadedKnowledgeSource, NormalizedKnowledgeSource


class KnowledgeSourceNormalizer:
    """
    负责文本基础清理的组件。
    严格限制边界：仅执行 Unicode NFKC 和换行符收束，绝不破坏段落边界或 Markdown 结构。
    """

    def _normalize_text(self, text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return unicodedata.normalize("NFKC", text)

    def normalize(self, source: LoadedKnowledgeSource) -> NormalizedKnowledgeSource:
        normalized_text = self._normalize_text(source.text)
        normalized_title = self._normalize_text(source.source_title)

        return NormalizedKnowledgeSource(
            source_path=source.source_path,
            domain=source.domain,
            source_title=normalized_title,
            source_type=source.source_type,
            text=normalized_text,
        )
