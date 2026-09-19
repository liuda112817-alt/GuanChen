from guanchen_v2.api.contracts import ChatResponse, ChatStatus, CitationResponse, InputRequirement, InterruptResponse
from guanchen_v2.core.session.models import ConversationState
from guanchen_v2.router.contracts import IntentType, RequiredDataType
from guanchen_v2.router.synthesis import SynthesizedResponse
from guanchen_v2.safety.models import SafetyDecision


class ChatResponseMapper:
    def map(
        self,
        result: SynthesizedResponse,
        *,
        safety: SafetyDecision | None,
        state: ConversationState | None,
    ) -> ChatResponse:

        status_map = {
            "answered": ChatStatus.ANSWERED,
            "needs_input": ChatStatus.NEEDS_INPUT,
            "needs_clarification": ChatStatus.NEEDS_INPUT,
            "interrupted": ChatStatus.INTERRUPTED,
            "cancelled": ChatStatus.CANCELLED,
        }
        try:
            api_status = status_map[result.status]
        except KeyError as exc:
            raise ValueError(f"Unsupported runtime response status: {result.status}") from exc

        # used_intents 现在拒绝静默修复
        used_intents = tuple(result.used_intents)

        required_input = None
        if api_status == ChatStatus.NEEDS_INPUT:
            if result.status == "needs_clarification":
                required_input = InputRequirement(kind=RequiredDataType.DREAM_CONTENT, fields=())
            else:
                missing_data = tuple(state.requirement_result.missing_data) if state and state.requirement_result else ()

                # 严格基于 Requirement missing_data 确定需求种类
                if RequiredDataType.BIRTH_PROFILE in missing_data:
                    need = state.agent_states.bazi.get("input_requirement", {}) if state else {}
                    required_input = InputRequirement(kind=RequiredDataType.BIRTH_PROFILE, fields=tuple(need.get("missing_fields", ())))
                elif RequiredDataType.DECISION_QUESTION in missing_data:
                    required_input = InputRequirement(kind=RequiredDataType.DECISION_QUESTION, fields=())
                elif RequiredDataType.DREAM_CONTENT in missing_data:
                    required_input = InputRequirement(kind=RequiredDataType.DREAM_CONTENT, fields=())
                # 兜底：Requirement 已准备好但 Agent 主动引发 Needs Input
                elif IntentType.LIUYAO in used_intents:
                    required_input = InputRequirement(kind=RequiredDataType.DECISION_QUESTION, fields=())
                elif IntentType.DREAM in used_intents:
                    required_input = InputRequirement(kind=RequiredDataType.DREAM_CONTENT, fields=())
                else:
                    raise ValueError("Unable to map runtime needs_input state accurately")

        interrupt = None
        if api_status == ChatStatus.INTERRUPTED:
            if not getattr(result, "thread_id", None):
                raise ValueError("Interrupted runtime response must contain thread_id")
            interrupt = InterruptResponse(type="confirmation", thread_id=result.thread_id, prompt=result.content)

        citations = [
            CitationResponse(chunk_id=c.chunk_id, document_id=c.document_id, source_title=c.source_title, section=c.section) for c in result.citations
        ]

        content = result.content
        if safety and safety.action == "allow_with_boundary" and safety.user_message:
            content = f"{content}\n\n---\n\n{safety.user_message}"

        return ChatResponse(
            session_id=result.session_id,
            status=api_status,
            content=content,
            used_intents=used_intents,
            citations=tuple(citations),
            required_input=required_input,
            interrupt=interrupt,
            safety=safety,
            facts=result.facts,
        )
