from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from guanchen_v2.knowledge.models import Citation


class AgentExecutionStatus(StrEnum):
    """
    Agent 执行状态。

    用于 Router / Orchestrator 判断后续行为。
    """

    SUCCESS = "success"

    NEEDS_INPUT = "needs_input"

    FAILED = "failed"


class AgentResponse(BaseModel):
    """
    GuanChen v2 统一 Agent 输出 Contract。

    所有领域 Agent 最终必须转换为该结构。

    注意：
    domain_payload 保存领域专属结果。
    Router / Application 不应该解析其中业务字段。
    """

    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    status: AgentExecutionStatus = Field(
        default=AgentExecutionStatus.SUCCESS
    )

    answer: str = Field(
        description="最终面向用户的文本结果"
    )

    citations: tuple[Citation, ...] = Field(
        default_factory=tuple,
        description="统一引用信息"
    )

    domain: str = Field(
        description="Agent 所属领域，例如 bazi/dream/liuyao"
    )

    domain_payload: dict[str, Any] = Field(
        default_factory=dict,
        description="领域专属结构化结果"
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="非业务控制信息，例如 trace/session 信息"
    )