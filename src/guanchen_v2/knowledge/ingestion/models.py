from pydantic import BaseModel, ConfigDict, Field

from guanchen_v2.knowledge.models import KnowledgeDomain, SourceType


class LoadedKnowledgeSource(BaseModel):
    """
    Ingestion 管道专用的源对象 (File-level)。
    代表一个已经通过边界校验，且带有稳固元数据特征的纯净 Markdown 文件。
    """

    model_config = ConfigDict(extra="forbid")

    source_path: str = Field(min_length=1, description="相对 raw_verified_root 的 POSIX 路径")
    domain: KnowledgeDomain
    source_title: str = Field(min_length=1, description="提取自文件唯一 H1 标题")
    source_type: SourceType
    text: str = Field(min_length=1, description="文件原始内容，未经任何清洗")


class NormalizedKnowledgeSource(BaseModel):
    """
    完成 NFKC 和格式净化的 Source (File-level)。
    处于可进入结构化 Parser 的最终就绪状态。
    """

    model_config = ConfigDict(extra="forbid")

    source_path: str = Field(min_length=1)
    domain: KnowledgeDomain
    source_title: str = Field(min_length=1)
    source_type: SourceType
    text: str = Field(min_length=1)
