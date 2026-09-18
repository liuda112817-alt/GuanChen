import json
import uuid

from guanchen_v2.application.exceptions import (
    ConversationExecutionError,
    SessionInitializationError,
    StateUpdateError,
)
from guanchen_v2.core.session.models import ConversationState, MessageState
from guanchen_v2.memory.selector import MemorySelector
from guanchen_v2.memory.store import MemoryStore
from guanchen_v2.router.contracts import IntentType, RequiredDataType
from guanchen_v2.router.core import TwoLayerIntentRouter
from guanchen_v2.router.dispatch import SingleAgentDispatcher
from guanchen_v2.router.dual_dispatch import AgentExecutionResult, DualDomainDispatcher
from guanchen_v2.router.dual_requirements import check_dual_requirements
from guanchen_v2.router.requirements import RequirementContext, RequirementStatus, check_requirements
from guanchen_v2.router.synthesis import SynthesisInput, SynthesizedResponse
from guanchen_v2.router.synthesizer import AgentSynthesizer


class ConversationOrchestrator:
    def __init__(
        self,
        memory_store: MemoryStore,
        router: TwoLayerIntentRouter,
        single_dispatcher: SingleAgentDispatcher,
        dual_dispatcher: DualDomainDispatcher,
        synthesizer: AgentSynthesizer,
        memory_selector: MemorySelector | None = None,
    ):
        self._memory_store = memory_store
        self._router = router
        self._single_dispatcher = single_dispatcher
        self._dual_dispatcher = dual_dispatcher
        self._synthesizer = synthesizer
        self._memory_selector = memory_selector

    async def execute(self, session_id: str | None, user_query: str) -> SynthesizedResponse:
        # 1. Session Lifecycle Initialization
        try:
            if session_id:
                state = await self._memory_store.load(session_id)
                if not state:
                    # 不存在则默认自然创建，保证用户体验
                    state = ConversationState(session_id=session_id)
                    await self._memory_store.save(state)
            else:
                session_id = str(uuid.uuid4())
                state = ConversationState(session_id=session_id)
                await self._memory_store.save(state)
        except Exception as exc:
            raise SessionInitializationError(f"Session {session_id} 初始化失败。") from exc

        try:
            # 2. Append User Message
            state.current_query = user_query
            state.messages.append(MessageState(role="user", content=user_query))

            # 3. Routing
            routing_result = await self._router.route(user_query)
            state.routing_result = routing_result

            # 4. Requirement Check
            # Stage 8：通过 Memory Selector 按领域注入长期记忆（只注入当前领域命名空间），
            # 不把全历史无脑塞给模型。
            if self._memory_selector is not None:
                await self._memory_selector.ensure_user(session_id)
                req_context = await self._memory_selector.select_for_intent(
                    routing_result.primary_intent,
                    session_id,
                )
            else:
                req_context = RequirementContext(available_data={})

            if routing_result.secondary_intents:
                req_result = check_dual_requirements(routing_result, req_context)
            else:
                req_result = check_requirements(routing_result, req_context)
            
            state.requirement_result = req_result

            # 5. Dispatching 调度
            if req_result.status in {RequirementStatus.NEEDS_INPUT, RequirementStatus.BYPASS}:
                results = (AgentExecutionResult(intent=routing_result.primary_intent, output=req_result),)
            else:
                if routing_result.secondary_intents:
                    primary_state = getattr(state.agent_states, routing_result.primary_intent.value, {})
                    secondary_state = getattr(state.agent_states, routing_result.secondary_intents[0].value, {})
                    results = await self._dual_dispatcher.dispatch(
                        routing_result, user_query, req_context, primary_state, secondary_state
                    )
                else:
                    agent_state = getattr(state.agent_states, routing_result.primary_intent.value, {})
                    out = await self._single_dispatcher.dispatch(
                        routing_result, req_result, user_query, req_context, agent_state
                    )
                    results = (AgentExecutionResult(intent=routing_result.primary_intent, output=out),)

        except Exception as exc:
            raise ConversationExecutionError("Orchestrator 调度执行期间发生系统错误。") from exc

        # 7. Memory Write（仅写入用户明确提供 / 确认的结构化资料）
        # 八字执行成功后，将本次使用的出生资料持久化为长期记忆，
        # 使后续轮次 / 重启后无需重复询问。
        if (
            self._memory_selector is not None
            and routing_result.primary_intent == IntentType.BAZI
        ):
            profile = req_context.available_data.get(RequiredDataType.BIRTH_PROFILE)
            if profile is not None:
                await self._memory_selector.persist_birth_profile(session_id, profile)

        # 8. Update Agent States (在不知道领域结构的前提下防御性注入)
        try:
            self._update_agent_states(state, results)
        except Exception as exc:
            raise StateUpdateError("更新 Agent State 时发生数据错误。") from exc

        # 9. Synthesis
        try:
            synth_input = SynthesisInput(query=user_query, results=results)
            synth_response = await self._synthesizer.synthesize(synth_input)

            # 10. Append Assistant Message
            state.messages.append(MessageState(role="assistant", content=synth_response.content))
        except Exception as exc:
            raise ConversationExecutionError("Synthesizer 合并响应执行失败。") from exc

        # 11. Persistence
        try:
            await self._memory_store.update(state)
        except Exception as exc:
            raise StateUpdateError("最终持久化 ConversationState 失败。") from exc

        return synth_response

    def _update_agent_states(self, state: ConversationState, results: tuple[AgentExecutionResult, ...]) -> None:
        """安全更新 Agent State，不探查 Agent 内部字段，不违反 Runtime Object Rule"""
        for res in results:
            intent_val = res.intent.value
            agent_dict = getattr(state.agent_states, intent_val, None)
            
            if agent_dict is not None:
                try:
                    if hasattr(res.output, "model_dump_json"):
                        agent_dict["latest_output"] = json.loads(res.output.model_dump_json())
                    elif isinstance(res.output, dict):
                        agent_dict["latest_output"] = json.loads(json.dumps(res.output))
                    else:
                        agent_dict["latest_output"] = str(res.output)
                except Exception:
                    agent_dict["latest_output"] = "Unserializable output representation"

