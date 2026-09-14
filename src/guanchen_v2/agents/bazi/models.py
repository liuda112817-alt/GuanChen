from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from guanchen_v2.knowledge.models import Citation
from guanchen_v2.models.bazi import BaziChart, BirthProfile, Gender


class MissingField(StrEnum):
    """描述缺失资料的具体字段（枚举保证了系统内部流转的稳定判断）"""

    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    HOUR = "hour"
    MINUTE = "minute"
    GENDER = "gender"


class BaziAgentInput(BaseModel):
    """Agent 收到的原始会话参数。只做单字段级的基础验证，组合验证交由 Checker 处理。"""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    year: Optional[int] = Field(default=None, ge=1, le=9999)
    month: Optional[int] = Field(None, ge=1, le=12)
    day: Optional[int] = Field(None, ge=1, le=31)
    hour: Optional[int] = Field(None, ge=0, le=23)
    minute: Optional[int] = Field(None, ge=0, le=59)
    gender: Optional[Gender] = None
    birth_place_text: Optional[str] = None

    @field_validator("question")
    @classmethod
    def check_question_not_empty(cls, v: str) -> str:
        normalized = v.strip()
        if not normalized:
            raise ValueError("question 不能为空或纯空格")
        return normalized


class NeedUserInput(BaseModel):
    """业务状态：资料不完整，需要追问用户。"""

    model_config = ConfigDict(extra="forbid")

    original_question: str
    missing_fields: list[MissingField] = Field(min_length=1)


class InvalidBaziInput(BaseModel):
    """业务状态：资料存在硬伤（如平年2月29日），必须让用户修正，而不是追问缺失信息。"""

    model_config = ConfigDict(extra="forbid")

    original_question: str
    reason: str = Field(min_length=1)


class ReadyForBazi(BaseModel):
    """业务状态：排盘资料完备，可以安全进入计算/Tool 环节。"""

    model_config = ConfigDict(extra="forbid")

    question: str
    profile: BirthProfile


class BaziInterpretation(BaseModel):
    """大模型负责的结构化最终解释（仅限解释，不包含排盘事实）"""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(
        min_length=1,
        description="围绕用户原问题，基于 calculate_bazi 提供的排盘事实生成的传统命理解读。",
    )
    used_chunk_ids: list[str] = Field(
        default_factory=list,
        description="实际在回答中被引用和参考的 BAZI KNOWLEDGE EVIDENCE 中的 chunk_id 列表。没用则留空。",
    )

    @model_validator(mode="after")
    def _validate_logic(self):
        if not self.answer.strip():
            raise ValueError("answer 不能为空或纯空格")
        for cid in self.used_chunk_ids:
            if not cid.strip():
                raise ValueError("used_chunk_ids 元素不能为空或纯空格")
        return self


class BaziAgentResult(BaseModel):
    """最终业务 Contract，由应用代码自身拼装，保证排盘事实来源"""

    model_config = ConfigDict(extra="forbid")

    question: str
    chart: BaziChart
    answer: str
    citations: tuple[Citation, ...]


class BaziBirthDataPatch(BaseModel):
    """
    业务状态：出生资料信息补丁。
    特点是不包含 question。明确提供的字段会覆盖旧值，未提供的字段 (unset) 保持不变。
    """

    model_config = ConfigDict(extra="forbid")

    year: int | None = Field(default=None, ge=1, le=9999)
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)
    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=None, ge=0, le=59)
    gender: Gender | None = None
    birth_place_text: str | None = None
