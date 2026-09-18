"""Stage 8 Memory Selector：按领域选择长期记忆，实现 namespace / domain 隔离。

设计约束（冻结规划）：
- 八字只读取 BirthProfile + 相关近期对话；
- 解梦读取当前 DreamRecord（由 DreamAgentRuntime.record_store 在运行时维护）；
- 六爻读取当前 DecisionRecord（由 LiuyaoAgentAdapter.record_store 在运行时维护）；
- 建立 Memory namespace / domain 隔离，防止梦境上下文污染八字分析；
- Memory Selector 不把全历史无脑塞给模型。
"""
from typing import Protocol

from sqlalchemy.ext.asyncio import async_sessionmaker

from guanchen_v2.memory.repositories import (
    BirthProfileRepository,
    DecisionRecordRepository,
    DreamRecordRepository,
    UserProfileRepository,
)
from guanchen_v2.models.bazi import BirthProfile
from guanchen_v2.models.dream import DreamRecord
from guanchen_v2.models.liuyao import DecisionQuestionStatus, DecisionRecord
from guanchen_v2.router.contracts import IntentType, RequiredDataType
from guanchen_v2.router.requirements import RequirementContext

_PENDING_QUESTION_STATUSES = {
    DecisionQuestionStatus.DRAFT,
    DecisionQuestionStatus.NEEDS_CLARIFICATION,
    DecisionQuestionStatus.PENDING_CONFIRMATION,
}


class MemoryPersistence(Protocol):
    """领域记忆持久化的最小契约（供运行时代入）。"""

    async def load_latest(self) -> object | None: ...

    async def save(self, record: object) -> None: ...


class MemorySelector:
    """
    长期记忆的领域选择器。

    每个 intent 只能看到自己命名空间内的数据：
    - BAZI       -> BirthProfile（唯一长期用户事实）
    - DREAM      -> 运行时由 DreamRecordStore 维护，选择器不注入上下文
    - LIUYAO     -> 运行时由 DecisionRecordStore / checkpointer 维护
    - KNOWLEDGE  -> 无需用户记忆
    """

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory
        self._user_repo = UserProfileRepository(session_factory)
        self._birth_repo = BirthProfileRepository(session_factory)
        self._dream_repo = DreamRecordRepository(session_factory)
        self._decision_repo = DecisionRecordRepository(session_factory)

    async def ensure_user(self, user_id: str) -> None:
        """幂等建立匿名用户主体。"""
        await self._user_repo.get_or_create(user_id)

    async def select_for_intent(
        self,
        intent: IntentType,
        user_id: str,
    ) -> RequirementContext:
        """
        按领域选择本次请求应注入的长期记忆。

        领域隔离在这里被结构性保证：每个分支只读取自己的 repository，
        梦境 / 六爻数据永远不会出现在 Bazi 的 context 中。
        """
        if intent == IntentType.BAZI:
            profile = await self._birth_repo.get(user_id)
            if profile is not None:
                return RequirementContext(
                    available_data={RequiredDataType.BIRTH_PROFILE: profile}
                )
            return RequirementContext(available_data={})

        if intent == IntentType.LIUYAO:
            # 六爻读取当前 DecisionRecord：仅当存在未完成的决策（中断 / 待确认）
            # 时注入问题种子，使恢复流程无需用户重新提供问题。
            record = await self._decision_repo.get_latest(user_id)
            if record is not None and record.question.status in _PENDING_QUESTION_STATUSES:
                seed = (
                    record.question.clarified_question
                    or record.question.original_question
                )
                if seed:
                    return RequirementContext(
                        available_data={RequiredDataType.DECISION_QUESTION: seed}
                    )
            return RequirementContext(available_data={})

        # DREAM / KNOWLEDGE / CHITCHAT / OUT_OF_SCOPE：
        # 当前轮内容来自用户本轮输入，不注入历史记忆到 requirement context。
        # （解梦的当前 DreamRecord 由 DreamAgentRuntime.record_store 在运行时维护）
        return RequirementContext(available_data={})

    async def persist_birth_profile(
        self,
        user_id: str,
        profile: BirthProfile,
    ) -> None:
        """用户明确提供 / 更正后的出生资料写入长期记忆。"""
        await self._birth_repo.upsert(user_id, profile)

    async def persist_decision_record(
        self,
        user_id: str,
        record: DecisionRecord,
    ) -> None:
        """六爻决策记录写入长期记忆（用户明确提供 / 确认后）。"""
        await self._decision_repo.save(user_id, record)

    async def load_birth_profile(self, user_id: str) -> BirthProfile | None:
        return await self._birth_repo.get(user_id)

    async def load_dream_memory(self, user_id: str) -> DreamRecord | None:
        """解梦域当前 DreamRecord（供 DreamAgentRuntime 恢复 / 测试核验）。"""
        return await self._dream_repo.get_latest(user_id)

    async def load_decision_memory(self, user_id: str) -> DecisionRecord | None:
        """六爻域当前 DecisionRecord（供恢复 / 测试核验）。"""
        return await self._decision_repo.get_latest(user_id)
