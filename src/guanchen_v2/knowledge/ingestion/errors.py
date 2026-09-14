from guanchen_v2.knowledge.errors import KnowledgeError


class KnowledgeIngestionError(KnowledgeError):
    """GuanChen 知识注入管道基础异常"""

    pass


class KnowledgeSourceLoadError(KnowledgeIngestionError):
    """在文件发现与加载环节发生的严重阻断异常（如：编码错误、目录越界、H1异常等）"""

    pass


class KnowledgeStructureParseError(KnowledgeIngestionError):
    """Markdown 知识源结构不满足 GuanChen ingestion contract (如跳级、路径重复等)"""

    pass


class KnowledgeChunkingError(KnowledgeIngestionError):
    """KnowledgeDocument 无法满足 GuanChen chunking contract."""

    pass
