from typing import Protocol

from guanchen_v2.core.session.models import ConversationState


class MemoryStore(Protocol):
    """
    Session State 的持久化抽象层。
    只负责 CRUD，不理解业务，不修改状态数据。
    """

    async def save(self, state: ConversationState) -> None:
        """
        持久化一个新的 Session State。
        如果 session_id 已存在，必须抛出 MemoryAlreadyExistsError 以防止覆盖。
        """
        ...

    async def load(self, session_id: str) -> ConversationState | None:
        """
        加载指定的 Session State。
        如果不存在，返回 None，而不抛出异常。
        """
        ...

    async def update(self, state: ConversationState) -> None:
        """
        更新已存在的 Session State。
        如果 session_id 不存在，必须抛出 MemoryNotFoundError。
        """
        ...

    async def delete(self, session_id: str) -> None:
        """
        删除指定的 Session State。
        操作应具备幂等性 (Idempotent)，如果不存在则静默成功，不报错。
        """
        ...

