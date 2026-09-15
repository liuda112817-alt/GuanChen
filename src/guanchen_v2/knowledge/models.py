import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import FrozenSet, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KnowledgeDomain(StrEnum):
    """共享知识库支持的业务知识领域白名单。"""

    BAZI = "bazi"
    YIJING = "yijing"
    LIUYAO = "liuyao"
    DREAM = "dream"
    TRADITIONAL_CULTURE = "traditional_culture"


class SourceType(StrEnum):
    """知识库来源类型边界。"""

    PUBLIC_DOMAIN_CLASSIC = "public_domain_classic"
    PROJECT_NOTE = "project_note"


def normalize_required_text(value: str) -> str:
    """
    通用基础非空文本校验。

    仅剥离首尾空白，保留内部原有格式，
    包括换行、段落和有意义的空格。
    """
    normalized = value.strip()

    if not normalized:
        raise ValueError("字段不能为空或纯空格")

    return normalized


def canonicalize_text_for_id(value: str) -> str:
    """
    专用于确定性 ID 的文本规范化。

    将连续空白规范为单空格，
    不用于修改实际持久化的 KnowledgeDocument.text
    或 KnowledgeChunk.text。
    """
    canonicalized = " ".join(value.split())

    if not canonicalized:
        raise ValueError("文本规范化后不能为空")

    return canonicalized


def generate_deterministic_document_id(
    domain: str,
    source_title: str,
    section: str,
) -> str:
    """基于领域、书名和章节路径生成稳定逻辑文档 ID。"""
    normalized_domain = normalize_required_text(domain)
    normalized_title = normalize_required_text(source_title)
    normalized_section = normalize_required_text(section)

    content = (f"DOC||{normalized_domain}||{normalized_title}||{normalized_section}").encode("utf-8")

    return hashlib.sha256(content).hexdigest()[:32]


def generate_deterministic_chunk_id(
    document_id: str,
    section: str,
    text: str,
) -> str:
    """
    基于 Document identity 与规范化 Chunk 内容生成确定性 ID。

    whitespace-only 差异经过 canonicalization 后不会改变 ID；
    规范化后的实际内容变化会改变 ID。
    """
    normalized_document_id = normalize_required_text(document_id)
    normalized_section = normalize_required_text(section)
    canonicalized_text = canonicalize_text_for_id(text)

    content = (f"{normalized_document_id}||{normalized_section}||{canonicalized_text}").encode("utf-8")

    return hashlib.sha256(content).hexdigest()[:32]


class KnowledgeDocument(BaseModel):
    """具有稳定来源身份的逻辑知识文档单元。"""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    domain: KnowledgeDomain
    source_title: str = Field(min_length=1)
    source_type: SourceType
    section: str = Field(min_length=1)
    text: str = Field(min_length=1)

    @field_validator(
        "document_id",
        "source_title",
        "section",
        "text",
        mode="before",
    )
    @classmethod
    def validate_required_fields(cls, value: str) -> str:
        return normalize_required_text(value)

    @classmethod
    def from_parser(
        cls,
        *,
        domain: KnowledgeDomain,
        source_title: str,
        source_type: SourceType,
        section: str,
        text: str,
    ) -> "KnowledgeDocument":
        """Parser 创建 KnowledgeDocument 的标准构造入口。"""
        document_id = generate_deterministic_document_id(
            domain=domain.value,
            source_title=source_title,
            section=section,
        )

        return cls(
            document_id=document_id,
            domain=domain,
            source_title=source_title,
            source_type=source_type,
            section=section,
            text=text,
        )


