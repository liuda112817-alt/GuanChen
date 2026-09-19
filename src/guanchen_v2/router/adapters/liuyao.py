import json
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from langgraph.types import Command

from guanchen_v2.liuyao.checkpoint import LiuyaoCheckpointManager
from guanchen_v2.liuyao.policy import ConfirmationResponse
from guanchen_v2.liuyao.state import create_initial_liuyao_state
from guanchen_v2.liuyao.workflow import LiuyaoAgentRuntime
from guanchen_v2.models.liuyao import DecisionQuestionStatus, DecisionRecord
from guanchen_v2.observability.decorators import trace
from guanchen_v2.router.contracts import RequiredDataType
from guanchen_v2.router.errors import RouterDispatchError
from guanchen_v2.router.requirements import RequirementContext


@dataclass(frozen=True)
class LiuyaoInvocationResult:
    thread_id: str
    output: object


class LiuyaoAgentAdapter:
    def __init__(
        self,
        runtime: LiuyaoAgentRuntime,
        record_store: Any | None = None,
    ) -> None:
        self._graph = runtime.build_graph()
        self._record_store = record_store

    async def _persist_decision_record(
        self,
        thread_id: str,
        state_snapshot: Any,
    ) -> None:
        """将当前六爻决策状态持久化为 DecisionRecord（Stage 8 长期记忆）。"""
        if self._record_store is None:
            return

        values = state_snapshot.values if state_snapshot is not None else {}
        question = values.get("question")
        if question is None:
            return

        record = DecisionRecord(
            record_id=uuid5(NAMESPACE_URL, "guanchen:decision:" + thread_id),
            question=question,
            thread_id=thread_id,
            status=question.status,
            hexagram=values.get("hexagram"),
            reflection=values.get("reflection"),
            final_response=values.get("final_response"),
        )
        await self._record_store.save(record)

    async def resume(
        self,
        thread_id: str,
        payload: dict[str, Any],
    ) -> object:
        """
        基于外部截获的 thread_id 与 HITL payload 接力恢复执行。

        供前端 / 外部系统在拿到 LiuyaoInvocationResult.thread_id 后，
        跨进程、跨会话继续同一 LangGraph 线程。
        """
        validated = ConfirmationResponse.model_validate(payload)
        config = {"configurable": {"thread_id": thread_id}}
        output = await self._graph.ainvoke(Command(resume=validated.model_dump(exclude_none=True)), config)
        snapshot = await self._graph.aget_state(config)
        await self._persist_decision_record(thread_id, snapshot)
        return output

    @trace("liuyao", "AGENT")
    async def invoke(self, query: str, context: RequirementContext, agent_state: dict[str, Any] | None = None) -> LiuyaoInvocationResult:
        if agent_state is None:
            agent_state = {}

        # A completed decision starts a new thread; never overwrite its checkpoint.
        if agent_state.get("status") == "COMPLETED":
            agent_state.pop("thread_id", None)
        # 1. 恢复或生成 LangGraph Thread
        thread_id = LiuyaoCheckpointManager.get_or_create_thread(agent_state)
        status = agent_state.get("status")

        config = {"configurable": {"thread_id": thread_id}}

        # 2. 判断当前生命周期阶段
        if status == "WAITING_INPUT":
            snapshot = await self._graph.aget_state(config)
            continued = dict(snapshot.values)
            continued["pending_user_input"] = query
            output = await self._graph.ainvoke(continued, config)
        elif status == "INTERRUPTED":
            # 这是一个挂起后的继续执行（Resume 流程）
            try:
                payload = json.loads(query)
            except ValueError:
                # 后备机制：尝试处理基于文本的用户确认 (如果前端还没对接 JSON)
                text = query.strip()
                if text.lower() in ("确认", "确认起卦", "confirm", "yes", "y"):
                    payload = {"action": "confirm"}
                elif "取消" in text or text.lower() in ("不确认", "暂不确认", "cancel", "no", "n"):
                    payload = {"action": "cancel"}
                else:
                    payload = {"action": "modify", "modification": text}

            validated = ConfirmationResponse.model_validate(payload)
            output = await self._graph.ainvoke(Command(resume=validated.model_dump(exclude_none=True)), config)
        else:
            # 全新执行
            seed = context.available_data.get(RequiredDataType.DECISION_QUESTION)
            if seed is None:
                raise RouterDispatchError("LiuyaoAgentAdapter 缺少已声明可用的 DECISION_QUESTION")
            if not isinstance(seed, str) or not seed.strip():
                raise RouterDispatchError("DECISION_QUESTION 必须为非空字符串")

            initial_state = create_initial_liuyao_state(seed)
            output = await self._graph.ainvoke(initial_state, config)

        # 3. 计算最新的 LangGraph 中断状态并更新回 ConversationState Namespace
        state_snapshot = await self._graph.aget_state(config)
        if state_snapshot and state_snapshot.next:
            new_status = "INTERRUPTED"
            pending_node = state_snapshot.next[0]
        elif (
            state_snapshot
            and isinstance(state_snapshot.values, dict)
            and getattr(state_snapshot.values.get("question"), "status", None) == DecisionQuestionStatus.NEEDS_CLARIFICATION
        ):
            new_status = "WAITING_INPUT"
            pending_node = "clarify"
        else:
            new_status = "COMPLETED"
            pending_node = None

        LiuyaoCheckpointManager.save_checkpoint_reference(agent_state, thread_id, new_status, pending_node)

        # 4. 持久化决策记录（含中断态），供跨进程恢复
        await self._persist_decision_record(thread_id, state_snapshot)

        return LiuyaoInvocationResult(
            thread_id=thread_id,
            output=output,
        )
