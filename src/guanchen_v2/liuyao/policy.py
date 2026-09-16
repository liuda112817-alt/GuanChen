from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from guanchen_v2.liuyao.exceptions import LiuyaoPolicyError
from guanchen_v2.liuyao.state import LiuyaoState
from guanchen_v2.models.liuyao import (
    DecisionQuestion,
    DecisionQuestionStatus,
    NonBlankText,
)


class ConfirmationAction(StrEnum):
    CONFIRM = "confirm"
    MODIFY = "modify"
    CANCEL = "cancel"


class ConfirmationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ConfirmationAction
    modification: NonBlankText | None = None

    @model_validator(mode="after")
    def validate_action_payload(self) -> "ConfirmationResponse":
        if self.action != ConfirmationAction.MODIFY and self.modification is not None:
            raise ValueError("只有 MODIFY action 可以携带 modification")
        return self


class ClarificationAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    needs_clarification: bool
    clarified_question: NonBlankText | None = None
    reality_constraints: list[NonBlankText] = Field(default_factory=list)
    clarification_prompt: NonBlankText | None = None

    @model_validator(mode="after")
    def validate_assessment(self) -> "ClarificationAssessment":
        if self.needs_clarification:
            if self.clarification_prompt is None:
                raise ValueError("需要澄清时必须提供 clarification_prompt")
            if self.clarified_question is not None:
                raise ValueError("尚需澄清时不能提前形成 clarified_question")
        else:
            if self.clarified_question is None:
                raise ValueError("可进入确认时必须存在 clarified_question")
            if self.clarification_prompt is not None:
                raise ValueError("已形成候选问题时不能继续携带 clarification_prompt")
        return self


def rebuild_question(
    question: DecisionQuestion,
    **updates: Any,
) -> DecisionQuestion:
    """使用完整 model_validator 重新校验并构建 DecisionQuestion"""
    payload = question.model_dump()
    payload.update(updates)
    return DecisionQuestion.model_validate(payload)


def invalidate_downstream(state: LiuyaoState) -> LiuyaoState:
    """统一的下游结果失效清空 helper，修改问题会导致所有后续资产失效"""
    return {
        **state,
        "confirmed": False,
        "hexagram": None,
        "retrieved_context": [],
        "reflection": None,
        "citations": [],
        "final_response": None,
    }


def project_confirmed(question: DecisionQuestion) -> bool:
    """confirmed 状态永远由 question.status 确定性投影"""
    return question.status == DecisionQuestionStatus.CONFIRMED


def validate_confirmation_projection(state: LiuyaoState) -> None:
    """State 一致性 Guard：防止 status 与 confirmed 出现孤立脱节"""
    question: DecisionQuestion | None = state.get("question")
    if not question:
        raise LiuyaoPolicyError("六爻状态机中缺少 DecisionQuestion")

    expected = project_confirmed(question)
    if state.get("confirmed", False) != expected:
        raise LiuyaoPolicyError("六爻确认状态不一致")


def can_cast(state: LiuyaoState) -> bool:
    """
    确定性起卦硬门槛：
    只有 question.status == CONFIRMED 且 confirmed projection 一致时才允许起卦。
    """
    validate_confirmation_projection(state)
    question: DecisionQuestion = state["question"]
    return question.status == DecisionQuestionStatus.CONFIRMED


def apply_clarification_assessment(
    state: LiuyaoState,
    assessment: ClarificationAssessment,
) -> LiuyaoState:
    """根据 LLM 的 ClarificationAssessment 驱动状态机更新"""
    validate_confirmation_projection(state)
    question: DecisionQuestion = state["question"]

    # 防止非草稿/非澄清阶段直接通过评估结果重写状态，绕过显式 MODIFY 语义
    if question.status not in {
        DecisionQuestionStatus.DRAFT,
        DecisionQuestionStatus.NEEDS_CLARIFICATION,
    }:
        raise LiuyaoPolicyError(f"当前状态 {question.status} 不允许直接应用澄清结果")

    # 若之前已处于非 DRAFT 状态，新 proposal 产生时需要先清理下游
    cleaned_state = invalidate_downstream(state)

    if assessment.needs_clarification:
        new_q = rebuild_question(
            question,
            status=DecisionQuestionStatus.NEEDS_CLARIFICATION,
            clarified_question=None,
            reality_constraints=assessment.reality_constraints,
        )
        return {
            **cleaned_state,
            "question": new_q,
            "clarification": assessment.clarification_prompt,
            "pending_user_input": None,  # 无论何种分支，澄清一旦成功应用，均视为已消费修改意见
            "confirmed": project_confirmed(new_q),
        }
    else:
        new_q = rebuild_question(
            question,
            status=DecisionQuestionStatus.PENDING_CONFIRMATION,
            clarified_question=assessment.clarified_question,
            reality_constraints=assessment.reality_constraints,
        )
        return {
            **cleaned_state,
            "question": new_q,
            "clarification": None,
            "pending_user_input": None,  # 成功形成候选问题，清空 pending 缓冲
            "confirmed": project_confirmed(new_q),
        }


def apply_confirmation_response(
    state: LiuyaoState,
    response: ConfirmationResponse,
) -> LiuyaoState:
    """根据用户的 ConfirmationResponse 驱动状态机更新（CONFIRM / MODIFY / CANCEL）"""
    validate_confirmation_projection(state)
    question: DecisionQuestion = state["question"]
    current_status = question.status

    # 1. 处理 CONFIRM
    if response.action == ConfirmationAction.CONFIRM:
        if current_status == DecisionQuestionStatus.CONFIRMED:
            return state
        if current_status != DecisionQuestionStatus.PENDING_CONFIRMATION:
            raise LiuyaoPolicyError(f"当前状态 {current_status} 不允许直接确认")

        new_q = rebuild_question(question, status=DecisionQuestionStatus.CONFIRMED)
        return {
            **state,
            "question": new_q,
            "confirmed": project_confirmed(new_q),
        }

    # 2. 处理 MODIFY
    elif response.action == ConfirmationAction.MODIFY:
        if current_status not in {
            DecisionQuestionStatus.PENDING_CONFIRMATION,
            DecisionQuestionStatus.CONFIRMED,
        }:
            raise LiuyaoPolicyError(f"当前状态 {current_status} 不支持修改")

        cleaned_state = invalidate_downstream(state)
        new_q = rebuild_question(
            question,
            status=DecisionQuestionStatus.NEEDS_CLARIFICATION,
            clarified_question=None,
        )

        modification = response.modification
        return {
            **cleaned_state,
            "question": new_q,
            "clarification": (None if modification is not None else "请问您希望如何修改或补充当前问题？"),
            "pending_user_input": modification,
            "confirmed": project_confirmed(new_q),
        }

    # 3. 处理 CANCEL
    elif response.action == ConfirmationAction.CANCEL:
        if current_status == DecisionQuestionStatus.CANCELLED:
            return state
        if current_status not in {
            DecisionQuestionStatus.PENDING_CONFIRMATION,
            DecisionQuestionStatus.CONFIRMED,
        }:
            raise LiuyaoPolicyError(f"当前状态 {current_status} 无法取消")

        cleaned_state = invalidate_downstream(state)
        new_q = rebuild_question(question, status=DecisionQuestionStatus.CANCELLED)
        return {
            **cleaned_state,
            "question": new_q,
            "confirmed": project_confirmed(new_q),
        }

    raise LiuyaoPolicyError(f"未知的确认动作: {response.action}")