class KnowledgeChunk(BaseModel):
    """
    Embedding 与 Retrieval 使用的最小知识搜索单元。

    不持有向量、检索分数或 query-time ranking 信息。
    """

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    domain: KnowledgeDomain
    source_title: str = Field(min_length=1)
    source_type: SourceType
    section: str = Field(min_length=1)
    text: str = Field(min_length=1)

    @field_validator(
        "chunk_id",
        "document_id",
        "source_title",
        "section",
        "text",
        mode="before",
    )
    @classmethod
    def validate_required_fields(cls, value: str) -> str:
        return normalize_required_text(value)

    @classmethod
    def from_document_part(
        cls,
        *,
        document_id: str,
        domain: KnowledgeDomain,
        source_title: str,
        source_type: SourceType,
        section: str,
        text: str,
    ) -> "KnowledgeChunk":
        """由 KnowledgeDocument 派生 Chunk 的标准构造入口。"""
        normalized_document_id = normalize_required_text(document_id)
        normalized_section = normalize_required_text(section)
        validated_text = normalize_required_text(text)

        chunk_id = generate_deterministic_chunk_id(
            document_id=normalized_document_id,
            section=normalized_section,
            text=validated_text,
        )

        return cls(
            chunk_id=chunk_id,
            document_id=normalized_document_id,
            domain=domain,
            source_title=source_title,
            source_type=source_type,
            section=normalized_section,
            text=validated_text,
        )


@dataclass(frozen=True)
class DenseSearchHit:
    """
    Dense Retrieval 返回的内部候选结果。

    score 越大表示相关性越强。
    Embedding 本身不进入该对象。
    """

    chunk_id: str
    document_id: str
    domain: KnowledgeDomain
    source_title: str
    source_type: SourceType
    section: str
    text: str
    score: float


@dataclass(frozen=True)
class SparseSearchHit:
    """
    Sparse Retrieval 返回的内部候选结果。

    score 为 BM25 原始分值，不进行跨检索器直接比较。
    """

    chunk_id: str
    document_id: str
    domain: KnowledgeDomain
    source_title: str
    source_type: SourceType
    section: str
    text: str
    score: float


@dataclass(frozen=True)
class SparseIndexEntry:
    """SparseRetriever 使用的只读知识快照。"""

    chunk_id: str
    document_id: str
    domain: KnowledgeDomain
    source_title: str
    source_type: SourceType
    section: str
    text: str


@dataclass(frozen=True)
class RetrievalFilter:
    """
    统一检索过滤器。

    同一字段中的多个值使用 OR 语义；
    不同字段之间使用 AND 语义；
    None 表示该字段不设限制。
    """

    domains: Optional[FrozenSet[KnowledgeDomain]] = None
    source_types: Optional[FrozenSet[SourceType]] = None
    source_titles: Optional[FrozenSet[str]] = None
    sections: Optional[FrozenSet[str]] = None


@dataclass(frozen=True)
class RrfSearchHit:
    """
    RRF 融合后的内部候选结果。

    score 为 RRF 融合分。
    """

    chunk_id: str
    document_id: str
    domain: KnowledgeDomain
    source_title: str
    source_type: SourceType
    section: str
    text: str
    score: float
    dense_rank: Optional[int]
    sparse_rank: Optional[int]


@dataclass(frozen=True)
class RerankedSearchHit:
    """
    Reranker 重排后的内部候选结果。

    score 为 reranker 原始 relevance score。
    """

    chunk_id: str
    document_id: str
    domain: KnowledgeDomain
    source_title: str
    source_type: SourceType
    section: str
    text: str
    score: float
    rrf_score: float
    rrf_rank: int
    dense_rank: Optional[int]
    sparse_rank: Optional[int]


@dataclass(frozen=True)
class RetrievalResult:
    """RAG 对上层暴露的稳定最终检索结果。"""

    rank: int
    chunk_id: str
    document_id: str
    domain: KnowledgeDomain
    source_title: str
    source_type: SourceType
    section: str
    text: str
    rrf_score: float
    rrf_rank: int
    reranker_score: Optional[float]
    dense_rank: Optional[int]
    sparse_rank: Optional[int]


@dataclass(frozen=True)
class Citation:
    """
    对最终回答暴露的稳定知识来源凭证。

    不包含正文、检索分数或动态引用序号。
    """

    chunk_id: str
    document_id: str
    source_title: str
    section: str

    @classmethod
    def from_retrieval_result(
        cls,
        result: RetrievalResult,
    ) -> "Citation":
        return cls(
            chunk_id=result.chunk_id,
            document_id=result.document_id,
            source_title=result.source_title,
            section=result.section,
        )
