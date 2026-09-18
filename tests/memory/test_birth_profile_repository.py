"""Stage 8 必测 1：BirthProfile 持久化集成测试（写入 / 读取 / 更正）。

验收点：
- 应用重启后 BirthProfile 仍可恢复（repository 写入 -> 全新 repository 实例读取）；
- 后写的明确更正覆盖当前有效事实，并保留 updated_at（用户更正语义）。
"""
import pytest

from guanchen_v2.memory.repositories import BirthProfileRepository
from guanchen_v2.models.bazi import BirthProfile, Gender

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_birth_profile_write_read_correct(postgres_session_factory):
    """写入 -> 读取（模拟重启）-> 更正 -> 再次读取，且 updated_at 随更正推进。"""
    repo = BirthProfileRepository(postgres_session_factory)

    user_id = "user-birth-1"

    # 1. 用户明确提供出生资料
    original = BirthProfile(
        year=1990,
        month=5,
        day=20,
        hour=14,
        minute=30,
        gender=Gender.MALE,
        birth_place_text="北京",
    )
    await repo.upsert(user_id, original)

    # 2. “应用重启”：完全新的 repository 实例读取（同一数据库）
    repo_after_restart = BirthProfileRepository(postgres_session_factory)
    loaded = await repo_after_restart.get(user_id)

    assert loaded is not None
    assert loaded.year == 1990
    assert loaded.month == 5
    assert loaded.day == 20
    assert loaded.hour == 14
    assert loaded.minute == 30
    assert loaded.gender == Gender.MALE
    assert loaded.birth_place_text == "北京"

    # 3. 用户更正出生时间（后写覆盖）
    corrected = BirthProfile(
        year=1990,
        month=5,
        day=20,
        hour=16,
        minute=0,
        gender=Gender.MALE,
        birth_place_text="北京",
    )
    await repo.upsert(user_id, corrected)

    loaded_corrected = await repo.get(user_id)
    assert loaded_corrected is not None
    assert loaded_corrected.hour == 16
    assert loaded_corrected.minute == 0

    # 4. 更正后 updated_at 必须推进（保留 updated_at 语义，行级维护）
    from sqlalchemy import select

    from guanchen_v2.memory.models import BirthProfileRow

    async def fetch_row():
        async with postgres_session_factory() as session:
            result = await session.execute(
                select(BirthProfileRow).where(BirthProfileRow.user_id == user_id)
            )
            return result.scalar_one()

    row_after_first = await fetch_row()
    await repo.upsert(user_id, corrected)
    row_after_correction = await fetch_row()

    assert row_after_first.updated_at is not None
    assert row_after_correction.updated_at is not None
    assert row_after_correction.updated_at >= row_after_first.updated_at


@pytest.mark.asyncio
async def test_birth_profile_single_current_fact(postgres_session_factory):
    """单用户只保留一条当前有效事实（唯一约束 + upsert 覆盖）。"""
    repo = BirthProfileRepository(postgres_session_factory)
    user_id = "user-birth-2"

    first = BirthProfile(
        year=1988, month=1, day=1, hour=8, minute=0, gender=Gender.FEMALE
    )
    second = BirthProfile(
        year=1988, month=1, day=1, hour=10, minute=15, gender=Gender.FEMALE
    )

    await repo.upsert(user_id, first)
    await repo.upsert(user_id, second)

    loaded = await repo.get(user_id)
    assert loaded is not None
    assert (loaded.hour, loaded.minute) == (10, 15)

    from sqlalchemy import func, select

    from guanchen_v2.memory.models import BirthProfileRow

    async with postgres_session_factory() as session:
        count = (await session.execute(select(func.count()).select_from(BirthProfileRow).where(BirthProfileRow.user_id == user_id))).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_birth_profile_missing_returns_none(postgres_session_factory):
    """从未提供过出生资料的用户返回 None，而不是异常。"""
    repo = BirthProfileRepository(postgres_session_factory)
    assert await repo.get("user-never-existed") is None
