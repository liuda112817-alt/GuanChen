import json
import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from guanchen_v2.agents.bazi.models import BaziAgentInput, BaziBirthDataPatch, ReadyForBazi
from guanchen_v2.agents.bazi.requirements import check_bazi_requirements
from guanchen_v2.application.exceptions import ConversationExecutionError, SessionInitializationError, StateUpdateError
from guanchen_v2.core.session.models import ConversationState, MessageState, PendingInterrupt
from guanchen_v2.router.contracts import IntentType, RequiredDataType
from guanchen_v2.router.core import HighPrecisionRuleRouter, RouterDecision, TwoLayerIntentRouter, build_routing_result
from guanchen_v2.router.dual_dispatch import AgentExecutionResult
from guanchen_v2.router.dual_requirements import check_dual_requirements
from guanchen_v2.router.requirements import RequirementContext, RequirementStatus, check_requirements
from guanchen_v2.router.synthesis import SynthesisInput, SynthesizedResponse


class TurnState(TypedDict, total=False):
    conversation: ConversationState
    query: str
    task_query: str
    birth_patch: BaziBirthDataPatch | None
    new_task: bool
    context: RequirementContext
    results: tuple[AgentExecutionResult, ...]
    response: SynthesizedResponse


class ConversationOrchestrator:
    """Bounded ConversationGraph; only domain state survives between turns."""

    def __init__(self, memory_store, router, single_dispatcher, dual_dispatcher, synthesizer, memory_selector=None):
        self._memory_store = memory_store
        self._router = router
        self._single_dispatcher = single_dispatcher
        self._dual_dispatcher = dual_dispatcher
        self._synthesizer = synthesizer
        self._memory_selector = memory_selector
        builder = StateGraph(TurnState)
        nodes = [
            ("route", self._route),
            ("requirements", self._requirements),
            ("agents", self._agents),
            ("response", self._response),
            ("persist", self._persist),
        ]
        previous = START
        for name, node in nodes:
            builder.add_node(name, node)
            builder.add_edge(previous, name)
            previous = name
        builder.add_edge(previous, END)
        self.graph = builder.compile()

    async def execute(
        self, session_id: str | None, user_query: str, *, birth_patch: BaziBirthDataPatch | dict | None = None, new_task: bool = False
    ) -> SynthesizedResponse:
        if not user_query.strip():
            raise ValueError("用户输入不能为空")
        patch = BaziBirthDataPatch.model_validate(birth_patch) if birth_patch is not None else None
        session_id = session_id or str(uuid.uuid4())
        try:
            state = await self._memory_store.load(session_id)
            if state is None:
                state = ConversationState(session_id=session_id)
                await self._memory_store.save(state)
        except Exception as exc:
            raise SessionInitializationError("会话初始化失败") from exc
        state.current_query = user_query
        state.messages.append(MessageState(role="user", content=user_query))
        try:
            result = await self.graph.ainvoke(
                {"conversation": state, "query": user_query, "birth_patch": patch, "new_task": new_task},
                {"recursion_limit": 8},
            )
            return result["response"]
        except (StateUpdateError, ConversationExecutionError):
            raise
        except Exception as exc:
            raise ConversationExecutionError("Orchestrator 调度执行期间发生系统错误。") from exc

    async def _route(self, turn: TurnState) -> dict:
        state, query = turn["conversation"], turn["query"]
        previous = state.routing_result
        explicit = HighPrecisionRuleRouter().match(query)
        continuing = (
            previous is not None
            and not turn["new_task"]
            and (
                (turn["birth_patch"] is not None and state.pending_query is not None)
                or (explicit is None and (state.pending_interrupt is not None or state.pending_query is not None))
                or (explicit is None and query.strip() in {"然后呢", "然后呢？", "继续", "再讲细一点"})
            )
        )
        if continuing and state.pending_interrupt is not None:
            # Resume only the waiting workflow, not every Agent from its original dual route.
            routing = build_routing_result(RouterDecision(primary_intent=IntentType.LIUYAO, confidence=1, reason="继续待确认任务"))
        elif continuing:
            routing = previous
        elif explicit is not None and isinstance(self._router, TwoLayerIntentRouter):
            routing = build_routing_result(explicit)
        else:
            routing = await self._router.route(query)
        task_query = state.pending_query if continuing and state.pending_query else query
        if continuing and routing.primary_intent in {IntentType.BAZI, IntentType.KNOWLEDGE} and not state.pending_query:
            prior = getattr(state.agent_states, routing.primary_intent.value).get("task_query")
            if prior:
                task_query = prior
        if turn["new_task"]:
            state.agent_states.liuyao.clear()
        if not continuing:
            state.pending_query = None
            state.pending_interrupt = None
        state.routing_result = routing
        return {"conversation": state, "task_query": task_query}

    async def _requirements(self, turn: TurnState) -> dict:
        state = turn["conversation"]
        routing = state.routing_result
        intents = (routing.primary_intent, *routing.secondary_intents)
        available: dict[RequiredDataType, Any] = {}
        if self._memory_selector is not None:
            await self._memory_selector.ensure_user(state.session_id)
            for intent in intents:
                selected = await self._memory_selector.select_for_intent(intent, state.session_id)
                available.update(selected.available_data)
        if IntentType.DREAM in intents:
            available[RequiredDataType.DREAM_CONTENT] = turn["task_query"] if turn["birth_patch"] is not None else turn["query"]
        if IntentType.LIUYAO in intents:
            if state.agent_states.liuyao.get("status") in {"INTERRUPTED", "WAITING_INPUT"}:
                available.setdefault(RequiredDataType.DECISION_QUESTION, "继续当前决策")
            if turn["query"].strip().lower() not in {"确认", "取消", "confirm", "cancel", "yes", "no"}:
                available[RequiredDataType.DECISION_QUESTION] = turn["query"]
        if IntentType.BAZI in intents:
            stored = available.get(RequiredDataType.BIRTH_PROFILE)
            fields = dict(state.birth_data)
            if stored is not None:
                fields.update({key: value for key, value in stored.model_dump().items() if key in BaziBirthDataPatch.model_fields})
                if state.pending_query and state.requirement_result and state.requirement_result.status == RequirementStatus.NEEDS_INPUT:
                    fields.update(state.birth_data)
            if turn["birth_patch"] is not None:
                fields.update(turn["birth_patch"].model_dump(exclude_unset=True))
            fields = {key: value for key, value in fields.items() if key in BaziBirthDataPatch.model_fields}
            state.birth_data = fields
            checked = check_bazi_requirements(BaziAgentInput(question=turn["task_query"], **fields))
            if isinstance(checked, ReadyForBazi):
                available[RequiredDataType.BIRTH_PROFILE] = checked.profile
            else:
                available.pop(RequiredDataType.BIRTH_PROFILE, None)
                state.agent_states.bazi["input_requirement"] = checked.model_dump(mode="json")
        context = RequirementContext(available_data=available)
        state.requirement_result = check_dual_requirements(routing, context) if routing.secondary_intents else check_requirements(routing, context)
        if state.requirement_result.status == RequirementStatus.NEEDS_INPUT:
            state.pending_query = turn["task_query"]
        return {"conversation": state, "context": context}

    async def _agents(self, turn: TurnState) -> dict:
        state, context = turn["conversation"], turn["context"]
        routing, requirement = state.routing_result, state.requirement_result
        if requirement.status != RequirementStatus.READY:
            results = (AgentExecutionResult(intent=routing.primary_intent, output=requirement),)
        elif routing.secondary_intents:
            results = await self._dual_dispatcher.dispatch(
                routing,
                turn["task_query"],
                context,
                getattr(state.agent_states, routing.primary_intent.value),
                getattr(state.agent_states, routing.secondary_intents[0].value),
            )
        else:
            output = await self._single_dispatcher.dispatch(
                routing,
                requirement,
                turn["task_query"] if routing.primary_intent in {IntentType.BAZI, IntentType.KNOWLEDGE} else turn["query"],
                context,
                getattr(state.agent_states, routing.primary_intent.value, {}),
            )
            results = (AgentExecutionResult(intent=routing.primary_intent, output=output),)
        if requirement.status == RequirementStatus.READY:
            state.pending_query = None
        self._update_agent_states(state, results)
        if requirement.status == RequirementStatus.READY:
            for item in results:
                getattr(state.agent_states, item.intent.value)["task_query"] = turn["task_query"]
        liuyao = state.agent_states.liuyao
        if any(item.intent == IntentType.LIUYAO for item in results) and liuyao.get("status") in {"INTERRUPTED", "WAITING_INPUT"}:
            state.pending_interrupt = PendingInterrupt(agent="liuyao", interrupt_type=liuyao["status"], payload={"thread_id": liuyao["thread_id"]})
        elif routing.primary_intent == IntentType.LIUYAO:
            state.pending_interrupt = None
        for item in results:
            if item.intent == IntentType.DREAM and requirement.status == RequirementStatus.READY:
                state.pending_query = turn["task_query"]
        return {"conversation": state, "results": results}

    async def _response(self, turn: TurnState) -> dict:
        response = await self._synthesizer.synthesize(SynthesisInput(query=turn["query"], results=turn["results"]))
        state = turn["conversation"]
        if (
            state.requirement_result.status == RequirementStatus.NEEDS_INPUT
            and RequiredDataType.BIRTH_PROFILE in state.requirement_result.missing_data
            and "input_requirement" in state.agent_states.bazi
        ):
            need = state.agent_states.bazi["input_requirement"]
            fields = need.get("missing_fields", [])
            content = ("请补充出生资料：" + "、".join(fields)) if fields else need.get("reason", response.content)
            response = response.model_copy(update={"content": content, "status": "needs_input"})
        response = response.model_copy(update={"session_id": state.session_id})
        state.messages.append(MessageState(role="assistant", content=response.content))
        return {"conversation": state, "response": response}

    async def _persist(self, turn: TurnState) -> dict:
        state, context = turn["conversation"], turn["context"]
        try:
            profile = context.available_data.get(RequiredDataType.BIRTH_PROFILE)
            if self._memory_selector is not None and profile is not None and turn["birth_patch"] is not None:
                await self._memory_selector.persist_birth_profile(state.session_id, profile)
            await self._memory_store.update(state)
        except Exception as exc:
            raise StateUpdateError("最终持久化 ConversationState 失败。") from exc
        return {}

    def _update_agent_states(self, state: ConversationState, results: tuple[AgentExecutionResult, ...]) -> None:
        for result in results:
            target = getattr(state.agent_states, result.intent.value, None)
            if target is None:
                continue
            if hasattr(result.output, "model_dump_json"):
                target["latest_output"] = json.loads(result.output.model_dump_json())
            elif isinstance(result.output, dict):
                target["latest_output"] = json.loads(json.dumps(result.output))
