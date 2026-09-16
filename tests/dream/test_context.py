from unittest.mock import AsyncMock, MagicMock

import pytest

from guanchen_v2.dream.context import DreamContextService, classify_dream_boundary
from guanchen_v2.dream.dream_merge import merge_dream_record, start_new_dream
from guanchen_v2.models.dream import (
    DreamContextStatus,
    DreamCorrection,
    DreamElements,
    DreamField,
    DreamPatch,
    DreamTurnBoundary,
    RealityBackground,
)


@pytest.fixture
def mock_extractor():
    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value=DreamPatch())
    return extractor


@pytest.fixture
def context_service(mock_extractor):
    return DreamContextService(extractor=mock_extractor)


def test_explicit_same_dream_negation_does_not_reset():
    """测试带有 '不是另一个梦' 等否定句时，不会触发错误的新梦标记"""
    result = classify_dream_boundary(
        "这不是另一个梦，是刚才那个梦的补充",
        has_current_dream=True,
    )
    assert result == DreamTurnBoundary.SAME


@pytest.mark.asyncio
async def test_3_consecutive_turns_same_dream(context_service, mock_extractor):
    """连续 3 轮梦境补充（场景 -> 现实背景 -> 修正人物），不丢旧字段"""
    # 轮次 1：初始梦境
    mock_extractor.extract.return_value = DreamPatch(element_additions=DreamElements(scenes=["旧学校", "走廊"]))
    res1 = await context_service.apply_turn("我梦见在学校走廊", None)

    assert res1.status == DreamContextStatus.UPDATED
    assert "旧学校" in res1.record.elements.scenes

    # 轮次 2：补充现实压力（注意这里不会触发 raw_description 的追加）
    mock_extractor.extract.return_value = DreamPatch(background_additions=RealityBackground(stressors=["考试"]))
    res2 = await context_service.apply_turn("最近考试压力大", res1.record)

    assert res2.status == DreamContextStatus.UPDATED
    assert "旧学校" in res2.record.elements.scenes
    assert "考试" in res2.record.reality_background.stressors
    assert len(res2.record.raw_descriptions) == 1

    # 轮次 3：错误修正
    mock_extractor.extract.return_value = DreamPatch(corrections=[DreamCorrection(field=DreamField.SCENES, old_value="旧学校", new_value="小学")])
    res3 = await context_service.apply_turn("不是旧学校，是小学", res2.record)

    assert res3.status == DreamContextStatus.UPDATED
    assert "旧学校" not in res3.record.elements.scenes
    assert "小学" in res3.record.elements.scenes
    assert "考试" in res3.record.reality_background.stressors
    assert res3.record.dream_id == res1.record.dream_id


@pytest.mark.asyncio
async def test_explicit_new_dream(context_service, mock_extractor):
    """明确的新梦标记应重启 DreamRecord 且 严格屏蔽旧上下文"""

    # 构建一个有脏数据的旧梦境
    old_record = merge_dream_record(
        start_new_dream(),
        DreamPatch(
            element_additions=DreamElements(
                people=["妈妈"],
                scenes=["旧学校"],
            )
        ),
    )

    mock_extractor.extract.return_value = DreamPatch(element_additions=DreamElements(scenes=["海边"]))
    res = await context_service.apply_turn("换一个梦，我梦到了海边", old_record)

    assert res.status == DreamContextStatus.UPDATED
    assert res.started_new_dream is True
    assert res.record.dream_id != old_record.dream_id

    # 核心验证 1：Extractor 收到的 current_record 必须被完全置空
    kwargs = mock_extractor.extract.call_args.kwargs
    extraction_record = kwargs["current_record"]

    assert extraction_record.dream_id != old_record.dream_id
    assert extraction_record.elements.people == []
    assert extraction_record.elements.scenes == []

    # 核心验证 2：最终的 ContextResult 也绝对不能包含前一个梦的元素
    assert "妈妈" not in res.record.elements.people
    assert "旧学校" not in res.record.elements.scenes
    assert res.record.elements.scenes == ["海边"]


@pytest.mark.asyncio
async def test_ambiguous_dream_boundary_clarification(context_service):
    """边界模糊时不猜，直接触发澄清追问"""
    old_record = start_new_dream()
    res = await context_service.apply_turn("昨晚我又梦见在树林", old_record)

    assert res.status == DreamContextStatus.NEEDS_CLARIFICATION
    assert "还是一个新的梦" in res.clarification_question


@pytest.mark.asyncio
async def test_merge_conflict_clarification(context_service, mock_extractor):
    """明确修正但目标缺失时，转为澄清追问，绝不污染原状态"""
    old_record = start_new_dream()
    mock_extractor.extract.return_value = DreamPatch(corrections=[DreamCorrection(field=DreamField.PEOPLE, old_value="妈妈", new_value="同事")])

    res = await context_service.apply_turn("不是妈妈，是同事", old_record)

    assert res.status == DreamContextStatus.NEEDS_CLARIFICATION
    assert "哪一项信息" in res.clarification_question
    assert res.record == old_record


@pytest.mark.asyncio
async def test_no_dream_content_clarification(context_service, mock_extractor):
    """仅包含现实压力，完全没有梦境实体时，触发补充追问"""
    mock_extractor.extract.return_value = DreamPatch(background_additions=RealityBackground(stressors=["加班"]))

    res = await context_service.apply_turn("最近疯狂加班", None)

    assert res.status == DreamContextStatus.NEEDS_CLARIFICATION
    assert "哪怕只描述一两个最鲜明的片段" in res.clarification_question


@pytest.mark.asyncio
async def test_empty_patch_then_what(context_service, mock_extractor):
    """'然后呢'导致的空补丁应正常延续状态，不引发无意义的强制问卷调查"""
    record = start_new_dream()
    record.elements.scenes.append("天台")

    mock_extractor.extract.return_value = DreamPatch()
    res = await context_service.apply_turn("然后呢？", record)

    assert res.status == DreamContextStatus.UPDATED
    assert res.started_new_dream is False
    assert "天台" in res.record.elements.scenes
