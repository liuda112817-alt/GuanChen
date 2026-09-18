"""Stage 8 长期用户资料 Repository 层。

设计约束（冻结规划）：
- 只为真实持久化需求创建 repository，不做抽象接口层套娃；
- 只保存“用户明确提供 / 确认”的结构化资料；
- 后写的明确更正覆盖当前有效事实（upsert），并保留 updated_at。
"""
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from guanchen_v2.core.session.models import MessageState
from guanchen_v2.memory.exceptions import MemoryPersistenceError
from guanchen_v2.memory.models import (
    BirthProfileRow,
    ConversationRow,
    DecisionRecordRow,
    DreamRecordRow,
    MessageRow,
    UserProfileRow,
)
from guanchen_v2.models.bazi import BirthProfile, Gender
from guanchen_v2.models.dream import DreamRecord
from guanchen_v2.models.liuyao import DecisionRecord


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UserProfileRepository:
    """用户主体的幂等创建 / 查询。"""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def get_or_create(self, user_id: str) -> UserProfileRow:
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(UserProfileRow).where(UserProfileRow.user_id == user_id)
                )
                row = result.scalar_one_or_none()
                if row is not None:
                    return row

                row = UserProfileRow(user_id=user_id)
                session.add(row)
                await session.commit()
                return row
        except Exception as exc:
            raise MemoryPersistenceError("用户档案写入失败") from exc


async def _ensure_user_async(
    session_factory: async_sessionmaker,
    user_id: str,
) -> None:
    """写入用户域数据前，确保 FK 父行 user_profile 存在（幂等）。"""
    user_repo = UserProfileRepository(session_factory)
    await user_repo.get_or_create(user_id)


class BirthProfileRepository:
    """出生资料：当前唯一有效事实 + 用户更正语义。"""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _row_to_domain(row: BirthProfileRow) -> BirthProfile:
        return BirthProfile(
            year=row.year,
            month=row.month,
            day=row.day,
            hour=row.hour,
            minute=row.minute,
            gender=Gender(row.gender),
            birth_place_text=row.birth_place_text,
        )

    async def get(self, user_id: str) -> BirthProfile | None:
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(BirthProfileRow).where(BirthProfileRow.user_id == user_id)
                )
                row = result.scalar_one_or_none()
                if row is None:
                    return None
                return self._row_to_domain(row)
        except Exception as exc:
            raise MemoryPersistenceError("出生资料读取失败") from exc

    async def upsert(self, user_id: str, profile: BirthProfile) -> None:
        """
        用户更正语义：存在则覆盖为最新事实，不存在则创建。
        单用户单行（唯一约束），刷新 updated_at。
        """
        now = _now()
        try:
            await _ensure_user_async(self._session_factory, user_id)
            async with self._session_factory() as session:
                result = await session.execute(
                    select(BirthProfileRow).where(BirthProfileRow.user_id == user_id)
                )
                row = result.scalar_one_or_none()

                if row is None:
                    row = BirthProfileRow(
                        user_id=user_id,
                        year=profile.year,
                        month=profile.month,
                        day=profile.day,
                        hour=profile.hour,
                        minute=profile.minute,
                        gender=profile.gender.value,
                        birth_place_text=profile.birth_place_text,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(row)
                else:
                    row.year = profile.year
                    row.month = profile.month
                    row.day = profile.day
                    row.hour = profile.hour
                    row.minute = profile.minute
                    row.gender = profile.gender.value
                    row.birth_place_text = profile.birth_place_text
                    row.updated_at = now

                await session.commit()
        except Exception as exc:
            raise MemoryPersistenceError("出生资料写入失败") from exc

    async def delete(self, user_id: str) -> None:
        """幂等删除，用于测试隔离 / 用户主动清除资料。"""
        try:
            async with self._session_factory() as session:
                await session.execute(
                    delete(BirthProfileRow).where(BirthProfileRow.user_id == user_id)
                )
                await session.commit()
        except Exception as exc:
            raise MemoryPersistenceError("出生资料删除失败") from exc


class ConversationRepository:
    """会话与消息的追加式持久化。"""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def create(self, conversation_id: str, user_id: str) -> None:
        try:
            await _ensure_user_async(self._session_factory, user_id)
            async with self._session_factory() as session:
                existing = await session.execute(
                    select(ConversationRow).where(
                        ConversationRow.conversation_id == conversation_id
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    return

                session.add(
                    ConversationRow(
                        conversation_id=conversation_id,
                        user_id=user_id,
                    )
                )
                await session.commit()
        except Exception as exc:
            raise MemoryPersistenceError("会话创建失败") from exc

    async def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
    ) -> None:
        if role not in {"user", "assistant", "system"}:
            raise ValueError("Message role 必须是 user, assistant 或 system")

        try:
            async with self._session_factory() as session:
                session.add(
                    MessageRow(
                        conversation_id=conversation_id,
                        role=role,
                        content=content,
                    )
                )
                await session.commit()
        except Exception as exc:
            raise MemoryPersistenceError("消息写入失败") from exc

    async def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = 20,
    ) -> list[MessageState]:
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(MessageRow)
                    .where(MessageRow.conversation_id == conversation_id)
                    .order_by(MessageRow.created_at.asc(), MessageRow.message_id.asc())
                    .limit(limit)
                )
                rows = result.scalars().all()

            return [
                MessageState(
                    role=row.role,
                    content=row.content,
                    timestamp=row.created_at,
                )
                for row in rows
            ]
        except Exception as exc:
            raise MemoryPersistenceError("会话消息读取失败") from exc


