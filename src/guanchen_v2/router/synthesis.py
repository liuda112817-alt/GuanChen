from pydantic import BaseModel, ConfigDict, Field

from guanchen_v2.knowledge.models import Citation
from guanchen_v2.router.contracts import IntentType
from guanchen_v2.router.dual_dispatch import AgentExecutionResult


class SynthesisInput(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    query: str
    results: tuple[AgentExecutionResult, ...]


class SynthesisDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1)


class SynthesizedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    used_intents: tuple[IntentType, ...] = Field(description="本次整合结果所涵盖的专业领域意图列表")

    session_id: str | None = None
    status: str = "answered"
    thread_id: str | None = None
    citations: tuple[Citation, ...] = ()

    facts: dict = Field(default_factory=dict)
    output_blocked: bool = False
