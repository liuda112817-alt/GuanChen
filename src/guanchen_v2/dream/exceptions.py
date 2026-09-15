from guanchen_v2.core.errors import ProjectError


class DreamError(ProjectError):
    """
    GuanChen Dream 子系统异常根类型。
    """

    pass


class DreamMergeConflictError(DreamError):
    """
    DreamRecord merge 过程中出现不可满足的状态冲突。
    """

    pass


class DreamExtractionError(DreamError):
    """
    梦境结构化增量信息抽取失败。
    """

    pass


class DreamInterpretationError(DreamError):
    """
    梦境解释生成或证据契约验证失败。
    """

    pass
