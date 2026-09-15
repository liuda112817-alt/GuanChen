from guanchen_v2.core.errors import ProjectError


class KnowledgeError(ProjectError):
    """GuanChen Knowledge 子系统异常根类型。"""

    pass


class KnowledgeEmbeddingError(KnowledgeError):
    """
    Embedding 模型加载、推理或向量契约异常。
    """

    pass


class KnowledgePersistenceError(KnowledgeError):
    """
    Knowledge persistence / database 基础异常。
    """

    pass


class KnowledgeTransactionError(KnowledgePersistenceError):
    """
    Knowledge document transaction 执行失败。
    """

    pass


class KnowledgeRetrievalError(KnowledgeError):
    """
    Knowledge retrieval 执行或输入契约异常。
    """

    pass


class KnowledgeRerankerError(KnowledgeRetrievalError):
    """
    Reranker 模型加载、推理或结果契约异常。
    """

    pass


class KnowledgeAgentError(KnowledgeError):
    """
    Knowledge Agent 业务契约异常。

    例如：
    - 非法 query
    - 非法 evidence lineage
    - 模型返回未授权 chunk_id
    """

    pass
