from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from guanchen_v2.router.contracts import INTENT_REQUIRED_DATA, IntentType, RequiredDataType, RoutingResult
from guanchen_v2.router.errors import RouterDispatchError


class RequirementContext(BaseModel):
    """
    当前可用数据的简单快照。
    Checker 只关心对应的 key (RequiredDataType) 是否存在，不解释具体的 value 内容。
    """

    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    available_data: dict[RequiredDataType, object] = Field(
        default_factory=dict,
    )

    @model_validator(mode="after")
    def validate_available_data(self) -> "RequirementContext":
        """防御性拦截：声明为 available 的数据绝对不能是 None"""
        invalid = [key for key, value in self.available_data.items() if value is None]

        if invalid:
            raise ValueError("available_data 中已声明的数据不能为 None")

        return self


class RequirementStatus(StrEnum):
    READY = "ready"
    NEEDS_INPUT = "needs_input"
    BYPASS = "bypass"


class RequirementCheckResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    intent: IntentType
    status: RequirementStatus

    required_data: tuple[RequiredDataType, ...] = ()
    missing_data: tuple[RequiredDataType, ...] = ()

    @model_validator(mode="after")
    def validate_invariants(self) -> "RequirementCheckResult":
        expected_required = INTENT_REQUIRED_DATA[self.intent]
        if self.required_data != expected_required:
            raise ValueError("required_data 与 intent 的确定性需求不一致")

        bypass_intents = {IntentType.CHITCHAT, IntentType.OUT_OF_SCOPE}
        if self.intent in bypass_intents:
            if self.status != RequirementStatus.BYPASS:
                raise ValueError("CHITCHAT / OUT_OF_SCOPE 必须使用 BYPASS 状态")
            if self.missing_data:
                raise ValueError("BYPASS 不允许包含 missing_data")
            return self

        if self.status == RequirementStatus.BYPASS:
            raise ValueError("专业 Intent 不能使用 BYPASS 状态")

        if self.status == RequirementStatus.READY:
            if self.missing_data:
                raise ValueError("READY 状态不能包含 missing_data")
            return self

        if self.status == RequirementStatus.NEEDS_INPUT:
            if not self.missing_data:
                raise ValueError("NEEDS_INPUT 必须包含 missing_data")
            if not set(self.missing_data).issubset(set(self.required_data)):
                raise ValueError("missing_data 必须属于 required_data 的子集")

        return self


def check_requirements(
    routing: RoutingResult,
    context: RequirementContext,
) -> RequirementCheckResult:
    """
    判断当前路由意图所需的数据是否已经满足。
    """
    if routing.secondary_intents:
        raise RouterDispatchError("Single-agent requirement check 不接受双领域 RoutingResult")

    intent = routing.primary_intent

    # CHITCHAT 和 OOS 直接走旁路，不需要任何专业数据校验
    if intent in {IntentType.CHITCHAT, IntentType.OUT_OF_SCOPE}:
        return RequirementCheckResult(
            intent=intent,
            status=RequirementStatus.BYPASS,
            required_data=(),
            missing_data=(),
        )

    # 精确比对当前缺什么
    missing = tuple(item for item in routing.required_data if item not in context.available_data)

    return RequirementCheckResult(
        intent=intent,
        status=RequirementStatus.NEEDS_INPUT if missing else RequirementStatus.READY,
        required_data=routing.required_data,
        missing_data=missing,
    )
