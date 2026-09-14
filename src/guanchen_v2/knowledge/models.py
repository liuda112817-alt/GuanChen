import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import FrozenSet, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KnowledgeDomain(StrEnum):
    """业务领域白名单，防止混入无关知识"""

    BAZI = "bazi"
    YIJING = "yijing"
    LIUYAO = "liuyao"
    TRADITIONAL_CULTURE = "traditional_culture"


class SourceType(StrEnum):
    """知识库来源类型边界"""

    PUBLIC_DOMAIN_CLASSIC = "public_domain_classic"
    PROJECT_NOTE = "project_note"


def normalize_required_text(value: str) -> str:
    """
    通用的基础非空文本校验。
    仅剥离首尾空白，保留内部原有格式（如换行符和段落）。
    """
    normalized = value.strip()
    if not normalized:
        raise ValueError("字段不能为空或纯空格")
    return normalized


def canonicalize_text_for_id(value: str) -> str:
    """
    专用于生成确定性 ID 的文本规范化。
    压缩多余空白符为单空格，保留基础语义分隔以供哈希。
    """
    canonicalized = " ".join(value.split())
    if not canonicalized:
        raise ValueError("文本规范化后不能为空")
    return canonicalized


def generate_deterministic_document_id(domain: str, source_title: str, section: str) -> str:
    """基于领域、书名和章节路径生成确定性逻辑文档 ID。"""
    normalized_domain = normalize_required_text(domain)
    normalized_title = normalize_required_text(source_title)
    normalized_sec = normalize_required_text(section)

    content = f"DOC||{normalized_domain}||{normalized_title}||{normalized_sec}".encode("utf-8")
    return hashlib.sha256(content).hexdigest()[:32]


def generate_deterministic_chunk_id(document_id: str, section: str, text: str) -> str:
    """
    基于内容特征的确定性 ID 生成器 (SHA-256)。
    保证：相同内容二次解析必定产生相同 ID；内容只要改动一丝一毫 ID 就会变化。
    """
    normalized_doc = normalize_required_text(document_id)
    normalized_sec = normalize_required_text(section)
    normalized_text = canonicalize_text_for_id(text)

    content = f"{normalized_doc}||{normalized_sec}||{normalized_text}".encode("utf-8")
    # 采用标准 SHA-256 并截取前 32 位满足极低碰撞率
    return hashlib.sha256(content).hexdigest()[:32]


class KnowledgeDocument(BaseModel):
    """系统吞吐时的逻辑文档单位"""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    domain: KnowledgeDomain
    source_title: str = Field(min_length=1)
    source_type: SourceType
    section: str = Field(min_length=1)
    text: str = Field(min_length=1)

    @field_validator("document_id", "source_title", "section", "text", mode="before")
    @classmethod
    def validate_required_fields(cls, v: str) -> str:
        return normalize_required_text(v)

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
        """来自 Parser 的官方文档构造路径，确保 document_id 的确定性。"""
        document_id = generate_deterministic_document_id(
            domain=domain.value, source_title=source_title, section=section
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
    参与 Embedding 与 Retrieval 的最小事实单元。
    严格隔离业务，不包含任何检索分数、向量等 runtime data。
    """

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    domain: KnowledgeDomain
    source_title: str = Field(min_length=1)
    source_type: SourceType
    section: str = Field(min_length=1)
    text: str = Field(min_length=1)

    @field_validator("chunk_id", "document_id", "source_title", "section", "text", mode="before")
    @classmethod
    def validate_required_fields(cls, v: str) -> str:
        return normalize_required_text(v)

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
        """
        官方唯一合法的构造路径 (Construction Path)。
        强行接管 chunk_id 的生成权，确保业务约束与确定性指纹完美闭合。
        """
        normalized_doc_id = normalize_required_text(document_id)
        normalized_sec = normalize_required_text(section)
        validated_text = normalize_required_text(text)

        chunk_id = generate_deterministic_chunk_id(
            document_id=normalized_doc_id, section=normalized_sec, text=validated_text
        )

        return cls(
            chunk_id=chunk_id,
            document_id=normalized_doc_id,
            domain=domain,
            source_title=source_title,
            source_type=source_type,
            section=normalized_sec,
            text=validated_text,
        )


@dataclass(frozen=True)
class DenseSearchHit:
    """
    Dense Retrieval 返回的候选搜索结果。
    仅用于内部流转，剥离了极占内存的 Embedding 向量。
    注意：score 已经倒置，越大表示相关性越强。
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
    Sparse Retrieval 返回的候选搜索结果。
    仅用于内部流转，完全依赖于 BM25 词汇相关性。
    注意：Score 为 BM25 原始打分，未作归一化，绝对不包含 0 分结果。
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
    """
    稀疏检索器在内存中缓存的只读数据快照实体。
    严格阻断对 SQLAlchemy ORM 对象 (Row) 的直接依赖。
    """

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
    通用检索过滤器，用于在语义/词汇相似度计算之前，圈定检索的合法边界。
    语义规则：
    1. 同一字段内部的多个集合元素属于逻辑 OR (例：属于 BAZI 或 YIJING)
    2. 不同字段之间属于逻辑 AND (例：属于 BAZI 且来源必须是 CLASSIC)
    3. 字段留空或未指定代表“不设限” (Unrestricted)
    """

    domains: Optional[FrozenSet[KnowledgeDomain]] = None
    source_types: Optional[FrozenSet[SourceType]] = None
    source_titles: Optional[FrozenSet[str]] = None
    sections: Optional[FrozenSet[str]] = None


@dataclass(frozen=True)
class RrfSearchHit:
    """
    RRF 阶段融合后的统一候选结果。
    注意：此处的 score 为两路排名换算后的融合分，不再是原生评分。
    保留了 dense_rank 和 sparse_rank 作为探针，以便后续评测。
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
    Reranker (重排模型) 结合原始 Query 重新打分后的最终内部候选结果。
    注意：此处的 score 为 Cross-Encoder 模型原生的 Relevance 浮点分 (Logit)，未经归一化。
    保留了 RRF 以及源阵营的名次探针，是后续组装 Citation 的基石。
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
    """
    RAG 系统的最终、稳定知识搜索结果契约。
    为上层提供统一结果形态，不要求调用方区分 RRF-only 与 Reranker pipeline；同时保留评测探针。
    保留了探针字段以备后续评估 (Eval) 和调试。
    """

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
    展示给最终用户的引用凭证 (Provenance)。
    严禁包含大段正文、不含算法打分、也不含动态的 [1][2] 等回答序号。
    它只证明：“系统检索到的这块内容，来自哪本书的哪一章节。”
    """

    chunk_id: str
    document_id: str
    source_title: str
    section: str

    @classmethod
    def from_retrieval_result(cls, result: RetrievalResult) -> "Citation":
        return cls(
            chunk_id=result.chunk_id,
            document_id=result.document_id,
            source_title=result.source_title,
            section=result.section,
        )
