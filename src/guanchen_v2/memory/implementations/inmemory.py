from guanchen_v2.core.session.models import ConversationState
from guanchen_v2.memory.exceptions import (
    MemoryAlreadyExistsError,
    MemoryNotFoundError,
)
from guanchen_v2.memory.store import MemoryStore


class InMemoryMemoryStore(MemoryStore):
    """
    第一版基于内存的 Store，仅用于验证 Contract 与测试。
    """

    def __init__(self) -> None:
        # 使用 JSON 字符串存储，强制切断内存对象引用 (State Identity)，验证 Value Equality
        self._data: dict[str, str] = {}

    async def save(self, state: ConversationState) -> None:
        if state.session_id in self._data:
            raise MemoryAlreadyExistsError(f"Session {state.session_id} 已经存在，无法重复 save。")
        
        self._data[state.session_id] = state.model_dump_json()

    async def load(self, session_id: str) -> ConversationState | None:
        json_data = self._data.get(session_id)
        if json_data is None:
            return None
            
        return ConversationState.model_validate_json(json_data)

    async def update(self, state: ConversationState) -> None:
        if state.session_id not in self._data:
            raise MemoryNotFoundError(f"Session {state.session_id} 不存在，无法 update。")
            
        self._data[state.session_id] = state.model_dump_json()

    async def delete(self, session_id: str) -> None:
        # 幂等操作：存在则删除，不存在也返回成功
        self._data.pop(session_id, None)

