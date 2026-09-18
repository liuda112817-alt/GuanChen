class ProjectError(RuntimeError):
    """
    GuanChen 所有稳定项目级异常的共同根类型。

    该类型只提供统一异常边界，不承载：
    - error code
    - HTTP status
    - logging policy
    - retry policy
    - user-facing message mapping

    各子系统继续使用自己的异常层级表达具体语义。
    """

    pass

class SessionStateError(ProjectError):
    """
    Application Session State 异常。
    
    处理：
    - invalid state
    - serialization failure
    - validation failure
    
    不归属：
    - AgentError
    - DatabaseError
    """
    pass

