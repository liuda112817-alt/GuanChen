from pydantic import BaseModel, ConfigDict, model_validator

from guanchen_v2.router.contracts import IntentType, RequiredDataType, RoutingResult
from guanchen_v2.router.errors import RouterDispatchError
from guanchen_v2.router.requirements import RequirementContext, RequirementStatus


class DualRequirementCheckResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    required_data: tuple[RequiredDataType, ...] = ()
    missing_data: tuple[RequiredDataType, ...] = ()
    status: RequirementStatus

    @model_validator(mode="after")
    def validate_invariants(self) -> "DualRequirementCheckResult":
        if self.status == RequirementStatus.BYPASS:
            raise ValueError("双领域校验不允许 BYPASS 状态")
        if self.status == RequirementStatus.READY and self.missing_data:
            raise ValueError("READY 状态不能包含 missing_data")
        if self.status == RequirementStatus.NEEDS_INPUT and not self.missing_data:
            raise ValueError("NEEDS_INPUT 必须包含 missing_data")
        return self


def check_dual_requirements(routing: RoutingResult, context: RequirementContext) -> DualRequirementCheckResult:
    # 1. 拒收单领域
    if not routing.secondary_intents:
        raise RouterDispatchError("Dual requirement check 仅接受双领域 RoutingResult")

    # 2. 拒收非专业领域的混搭
    non_combinable = {IntentType.CHITCHAT, IntentType.OUT_OF_SCOPE}
    if routing.primary_intent in non_combinable or routing.secondary_intents[0] in non_combinable:
        raise RouterDispatchError("双领域校验不允许包含闲聊或 OOS 等非专业意图")

    # 3. 计算缺失项 (routing.required_data 已经在 Router 层经过严密的 Union 计算)
    missing = tuple(item for item in routing.required_data if item not in context.available_data)

    return DualRequirementCheckResult(
        required_data=routing.required_data,
        missing_data=missing,
        status=RequirementStatus.NEEDS_INPUT if missing else RequirementStatus.READY,
    )
