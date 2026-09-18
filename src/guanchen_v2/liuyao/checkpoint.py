import uuid
from typing import Any

from guanchen_v2.liuyao.exceptions import LiuyaoCheckpointError


class LiuyaoCheckpointManager:
    """负责将 LangGraph 的 Thread Reference 同步到 Application Session State"""

    @staticmethod
    def get_or_create_thread(agent_state: dict[str, Any]) -> str:
        """从状态中获取当前 Thread ID，如果不存在则自动创建一个新的以隔离流程"""
        if not isinstance(agent_state, dict):
            raise LiuyaoCheckpointError("非法的 agent_state 容器类型。")
            
        if "thread_id" not in agent_state:
            agent_state["thread_id"] = f"liuyao_thread_{uuid.uuid4().hex}"
            agent_state.pop("status", None)
            agent_state.pop("pending_node", None)
        return agent_state["thread_id"]

    @staticmethod
    def save_checkpoint_reference(
        agent_state: dict[str, Any],
        thread_id: str,
        status: str,
        pending_node: str | None = None
    ) -> None:
        """更新工作流恢复所需的核心 metadata"""
        agent_state["thread_id"] = thread_id
        agent_state["status"] = status
        
        if pending_node:
            agent_state["pending_node"] = pending_node
        elif "pending_node" in agent_state:
            del agent_state["pending_node"]

    @staticmethod
    def get_thread_id(agent_state: dict[str, Any]) -> str | None:
        return agent_state.get("thread_id")

