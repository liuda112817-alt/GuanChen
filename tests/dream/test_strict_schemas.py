import pytest
from pydantic import ValidationError

from guanchen_v2.dream.runtime import (
    DreamInterpretationDraft,
)
from guanchen_v2.models.dream import (
    DreamPatch,
)


def test_dream_patch_rejects_top_level_extra():
    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        DreamPatch.model_validate(
            {
                "unexpected_field": "illegal",
            }
        )


def test_dream_patch_rejects_extra_inside_elements():
    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        DreamPatch.model_validate(
            {
                "element_additions": {
                    "scenes": ["旧学校"],
                    "hallucinated_field": ["illegal"],
                }
            }
        )


def test_dream_patch_rejects_extra_inside_background():
    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        DreamPatch.model_validate(
            {
                "background_additions": {
                    "stressors": ["工作压力"],
                    "diagnosis": ("模型不应创建这个字段"),
                }
            }
        )


def test_dream_patch_rejects_extra_inside_correction():
    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        DreamPatch.model_validate(
            {
                "corrections": [
                    {
                        "field": ("elements.people"),
                        "old_value": "姐姐",
                        "new_value": "同事",
                        "reason": "非法额外字段",
                    }
                ]
            }
        )


def test_dream_interpretation_draft_rejects_extra():
    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        DreamInterpretationDraft.model_validate(
            {
                "traditional_view": ("传统资料中的解释。"),
                "psychological_context_view": ("结合用户明确提供的现实背景进行反思。"),
                "used_chunk_ids": ["chunk-1"],
                "confidence": 0.99,
            }
        )


def test_dream_patch_json_schema_is_strict():
    schema = DreamPatch.model_json_schema()

    assert schema["additionalProperties"] is False

    definitions = schema["$defs"]

    assert definitions["DreamElements"]["additionalProperties"] is False

    assert definitions["RealityBackground"]["additionalProperties"] is False

    assert definitions["DreamCorrection"]["additionalProperties"] is False


def test_dream_interpretation_json_schema_is_strict():
    schema = DreamInterpretationDraft.model_json_schema()

    assert schema["additionalProperties"] is False


def test_uncited_traditional_text_is_discarded_without_inventing_evidence():
    draft = DreamInterpretationDraft(traditional_view="无引用的传统断言", psychological_context_view="可讨论用户自己的感受。")
    assert draft.traditional_view is None
    assert draft.used_chunk_ids == []
    assert draft.psychological_context_view == "可讨论用户自己的感受。"


def test_unused_citations_are_not_returned_as_sources():
    draft = DreamInterpretationDraft(traditional_view=None, used_chunk_ids=["unused-id"], psychological_context_view="反思")
    assert draft.traditional_view is None
    assert draft.used_chunk_ids == []
