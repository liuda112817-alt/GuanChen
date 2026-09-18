from datetime import datetime, timezone
from enum import IntEnum, StrEnum
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonBlankText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class DecisionQuestionStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_CLARIFICATION = "needs_clarification"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class CastingMethod(StrEnum):
    SYSTEM_THREE_COIN = "system_three_coin"
    MANUAL_SIX_LINES = "manual_six_lines"


class LineValue(IntEnum):
    OLD_YIN = 6
    YOUNG_YANG = 7
    YOUNG_YIN = 8
    OLD_YANG = 9


class YinYang(StrEnum):
    YIN = "yin"
    YANG = "yang"


class CoinFace(StrEnum):
    HEAD = "head"
    TAIL = "tail"


class CoinToss(BaseModel):
    model_config = ConfigDict(extra="forbid")
    position: int
    coins: tuple[CoinFace, CoinFace, CoinFace]
    line_value: LineValue


class HexagramLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    position: int = Field(ge=1, le=6)
    value: LineValue

    polarity: YinYang
    moving: bool

    heavenly_stem: NonBlankText | None = None
    earthly_branch: NonBlankText | None = None
    element: NonBlankText | None = None
    six_relative: NonBlankText | None = None
    six_spirit: NonBlankText | None = None
    is_shi: bool = False
    is_ying: bool = False


class HexagramIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: NonBlankText | None = None
    upper_trigram: NonBlankText
    lower_trigram: NonBlankText


class HexagramResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    casting_method: CastingMethod
    line_order: Literal["bottom_to_top"] = "bottom_to_top"

    lines: tuple[HexagramLine, ...]

    primary_hexagram: HexagramIdentity
    changed_hexagram: HexagramIdentity | None = None
    moving_line_positions: list[int] = Field(default_factory=list)
    coin_tosses: list[CoinToss] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_invariants(self) -> "HexagramResult":
        if len(self.lines) != 6:
            raise ValueError("HexagramResult 必须正好包含 6 爻")

        for i, line in enumerate(self.lines, start=1):
            if line.position != i:
                raise ValueError(f"第 {i} 爻的 position 必须为 {i}")

            is_yin = line.polarity == YinYang.YIN
            is_moving = line.moving

            if line.value == LineValue.OLD_YIN and (not is_yin or not is_moving):
                raise ValueError("老阴(6) 必须是阴且动")
            elif line.value == LineValue.YOUNG_YANG and (is_yin or is_moving):
                raise ValueError("少阳(7) 必须是阳且静")
            elif line.value == LineValue.YOUNG_YIN and (not is_yin or is_moving):
                raise ValueError("少阴(8) 必须是阴且静")
            elif line.value == LineValue.OLD_YANG and (is_yin or not is_moving):
                raise ValueError("老阳(9) 必须是阳且动")

        actual_moving = [line.position for line in self.lines if line.moving]
        if self.moving_line_positions != actual_moving:
            raise ValueError("moving_line_positions 必须与各爻的 moving 状态一致")

        if actual_moving and self.changed_hexagram is None:
            raise ValueError("存在动爻时，必须包含 changed_hexagram")
        if not actual_moving and self.changed_hexagram is not None:
            raise ValueError("无动爻时，不能包含 changed_hexagram")

        if self.casting_method == CastingMethod.SYSTEM_THREE_COIN:
            if len(self.coin_tosses) != 6:
                raise ValueError("使用系统三枚硬币法时，必须包含正好 6 次 coin_tosses 记录")
            for i, toss in enumerate(self.coin_tosses):
                if toss.position != i + 1:
                    raise ValueError(f"coin_tosses[{i}] 的 position 必须是 {i + 1}")
                if toss.line_value != self.lines[i].value:
                    raise ValueError(f"coin_tosses[{i}] 的 line_value 必须与 lines[{i}] 一致")

                coin_sum = sum(3 if c == CoinFace.HEAD else 2 for c in toss.coins)
                if coin_sum != toss.line_value.value:
                    raise ValueError(f"coin_tosses[{i}] 的硬币组合之和不等于 {toss.line_value.value}")
        elif self.casting_method == CastingMethod.MANUAL_SIX_LINES:
            if len(self.coin_tosses) != 0:
                raise ValueError("手工起卦不能包含 coin_tosses 记录")

        return self


class DecisionQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    original_question: NonBlankText = Field(description="用户最初提出的问题原文")
    clarified_question: NonBlankText | None = Field(default=None)
    reality_constraints: list[NonBlankText] = Field(default_factory=list)
    status: DecisionQuestionStatus = DecisionQuestionStatus.DRAFT

    @model_validator(mode="after")
    def validate_question_state(self) -> "DecisionQuestion":
        if (
            self.status
            in {
                DecisionQuestionStatus.PENDING_CONFIRMATION,
                DecisionQuestionStatus.CONFIRMED,
            }
            and self.clarified_question is None
        ):
            raise ValueError("待确认或已确认的问题必须存在 clarified_question")
        return self


class DecisionReflection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    situation_summary: NonBlankText = Field(description="对用户当前面临决策情境和现实约束的客观总结")
    traditional_reflection: NonBlankText = Field(description="严格基于 Retrieval Evidence 与 Hexagram Facts 得出的传统文化视角反思")
    reality_check: NonBlankText = Field(
        description="将传统文化视角与用户明确提出的 reality_constraints 相结合的现实校验。当传统结论与现实冲突时，提示现实约束优先"
    )
    decision_options: list[NonBlankText] = Field(
        description="给用户提供的可进一步评估或行动的方向参考，而非必须执行的命令",
        min_length=1,
    )
    uncertainty_note: NonBlankText = Field(description="免责与边界声明，明确表示该推演仅作文化参考，不能用于确定性预测")


class DecisionRecord(BaseModel):
    """
    六爻决策域的持久化领域记录（Stage 8）。

    只保存用户明确提供 / 确认的问题与确定性 / 结构化产物，
    不保存任何自动抽取的隐式画像。
    """

    model_config = ConfigDict(extra="forbid")

    record_id: UUID = Field(default_factory=uuid4)

    question: DecisionQuestion = Field(description="澄清 / 确认后的决策问题")

    thread_id: str = Field(
        min_length=1,
        description="关联的 LangGraph 持久线程 ID，用于跨进程恢复 HITL 流程",
    )

    status: DecisionQuestionStatus = DecisionQuestionStatus.DRAFT

    hexagram: HexagramResult | None = None

    reflection: DecisionReflection | None = None

    final_response: str | None = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
