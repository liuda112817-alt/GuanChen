from guanchen_v2.core.errors import ProjectError


class ApplicationError(ProjectError):
    """Application Layer 核心异常基类"""
    pass

class SessionInitializationError(ApplicationError):
    """Session 创建或加载时发生的严重错误"""
    pass

class ConversationExecutionError(ApplicationError):
    """Orchestrator 执行生命周期（Router, Dispatcher, Synthesizer 等）发生的错误"""
    pass

class StateUpdateError(ApplicationError):
    """ConversationState 更新或合并结果时发生的错误"""
    pass

