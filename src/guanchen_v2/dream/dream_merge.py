from guanchen_v2.dream.exceptions import DreamMergeConflictError
from guanchen_v2.models.dream import (
    DreamElements,
    DreamInterpretationState,
    DreamPatch,
    DreamRecord,
    InterpretationStatus,
    RealityBackground,
)


def _normalize(text: str) -> str:
    """轻量级规范化，用于稳定的去重和冲突检测"""
    return " ".join(text.split()).casefold()


def _stable_dedupe(items: list[str]) -> list[str]:
    """在保持顺序和原始大小写不变的情况下，对列表进行去重"""
    seen = set()
    result = []
    for item in items:
        norm = _normalize(item)
        if norm not in seen:
            seen.add(norm)
            result.append(item)
    return result


def merge_dream_record(
    record: DreamRecord,
    patch: DreamPatch,
    *,
    raw_description_fragment: str | None = None,
) -> DreamRecord:

    new_elements = record.elements.model_dump()
    new_bg = record.reality_background.model_dump()
    new_raw = list(record.raw_descriptions)

    for correction in patch.corrections:
        domain_name, field_name = correction.field.value.split(".")
        target_dict = new_elements if domain_name == "elements" else new_bg

        target_list = target_dict[field_name]
        norm_old = _normalize(correction.old_value)

        found_idx = -1
        for i, item in enumerate(target_list):
            if _normalize(item) == norm_old:
                found_idx = i
                break

        if found_idx == -1:
            raise DreamMergeConflictError("当前梦境记录中不存在待修正目标")

        if correction.new_value is None:
            target_list.pop(found_idx)
        else:
            target_list[found_idx] = correction.new_value

    for field in new_elements.keys():
        adds = getattr(patch.element_additions, field)
        new_elements[field] = _stable_dedupe(new_elements[field] + adds)

    for field in new_bg.keys():
        adds = getattr(patch.background_additions, field)
        new_bg[field] = _stable_dedupe(new_bg[field] + adds)

    if raw_description_fragment:
        norm_frag = _normalize(raw_description_fragment)
        if norm_frag and not any(_normalize(existing) == norm_frag for existing in new_raw):
            new_raw.append(raw_description_fragment)

    updated_elements = DreamElements(**new_elements)
    updated_bg = RealityBackground(**new_bg)

    elements_changed = record.elements != updated_elements
    bg_changed = record.reality_background != updated_bg
    raw_changed = record.raw_descriptions != new_raw

    new_revision = record.revision
    new_status = record.interpretation_state.status

    if elements_changed or bg_changed or raw_changed:
        new_revision += 1
        if new_status == InterpretationStatus.CURRENT:
            new_status = InterpretationStatus.STALE

    return DreamRecord(
        dream_id=record.dream_id,
        raw_descriptions=new_raw,
        elements=updated_elements,
        reality_background=updated_bg,
        interpretation_state=DreamInterpretationState(
            status=new_status, last_interpreted_revision=record.interpretation_state.last_interpreted_revision
        ),
        revision=new_revision,
    )


def start_new_dream() -> DreamRecord:
    """返回一个完全新的、状态隔离的DreamRecord"""
    return DreamRecord()


def mark_interpreted(record: DreamRecord) -> DreamRecord:
    """助手将记录解释状态转换为当前"""
    new_record = record.model_copy(deep=True)
    new_record.interpretation_state.status = InterpretationStatus.CURRENT
    new_record.interpretation_state.last_interpreted_revision = new_record.revision
    return new_record
