import re

from guanchen_v2.dream.dream_merge import merge_dream_record, start_new_dream
from guanchen_v2.dream.exceptions import DreamMergeConflictError
from guanchen_v2.dream.extractor import DreamExtractor
from guanchen_v2.models.dream import (
    DreamContextResult,
    DreamContextStatus,
    DreamPatch,
    DreamRecord,
    DreamTurnBoundary,
)

_EXPLICIT_SAME_PATTERNS = (
    r"不是(另一个|另外一个|新的?)梦",
    r"(还是|就是|继续)刚才(那个)?梦",
    r"同一个梦",
    r"刚才(那个)?梦的补充",
)

_EXPLICIT_NEW_PATTERNS = (
    r"换一个梦",
    r"我还有(一个梦|另一个梦|另外一个梦)",
    r"这是(我(的)?)?第二个梦",
    r"再说一个(新梦|新的梦|梦)",
    r"(还|又)做了(一个梦|另一个梦|另外一个梦)",
    r"(另一个|另外一个)梦[是里中：:，,]",
)

_AMBIGUOUS_PATTERNS = (
    r"又梦到",
    r"又梦见",
    r"还梦到",
    r"还梦见",
)


def classify_dream_boundary(user_text: str, has_current_dream: bool) -> DreamTurnBoundary:
    """分层优先级的梦境边界判别，保守策略：优先识别'同一梦境'声明。"""
    if not has_current_dream:
        return DreamTurnBoundary.NEW

    text = user_text.strip()

    if any(re.search(pattern, text) for pattern in _EXPLICIT_SAME_PATTERNS):
        return DreamTurnBoundary.SAME

    if any(re.search(pattern, text) for pattern in _EXPLICIT_NEW_PATTERNS):
        return DreamTurnBoundary.NEW

    if any(re.search(pattern, text) for pattern in _AMBIGUOUS_PATTERNS):
        return DreamTurnBoundary.NEEDS_CLARIFICATION

    return DreamTurnBoundary.SAME


def patch_contains_dream_content(patch: DreamPatch) -> bool:
    """判断 Patch 中是否包含有效的梦境内元素更新。现实背景不算。"""
    adds = patch.element_additions
    if any(
        (
            adds.people,
            adds.scenes,
            adds.objects,
            adds.actions,
            adds.emotions,
            adds.anomalies,
            adds.subjective_feelings,
        )
    ):
        return True

    for correction in patch.corrections:
        if correction.field.value.startswith("elements."):
            return True

    return False


def has_dream_content(record: DreamRecord) -> bool:
    """判断一个梦境记录是否真的记录了梦境事件，而不仅仅是现实背景。"""
    e = record.elements
    return any((e.people, e.scenes, e.objects, e.actions, e.emotions, e.anomalies, e.subjective_feelings))


class DreamContextService:
    def __init__(self, extractor: DreamExtractor):
        self._extractor = extractor

    async def apply_turn(
        self,
        user_text: str,
        current_record: DreamRecord | None,
    ) -> DreamContextResult:
        boundary = classify_dream_boundary(user_text, current_record is not None)

        if boundary == DreamTurnBoundary.NEEDS_CLARIFICATION:
            return DreamContextResult(
                status=DreamContextStatus.NEEDS_CLARIFICATION,
                record=current_record,
                clarification_question="这是刚才那个梦的补充，还是一个新的梦？",
                started_new_dream=False,
            )

        if boundary == DreamTurnBoundary.NEW:
            base_record = start_new_dream()
            started_new_dream = True
        else:
            base_record = current_record
            started_new_dream = False

        patch = await self._extractor.extract(user_text, current_record=base_record)

        try:
            # 只有当该轮有真实的梦境更新时，才将原文记录为历史
            raw_frag = user_text if patch_contains_dream_content(patch) else None
            new_record = merge_dream_record(base_record, patch, raw_description_fragment=raw_frag)
        except DreamMergeConflictError:
            return DreamContextResult(
                status=DreamContextStatus.NEEDS_CLARIFICATION,
                record=base_record,
                patch=patch,
                clarification_question="你是在更正刚才梦里的哪一项信息？请说明原来的内容和正确内容。",
                started_new_dream=started_new_dream,
            )

        if not has_dream_content(new_record):
            return DreamContextResult(
                status=DreamContextStatus.NEEDS_CLARIFICATION,
                record=new_record,
                patch=patch,
                clarification_question="请补充一下梦里实际发生了什么，哪怕只描述一两个最鲜明的片段也可以。",
                started_new_dream=started_new_dream,
            )

        return DreamContextResult(
            status=DreamContextStatus.UPDATED,
            record=new_record,
            patch=patch,
            started_new_dream=started_new_dream,
        )
