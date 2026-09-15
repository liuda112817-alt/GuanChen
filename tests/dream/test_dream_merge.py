import pytest
from pydantic import ValidationError

from guanchen_v2.dream.dream_merge import mark_interpreted, merge_dream_record, start_new_dream
from guanchen_v2.dream.exceptions import DreamMergeConflictError
from guanchen_v2.models.dream import (
    DreamCorrection,
    DreamElements,
    DreamField,
    DreamPatch,
    InterpretationStatus,
    RealityBackground,
)


def test_consecutive_appends_retain_old_fields():
    record = start_new_dream()

    # Turn 1: Add Scene
    patch1 = DreamPatch(element_additions=DreamElements(scenes=["旧学校"]))
    record1 = merge_dream_record(record, patch1, raw_description_fragment="梦到在学校")
    assert "旧学校" in record1.elements.scenes

    # Turn 2: Add Person
    patch2 = DreamPatch(element_additions=DreamElements(people=["姐姐"]))
    record2 = merge_dream_record(record1, patch2, raw_description_fragment="里面还有我姐姐")
    assert "旧学校" in record2.elements.scenes
    assert "姐姐" in record2.elements.people

    # Turn 3: Add Background (Stressors). 纯现实背景不写入 raw_descriptions.
    patch3 = DreamPatch(background_additions=RealityBackground(stressors=["最近工作压力大"]))
    record3 = merge_dream_record(record2, patch3)
    assert "旧学校" in record3.elements.scenes
    assert "姐姐" in record3.elements.people
    assert "最近工作压力大" in record3.reality_background.stressors

    # 证明第 3 轮未提供 raw 文本，因此 raw_descriptions 长度仍为 2
    assert len(record3.raw_descriptions) == 2


def test_merge_does_not_mutate_input_record():
    record = start_new_dream()
    record = merge_dream_record(
        record,
        DreamPatch(
            element_additions=DreamElements(
                scenes=["旧学校"],
                people=["姐姐"],
            )
        ),
    )

    original = record.model_copy(deep=True)

    patch = DreamPatch(
        element_additions=DreamElements(objects=["红门"]),
        corrections=[
            DreamCorrection(
                field=DreamField.PEOPLE,
                old_value="姐姐",
                new_value="同事",
            )
        ],
    )

    result = merge_dream_record(record, patch)

    # 断言 1：入参 record 完全没变
    assert record == original
    # 断言 2：返回的是全新对象内存地址
    assert result is not record
    # 断言 3：原来的 record 依然保留旧值
    assert record.elements.people == ["姐姐"]
    assert record.elements.objects == []


def test_reject_blank_structured_values():
    """测试 NonBlankText 能否有效拦截大模型可能输出的脏数据"""
    with pytest.raises(ValidationError):
        DreamElements(people=["   "])

    with pytest.raises(ValidationError):
        DreamCorrection(field=DreamField.PEOPLE, old_value="", new_value=None)


# ====== 以下为原有的其它测试，只需修改报错捕获的 match 文案 ======


def test_unmentioned_fields_remain_unchanged():
    record = start_new_dream()
    patch1 = DreamPatch(element_additions=DreamElements(scenes=["教室"], objects=["黑板"]))
    record1 = merge_dream_record(record, patch1)

    patch2 = DreamPatch(element_additions=DreamElements(people=["老师"]))
    record2 = merge_dream_record(record1, patch2)

    assert record2.elements.scenes == ["教室"]
    assert record2.elements.objects == ["黑板"]
    assert record2.elements.people == ["老师"]


def test_stable_dedupe():
    record = start_new_dream()
    patch1 = DreamPatch(element_additions=DreamElements(people=["同事"]))
    record1 = merge_dream_record(record, patch1)

    # Append the same concept with different spacing/case (simulate normalization target)
    patch2 = DreamPatch(element_additions=DreamElements(people=[" 同事 "]))
    record2 = merge_dream_record(record1, patch2)

    assert len(record2.elements.people) == 1
    assert record2.elements.people[0] == "同事"


def test_explicit_correction_replace():
    record = start_new_dream()
    record = merge_dream_record(record, DreamPatch(element_additions=DreamElements(people=["姐姐"])))

    correction = DreamCorrection(field=DreamField.PEOPLE, old_value="姐姐", new_value="以前的同事")
    record2 = merge_dream_record(record, DreamPatch(corrections=[correction]))

    assert "姐姐" not in record2.elements.people
    assert "以前的同事" in record2.elements.people


def test_explicit_correction_remove():
    record = start_new_dream()
    record = merge_dream_record(record, DreamPatch(element_additions=DreamElements(objects=["红门"])))

    correction = DreamCorrection(field=DreamField.OBJECTS, old_value="红门", new_value=None)
    record2 = merge_dream_record(record, DreamPatch(corrections=[correction]))

    assert "红门" not in record2.elements.objects
    assert len(record2.elements.objects) == 0


def test_invalid_correction_raises_conflict():
    record = start_new_dream()
    record = merge_dream_record(record, DreamPatch(element_additions=DreamElements(people=["同事"])))

    correction = DreamCorrection(field=DreamField.PEOPLE, old_value="姐姐", new_value="路人")
    # match 文案已被修改为与核心逻辑中一致
    with pytest.raises(DreamMergeConflictError, match="当前梦境记录中不存在待修正目标"):
        merge_dream_record(record, DreamPatch(corrections=[correction]))


def test_interpretation_stale_logic():
    record = start_new_dream()
    record = merge_dream_record(record, DreamPatch(element_additions=DreamElements(scenes=["学校"])))

    # Simulate interpretation complete
    record = mark_interpreted(record)
    assert record.interpretation_state.status == InterpretationStatus.CURRENT

    # Empty patch (no-op) should not change revision or stale status
    record_noop = merge_dream_record(record, DreamPatch())
    assert record_noop.revision == record.revision
    assert record_noop.interpretation_state.status == InterpretationStatus.CURRENT

    # Effective change should bump revision and stale the status
    record_changed = merge_dream_record(record, DreamPatch(element_additions=DreamElements(people=["同事"])))
    assert record_changed.revision == record.revision + 1
    assert record_changed.interpretation_state.status == InterpretationStatus.STALE


def test_new_dream_reset():
    old_record = start_new_dream()
    old_record = merge_dream_record(
        old_record,
        DreamPatch(
            element_additions=DreamElements(people=["妈妈"]),
            background_additions=RealityBackground(stressors=["考试"]),
        ),
        raw_description_fragment="梦见考试",
    )
    old_record = mark_interpreted(old_record)

    new_record = start_new_dream()
    assert new_record.dream_id != old_record.dream_id
    assert new_record.elements.people == []
    assert new_record.reality_background.stressors == []
    assert new_record.raw_descriptions == []
    assert new_record.interpretation_state.status == InterpretationStatus.NOT_STARTED
    assert new_record.revision == 1
