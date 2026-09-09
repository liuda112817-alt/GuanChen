from guanchen_v2.agents.bazi.models import (
    BaziAgentInput,
    BaziAgentResult,
    BaziBirthDataPatch,
    InvalidBaziInput,
    NeedUserInput,
    ReadyForBazi,
)
from guanchen_v2.agents.bazi.requirements import check_bazi_requirements
from guanchen_v2.agents.bazi.runtime import BaziAgentRuntime

type BaziTaskResult = NeedUserInput | InvalidBaziInput | BaziAgentResult


class BaziTaskSession:
    """
    单个八字分析任务的内存状态会话。
    负责安全的跨轮次（Multi-turn）资料收集，
    并严格限制 Agent Runtime 在 Ready 状态才执行且仅执行一次。
    """

    def __init__(self, initial_input: BaziAgentInput, runtime: BaziAgentRuntime) -> None:
        self._current_input = initial_input
        self._runtime = runtime
        self._result: BaziAgentResult | None = None

    def evaluate(self) -> BaziTaskResult:
        """评估当前任务状态，若资料齐备则触发并返回最终结果。"""
        if self._result is not None:
            return self._result

        req_result = check_bazi_requirements(self._current_input)

        if isinstance(req_result, ReadyForBazi):
            self._result = self._runtime.run(req_result)
            return self._result

        return req_result

    def supplement(self, patch: BaziBirthDataPatch) -> BaziTaskResult:
        """
        接收出生资料补丁。

        字段级非法 Patch 会在写入 Session 前被 Pydantic 拦截；
        字段级合法的更新先合并进当前任务状态，
        跨字段组合合法性随后由 Requirement Checker 判断。

        因此组合错误可以作为当前业务状态保留，
        供用户下一轮继续修正。
        """
        if self._result is not None:
            raise RuntimeError("任务已完成。")

        current_data = self._current_input.model_dump()
        updates = patch.model_dump(exclude_unset=True)
        merged = {**current_data, **updates}

        new_input = BaziAgentInput.model_validate(merged)
        self._current_input = new_input

        return self.evaluate()
