"""Stage 8 必测 3：Memory Selector 领域隔离测试。

验收点：
- DreamRecord 不出现在 Bazi Agent 的 memory context；
- Memory Selector 不把全历史无脑塞给模型；
- 每个领域只能看到自己命名空间的数据。
"""
import pytest

from guanchen_v2.memory.selector import MemorySelector
from guanchen_v2.models.bazi import BirthProfile, Gender
from guanchen_v2.models.dream import DreamRecord
from guanchen_v2.router.contracts import IntentType, RequiredDataType

pytestmark = pytest.mark.integration


def make_dream_record() -> DreamRecord:
    record = DreamRecord()
    record.raw_descriptions.append("梦见一条大蛇在追我")
    record.elements.people.append("陌生人")
    record.elements.objects.append("大蛇")
    return record


@pytest.mark.asyncio
async def test_dream_record_never_leaks_into_bazi_context(postgres_session_factory):
    """核心隔离断言：梦境数据绝不进入八字 memory context。"""
    selector = MemorySelector(postgres_session_factory)
    user_id = "user-isolation-1"

    # 1. 同一个用户同时拥有梦境记录与出生资料
    dream = make_dream_record()
    from guanchen_v2.memory.repositories import DreamRecordRepository

    await DreamRecordRepository(postgres_session_factory).save(user_id, dream)

    profile = BirthProfile(
        year=1995, month=3, day=10, hour=9, minute=0, gender=Gender.FEMALE
    )
    await selector.persist_birth_profile(user_id, profile)

    # 2. 梦境记忆确实存在（持久层可恢复）
    loaded_dream = await selector.load_dream_memory(user_id)
    assert loaded_dream is not None
    assert any("蛇" in obj for obj in loaded_dream.elements.objects)

    # 3. Bazi 的 memory context 只包含出生资料，绝无梦境内容
    bazi_context = await selector.select_for_intent(IntentType.BAZI, user_id)
    assert RequiredDataType.BIRTH_PROFILE in bazi_context.available_data
    assert len(bazi_context.available_data) == 1
    assert RequiredDataType.DREAM_CONTENT not in bazi_context.available_data
    assert "dream" not in bazi_context.available_data


@pytest.mark.asyncio
async def test_selector_does_not_inject_history_for_other_intents(postgres_session_factory):
    """Knowledge / 普通请求不注入任何用户历史记忆。"""
    selector = MemorySelector(postgres_session_factory)
    user_id = "user-isolation-2"

    profile = BirthProfile(
        year=2000, month=1, day=1, hour=12, minute=0, gender=Gender.MALE
    )
    await selector.persist_birth_profile(user_id, profile)

    knowledge_ctx = await selector.select_for_intent(IntentType.KNOWLEDGE, user_id)
    assert knowledge_ctx.available_data == {}

    dream_ctx = await selector.select_for_intent(IntentType.DREAM, user_id)
    # 当前轮梦境内容来自用户本轮输入；历史 DreamRecord 由运行时 record_store 维护
    assert dream_ctx.available_data == {}

    liuyao_ctx = await selector.select_for_intent(IntentType.LIUYAO, user_id)
    assert liuyao_ctx.available_data == {}


@pytest.mark.asyncio
async def test_bazi_memory_prefill_enables_ready_without_reask(postgres_session_factory):
    """八字长期记忆预填：已有出生资料时，Requirement Check 直接 READY（重启后无需再问）。"""
    from guanchen_v2.router.contracts import RoutingResult
    from guanchen_v2.router.requirements import RequirementStatus, check_requirements

    selector = MemorySelector(postgres_session_factory)
    user_id = "user-isolation-3"

    profile = BirthProfile(
        year=1990, month=6, day=15, hour=20, minute=30, gender=Gender.MALE
    )
    await selector.persist_birth_profile(user_id, profile)

    routing = RoutingResult(
        primary_intent=IntentType.BAZI,
        confidence=1.0,
        required_data=(RequiredDataType.BIRTH_PROFILE,),
        reason="八字测试",
    )

    context = await selector.select_for_intent(IntentType.BAZI, user_id)
    result = check_requirements(routing, context)

    assert result.status == RequirementStatus.READY
    assert result.missing_data == ()
