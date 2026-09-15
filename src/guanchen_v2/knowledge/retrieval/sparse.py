import unicodedata
from typing import Any, Optional

import bm25s
import jieba
from sqlalchemy import select

from guanchen_v2.knowledge.errors import KnowledgeRetrievalError
from guanchen_v2.knowledge.models import (
    KnowledgeDomain,
    RetrievalFilter,
    SourceType,
    SparseIndexEntry,
    SparseSearchHit,
)
from guanchen_v2.knowledge.persistence.database import async_session
from guanchen_v2.knowledge.persistence.models import KnowledgeChunkRow


class SparseRetriever:
    """
    GuanChen 稀疏检索器 (BM25 Lexical Match)。
    职责：
    1. 依托 PostgreSQL 当前 Chunk 快照构建原子化内存词汇索引。
    2. 使用 Jieba 分词器维持 Document 与 Query 切词规则的绝对一致性。
    3. 严禁分数归一化；严禁返回零分无相关内容。
    4. 采用一致的平局打破机制 (score DESC, chunk_id ASC)。
    """

    def __init__(self):
        self._is_initialized = False
        self._chunk_snapshots: list[SparseIndexEntry] = []
        self._bm25_index: Any = None

    def _tokenize_sparse_text(self, text: str) -> list[str]:
        """
        核心 Tokenizer：
        NFKC 规范化 -> Jieba 精确切词 -> 剔除纯空格字符。
        无论 Query 还是 Corpus 均须通过此漏斗。
        """
        normalized_text = unicodedata.normalize("NFKC", text)
        tokens = jieba.lcut(normalized_text, cut_all=False)
        return [t.strip() for t in tokens if t.strip()]

    async def rebuild_index(self) -> int:
        """
        全量重新拉取数据库快照，并在内存中原子化重构 BM25 索引。
        绝不拉回无用的 embedding 向量，绝不在失败时破坏当前已有的内存缓存。
        返回：成功索引的块数量。
        """
        try:
            async with async_session() as session:
                stmt = select(
                    KnowledgeChunkRow.chunk_id,
                    KnowledgeChunkRow.document_id,
                    KnowledgeChunkRow.domain,
                    KnowledgeChunkRow.source_title,
                    KnowledgeChunkRow.source_type,
                    KnowledgeChunkRow.section,
                    KnowledgeChunkRow.text,
                ).order_by(KnowledgeChunkRow.chunk_id.asc())

                result = await session.execute(stmt)

                new_chunk_snapshots = []
                for row in result:
                    entry = SparseIndexEntry(
                        chunk_id=row.chunk_id,
                        document_id=row.document_id,
                        domain=KnowledgeDomain(row.domain),
                        source_title=row.source_title,
                        source_type=SourceType(row.source_type),
                        section=row.section,
                        text=row.text,
                    )
                    new_chunk_snapshots.append(entry)
        except Exception as exc:
            raise KnowledgeRetrievalError("从数据库拉取最新快照构建稀疏索引失败。") from exc

        # 第三方库的内存索引建立
        try:
            if not new_chunk_snapshots:
                new_index = None
            else:
                tokenized_corpus = []
                for entry in new_chunk_snapshots:
                    searchable_text = f"{entry.source_title} {entry.section} {entry.text}"
                    tokenized_corpus.append(self._tokenize_sparse_text(searchable_text))

                new_index = bm25s.BM25(method="lucene")
                new_index.index(tokenized_corpus)
        except Exception as exc:
            raise KnowledgeRetrievalError("Jieba 分词与 BM25s 第三方构建过程崩溃。") from exc

        self._bm25_index = new_index
        self._chunk_snapshots = new_chunk_snapshots
        self._is_initialized = True

        return len(self._chunk_snapshots)

    def _matches_filter(self, entry: SparseIndexEntry, filters: Optional[RetrievalFilter]) -> bool:
        if not filters:
            return True
        if filters.domains and entry.domain not in filters.domains:
            return False
        if filters.source_types and entry.source_type not in filters.source_types:
            return False
        if filters.source_titles and entry.source_title not in filters.source_titles:
            return False
        if filters.sections and entry.section not in filters.sections:
            return False
        return True

    def search(
        self, query: str, limit: int, filters: Optional[RetrievalFilter] = None
    ) -> list[SparseSearchHit]:
        """
        在当前内存快照中进行词汇搜索。
        """
        if limit <= 0:
            raise KnowledgeRetrievalError("检索数量必须大于 0。")
        if not self._is_initialized:
            raise KnowledgeRetrievalError("稀疏检索索引尚未初始化，请先执行 rebuild_index。")
        if not query.strip():
            raise KnowledgeRetrievalError("检索查询 (Query) 不能为空。")

        if not self._chunk_snapshots or self._bm25_index is None:
            return []

        try:
            query_tokens = self._tokenize_sparse_text(query)
            if not query_tokens:
                return []

            docs_indices, scores = self._bm25_index.retrieve([query_tokens], k=len(self._chunk_snapshots))

            indices = docs_indices[0].tolist()
            raw_scores = scores[0].tolist()

            candidates: list[tuple[float, str, SparseIndexEntry]] = []

            for i, score in zip(indices, raw_scores):
                if score <= 0:
                    continue
                entry = self._chunk_snapshots[i]

                if not self._matches_filter(entry, filters):
                    continue

                candidates.append((float(score), entry.chunk_id, entry))

            # Tie-break 排序: 按分数降序 (Score DESC), 如果一样按 chunk_id 升序 (chunk_id ASC)
            candidates.sort(key=lambda x: (-x[0], x[1]))

            # 截取最终的合法 Top-K
            final_hits = []
            for score, _, entry in candidates[:limit]:
                hit = SparseSearchHit(
                    chunk_id=entry.chunk_id,
                    document_id=entry.document_id,
                    domain=entry.domain,
                    source_title=entry.source_title,
                    source_type=entry.source_type,
                    section=entry.section,
                    text=entry.text,
                    score=score,
                )
                final_hits.append(hit)

            return final_hits
        except Exception as exc:
            raise KnowledgeRetrievalError("稀疏检索失败。") from exc
