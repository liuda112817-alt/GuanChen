from guanchen_v2.core.errors import ProjectError


class RouterDispatchError(ProjectError):
    """
    Router 与 Requirement Check / Dispatch 过程中的调度异常。
    例如：双领域违规进入单领域分发器、Intent 上下文断裂等。
    """

    pass
