import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from guanchen_v2.knowledge.ingestion.errors import KnowledgeChunkingError
from guanchen_v2.knowledge.models import KnowledgeChunk, KnowledgeDocument


class KnowledgeDocumentChunker:
    """
    确定性的知识切分工厂。
    负责将 KnowledgeDocument 转换为具备检索粒度的 KnowledgeChunk 数组。
    保障：
    1. 绝不跨 Document 边界。
    2. Metadata 血缘全量继承。
    3. 特供《滴天髓阐微》的 Commentary-Anchor 规则，防止经文与释义断裂。
    """

    def __init__(self, max_chars: int = 800, chunk_overlap: int = 80):
        if max_chars <= 0:
            raise ValueError("max_chars 必须大于 0")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap 不能为负数")
        if chunk_overlap >= max_chars:
            raise ValueError("chunk_overlap 必须严格小于 max_chars")

        self._max_chars = max_chars
        self._chunk_overlap = chunk_overlap

        # 严格遵守：段落 > 换行 > 整句 > 弱标点 > 硬切
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_chars,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=[
                "\n\n",
                "\n",
                "。",
                "；",
                "！",
                "？",
                "，",
                "、",
                "",
            ],
            keep_separator=True,
        )

        # 用于定位《滴天髓阐微》中经文锚点组的作用域
        self._ditiansui_anchor_pattern = re.compile(r"(【经文】.*?)(?=\n【|$)", flags=re.DOTALL)

    def _create_chunk_from_text(
        self, document: KnowledgeDocument, chunk_text: str
    ) -> KnowledgeChunk:
        return KnowledgeChunk.from_document_part(
            document_id=document.document_id,
            domain=document.domain,
            source_title=document.source_title,
            source_type=document.source_type,
            section=document.section,
            text=chunk_text,
        )

    def _chunk_ditiansui_document(self, document: KnowledgeDocument) -> list[KnowledgeChunk]:
        """
        处理《滴天髓阐微》专属的【经文】挂靠规则。
        确保每一个拆分出的注疏块都带有经文作为 Context Overhead。
        """
        text = document.text
        matches = list(self._ditiansui_anchor_pattern.finditer(text))

        if not matches:
            if len(text) <= self._max_chars:
                return [self._create_chunk_from_text(document=document, chunk_text=text)]
            splits = self._splitter.split_text(text=text)
            return [
                self._create_chunk_from_text(document, split) for split in splits if split.strip()
            ]

        chunks = []
        for i, match in enumerate(matches):
            anchor_text = match.group(1).strip()

            # 定位当前经文影响的作用域：直到下一个经文锚点，或文档末尾
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            commentary_text = text[start_pos:end_pos].strip()

            if not commentary_text:
                # 只有经文没有释义。绝不能成为孤立块。
                raise KnowledgeChunkingError("《滴天髓阐微》经文锚点缺失关联释义")

            # 将该经文块下的所有原注/任氏曰全部按正常逻辑尝试切分
            if len(commentary_text) + len(anchor_text) <= self._max_chars:
                combined = f"{anchor_text}\n\n{commentary_text}"
                chunks.append(self._create_chunk_from_text(document=document, chunk_text=combined))
            else:
                # 注解太长，执行 Fallback Split，并将经文挂载到所有碎片的最前排
                splits = self._splitter.split_text(text=commentary_text)
                for split in splits:
                    if not split.strip():
                        continue
                    combined = f"{anchor_text}\n\n{split.strip()}"
                    chunks.append(self._create_chunk_from_text(document, combined))

        return chunks

    def chunk_document(self, document: KnowledgeDocument) -> list[KnowledgeChunk]:
        if not document.text.strip():
            return []

        # ====================================================
        # 特供规则：《滴天髓阐微》Anchor Pre-split
        # ====================================================
        if document.source_title == "《滴天髓阐微》":
            return self._chunk_ditiansui_document(
                document,
            )

        # ====================================================
        # C1: 通用规则：Bypass Splitter (保护人工语义边界)
        # ====================================================
        if len(document.text) <= self._max_chars:
            return [self._create_chunk_from_text(document, document.text)]

        # ====================================================
        # C2: 通用规则：Fallback Split
        # ====================================================
        splits = self._splitter.split_text(document.text)
        return [self._create_chunk_from_text(document, split) for split in splits if split.strip()]

    def chunk_documents(self, documents: list[KnowledgeDocument]) -> list[KnowledgeChunk]:
        all_chunks = []
        for doc in documents:
            all_chunks.extend(self.chunk_document(doc))
        return all_chunks
