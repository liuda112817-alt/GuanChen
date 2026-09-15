from dataclasses import dataclass

from pydantic import BaseModel, Field, model_validator

from guanchen_v2.knowledge.models import Citation


class KnowledgeAnswerDraft(BaseModel):
    """
    LLM 的结构化输出草稿纸。
    模型通过这个结构告诉我们：它的解释是什么、当前提供的证据是否充分，以及它到底“翻阅”了哪些物证。
    """

    answer: str = Field(description="基于提供证据对用户问题的解答与分析。")
    evidence_sufficient: bool = Field(description="标识现有的检索证据是否足以完整、确切地回答该问题。")
    used_chunk_ids: list[str] = Field(description="实际在回答中被引用和参考的证据块 ID 列表。")

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _validate_logic(self):
        if not self.answer.strip():
            raise ValueError("回答内容不能留空。")
        if self.evidence_sufficient and not self.used_chunk_ids:
            raise ValueError("当声明证据充分时，必须至少提供一个实际引用的 chunk_id。")
        return self


@dataclass(frozen=True)
class KnowledgeAgentResponse:
    """
    Knowledge Agent 对外输出的最终结果。
    完全屏蔽了打分与排名，只提供解释、充分性声明与血缘证明。
    """

    answer: str
    evidence_sufficient: bool
    citations: tuple[Citation, ...]
