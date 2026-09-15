import re

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
)

from guanchen_v2.knowledge.ingestion.errors import (
    KnowledgeChunkingError,
)
from guanchen_v2.knowledge.models import (
    KnowledgeChunk,
    KnowledgeDocument,
)


class KnowledgeDocumentChunker:
    """
    确定性的知识切分工厂。

    负责将 KnowledgeDocument 转换为具备检索粒度的
    KnowledgeChunk 数组。

    保障：
    1. 绝不跨 Document 边界。
    2. Metadata 血缘全量继承。
    3. 相同 chunk_id 在同一 Document 内稳定去重。
    4. 特供《滴天髓阐微》的 Commentary-Anchor 规则，
       防止经文与释义断裂。
    """

    def __init__(
        self,
        max_chars: int = 800,
        chunk_overlap: int = 80,
    ) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars 必须大于 0")

        if chunk_overlap < 0:
            raise ValueError("chunk_overlap 不能为负数")

        if chunk_overlap >= max_chars:
            raise ValueError("chunk_overlap 必须严格小于 max_chars")

        self._max_chars = max_chars
        self._chunk_overlap = chunk_overlap

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

        self._ditiansui_anchor_pattern = re.compile(
            r"(【经文】.*?)(?=\n【|$)",
            flags=re.DOTALL,
        )

    def _create_chunk_from_text(
        self,
        document: KnowledgeDocument,
        chunk_text: str,
    ) -> KnowledgeChunk:
        return KnowledgeChunk.from_document_part(
            document_id=document.document_id,
            domain=document.domain,
            source_title=document.source_title,
            source_type=document.source_type,
            section=document.section,
            text=chunk_text,
        )

    @staticmethod
    def _dedupe_chunks(
        chunks: list[KnowledgeChunk],
    ) -> list[KnowledgeChunk]:
        """
        按 chunk_id 稳定去重。

        chunk_id 是基于：
        document_id + section + canonicalized text
        生成的确定性内容指纹。

        同一个 Document 内出现相同 chunk_id 时，
        保留第一次出现的 Chunk，忽略后续重复项。
        """
        unique_chunks: list[KnowledgeChunk] = []

        seen_chunk_ids: set[str] = set()

        for chunk in chunks:
            if chunk.chunk_id in seen_chunk_ids:
                continue

            seen_chunk_ids.add(chunk.chunk_id)

            unique_chunks.append(chunk)

        return unique_chunks

    def _chunk_ditiansui_document(
        self,
        document: KnowledgeDocument,
    ) -> list[KnowledgeChunk]:
        """
        处理《滴天髓阐微》专属的【经文】挂靠规则。

        每一个拆分出的注疏块都必须带有对应经文，
        防止经文与解释在切分后失去关联。
        """
        text = document.text

        matches = list(self._ditiansui_anchor_pattern.finditer(text))

        if not matches:
            if len(text) <= self._max_chars:
                return [
                    self._create_chunk_from_text(
                        document=document,
                        chunk_text=text,
                    )
                ]

            splits = self._splitter.split_text(text=text)

            return [
                self._create_chunk_from_text(
                    document=document,
                    chunk_text=split,
                )
                for split in splits
                if split.strip()
            ]

        chunks: list[KnowledgeChunk] = []

        for index, match in enumerate(matches):
            anchor_text = match.group(1).strip()

            start_pos = match.end()

            if index + 1 < len(matches):
                end_pos = matches[index + 1].start()
            else:
                end_pos = len(text)

            commentary_text = text[start_pos:end_pos].strip()

            if not commentary_text:
                raise KnowledgeChunkingError("《滴天髓阐微》经文锚点缺失关联释义")

            combined_length = len(anchor_text) + len(commentary_text)

            if combined_length <= self._max_chars:
                combined = f"{anchor_text}\n\n{commentary_text}"

                chunks.append(
                    self._create_chunk_from_text(
                        document=document,
                        chunk_text=combined,
                    )
                )

                continue

            splits = self._splitter.split_text(text=commentary_text)

            for split in splits:
                if not split.strip():
                    continue

                combined = f"{anchor_text}\n\n{split.strip()}"

                chunks.append(
                    self._create_chunk_from_text(
                        document=document,
                        chunk_text=combined,
                    )
                )

        return chunks

    def chunk_document(
        self,
        document: KnowledgeDocument,
    ) -> list[KnowledgeChunk]:
        if not document.text.strip():
            return []

        if document.source_title == "《滴天髓阐微》":
            chunks = self._chunk_ditiansui_document(document)

            return self._dedupe_chunks(chunks)

        if len(document.text) <= self._max_chars:
            return [
                self._create_chunk_from_text(
                    document=document,
                    chunk_text=document.text,
                )
            ]

        splits = self._splitter.split_text(document.text)

        chunks = [
            self._create_chunk_from_text(
                document=document,
                chunk_text=split,
            )
            for split in splits
            if split.strip()
        ]

        return self._dedupe_chunks(chunks)

    def chunk_documents(
        self,
        documents: list[KnowledgeDocument],
    ) -> list[KnowledgeChunk]:
        all_chunks: list[KnowledgeChunk] = []

        for document in documents:
            all_chunks.extend(self.chunk_document(document))

        return all_chunks
