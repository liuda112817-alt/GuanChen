from pydantic import BaseModel, ConfigDict, Field

from guanchen_v2.router.contracts import IntentType
from guanchen_v2.router.dual_dispatch import AgentExecutionResult


class SynthesisInput(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    query: str
    results: tuple[AgentExecutionResult, ...]


class SynthesizedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    used_intents: tuple[IntentType, ...] = Field(description="本次整合结果所涵盖的专业领域意图列表")
