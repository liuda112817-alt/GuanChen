from guanchen_v2.core.errors import ProjectError


class MemoryError(ProjectError):
    """Memory Store 基础异常"""
    pass

class MemoryNotFoundError(MemoryError):
    """
    更新或读取时，Session 不存在。
    注意：load() 允许返回 None，但 update() 必须抛出此异常。
    """
    pass

class MemoryAlreadyExistsError(MemoryError):
    """
    创建（save）Session 时，指定的 Session ID 已存在。
    """
    pass

class MemoryPersistenceError(MemoryError):
    """
    未来供数据库后端使用，例如序列化失败、网络故障或数据库崩溃。
    """
    pass