class DreamRecordRepository:
    """解梦域当前 DreamRecord 的保存 / 读取（按 user 取最新）。"""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def save(self, user_id: str, record: DreamRecord) -> None:
        try:
            now = _now()
            await _ensure_user_async(self._session_factory, user_id)
            async with self._session_factory() as session:
                result = await session.execute(
                    select(DreamRecordRow).where(
                        DreamRecordRow.record_id == str(record.dream_id)
                    )
                )
                row = result.scalar_one_or_none()

                if row is None:
                    session.add(
                        DreamRecordRow(
                            record_id=str(record.dream_id),
                            user_id=user_id,
                            record_json=record.model_dump_json(),
                            created_at=now,
                            updated_at=now,
                        )
                    )
                else:
                    row.record_json = record.model_dump_json()
                    row.updated_at = now

                await session.commit()
        except Exception as exc:
            raise MemoryPersistenceError("梦境记录写入失败") from exc

    async def get_latest(self, user_id: str) -> DreamRecord | None:
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(DreamRecordRow)
                    .where(DreamRecordRow.user_id == user_id)
                    .order_by(
                        DreamRecordRow.updated_at.desc(),
                        DreamRecordRow.created_at.desc(),
                    )
                    .limit(1)
                )
                row = result.scalar_one_or_none()
                if row is None:
                    return None
                return DreamRecord.model_validate_json(row.record_json)
        except Exception as exc:
            raise MemoryPersistenceError("梦境记录读取失败") from exc


class DecisionRecordRepository:
    """六爻决策域当前 DecisionRecord 的保存 / 读取（按 user 取最新）。"""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def save(self, user_id: str, record: DecisionRecord) -> None:
        try:
            now = _now()
            await _ensure_user_async(self._session_factory, user_id)
            async with self._session_factory() as session:
                result = await session.execute(
                    select(DecisionRecordRow).where(
                        DecisionRecordRow.record_id == str(record.record_id)
                    )
                )
                row = result.scalar_one_or_none()

                if row is None:
                    session.add(
                        DecisionRecordRow(
                            record_id=str(record.record_id),
                            user_id=user_id,
                            thread_id=record.thread_id,
                            record_json=record.model_dump_json(),
                            created_at=now,
                            updated_at=now,
                        )
                    )
                else:
                    row.thread_id = record.thread_id
                    row.record_json = record.model_dump_json()
                    row.updated_at = now

                await session.commit()
        except Exception as exc:
            raise MemoryPersistenceError("决策记录写入失败") from exc

    async def get_latest(self, user_id: str) -> DecisionRecord | None:
        try:
            async with self._session_factory() as session:
                result = await session.execute(
                    select(DecisionRecordRow)
                    .where(DecisionRecordRow.user_id == user_id)
                    .order_by(
                        DecisionRecordRow.updated_at.desc(),
                        DecisionRecordRow.created_at.desc(),
                    )
                    .limit(1)
                )
                row = result.scalar_one_or_none()
                if row is None:
                    return None
                return DecisionRecord.model_validate_json(row.record_json)
        except Exception as exc:
            raise MemoryPersistenceError("决策记录读取失败") from exc
