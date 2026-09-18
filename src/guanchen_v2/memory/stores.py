"""Stage 8 领域记忆 Store：绑定到具体 user 的持久化适配。

这些 Store 只做“按用户读写领域记录”，不包含业务判断。
DreamAgentRuntime / LiuyaoAgentAdapter 通过它们获得跨进程可恢复的领域记忆。
"""
from sqlalchemy.ext.asyncio import async_sessionmaker

from guanchen_v2.memory.repositories import (
    DecisionRecordRepository,
    DreamRecordRepository,
)
from guanchen_v2.models.dream import DreamRecord
from guanchen_v2.models.liuyao import DecisionRecord


class PostgresDreamRecordStore:
    """解梦域：按 user 读写当前 DreamRecord。"""

    def __init__(
        self,
        user_id: str,
        session_factory: async_sessionmaker,
    ) -> None:
        self._user_id = user_id
        self._repo = DreamRecordRepository(session_factory)

    async def load_latest(self) -> DreamRecord | None:
        return await self._repo.get_latest(self._user_id)

    async def save(self, record: DreamRecord) -> None:
        await self._repo.save(self._user_id, record)


class PostgresDecisionRecordStore:
    """六爻决策域：按 user 读写当前 DecisionRecord。"""

    def __init__(
        self,
        user_id: str,
        session_factory: async_sessionmaker,
    ) -> None:
        self._user_id = user_id
        self._repo = DecisionRecordRepository(session_factory)

    async def load_latest(self) -> DecisionRecord | None:
        return await self._repo.get_latest(self._user_id)

    async def save(self, record: DecisionRecord) -> None:
        await self._repo.save(self._user_id, record)
