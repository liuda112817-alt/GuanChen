class KnowledgeError(RuntimeError):
    """GuanChen 知识模块的根异常"""

    pass


class KnowledgeEmbeddingError(KnowledgeError):
    """Embedding 过程中的项目级异常，屏蔽第三方模型或设备错误"""

    pass


class KnowledgePersistenceError(KnowledgeError):
    """知识库持久化与数据库操作相关的基础异常，屏蔽底层 SQLAlchemy / asyncpg 错误。"""

    pass


class KnowledgeTransactionError(KnowledgePersistenceError):
    """在执行整个 Knowledge Document 替换事务时发生的不可恢复崩溃。"""

    pass


class KnowledgeRetrievalError(KnowledgeError):
    """知识检索相关的基础异常，屏蔽底层或非法输入导致的崩溃。"""

    pass


class KnowledgeRerankerError(KnowledgeRetrievalError):
    """知识重排模型加载或推理相关的异常。"""

    pass


class KnowledgeAgentError(KnowledgeError):
    """
    Knowledge Agent 执行过程中的业务违规异常。
    主要用于拦截非法的 Query、伪造的 chunk_id 以及其他未按契约工作的模型返回。
    """

    pass
