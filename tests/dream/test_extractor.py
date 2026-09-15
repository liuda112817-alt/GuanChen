from unittest.mock import AsyncMock, MagicMock

import pytest

from guanchen_v2.dream.dream_merge import (
    merge_dream_record,
    start_new_dream,
)
from guanchen_v2.dream.exceptions import (
    DreamExtractionError,
)
from guanchen_v2.dream.extractor import (
    DreamExtractor,
)
from guanchen_v2.llm.client import LLMClient
from guanchen_v2.llm.exceptions import (
    LLMProviderError,
    LLMStructuredOutputError,
)
from guanchen_v2.models.dream import (
    DreamElements,
    DreamPatch,
)
from guanchen_v2.prompts.dream_agent import (
    DREAM_EXTRACTION_SYSTEM_PROMPT,
)


@pytest.fixture
def fake_llm_client():
    client = MagicMock(spec_set=LLMClient)

    client.generate_structured = AsyncMock(return_value=DreamPatch())

    return client


@pytest.fixture
def extractor(
    fake_llm_client,
):
    return DreamExtractor(llm_client=fake_llm_client)


@pytest.mark.asyncio
async def test_extract_returns_dream_patch_and_uses_llm_client_contract(
    extractor,
    fake_llm_client,
):
    expected = DreamPatch(
        element_additions=DreamElements(
            scenes=["旧学校"],
            emotions=["害怕"],
        )
    )

    fake_llm_client.generate_structured.return_value = expected

    result = await extractor.extract("我梦到回到旧学校，梦里很害怕")

    assert result == expected

    fake_llm_client.generate_structured.assert_awaited_once()

    kwargs = fake_llm_client.generate_structured.await_args.kwargs

    assert set(kwargs) == {
        "system_prompt",
        "user_prompt",
        "schema",
    }

    assert kwargs["system_prompt"] == DREAM_EXTRACTION_SYSTEM_PROMPT

    assert kwargs["schema"] is DreamPatch

    assert "我梦到回到旧学校" in kwargs["user_prompt"]

    # System instruction 与用户数据保持分离。
    assert "旧学校" not in kwargs["system_prompt"]


@pytest.mark.asyncio
async def test_empty_input_raises_error_without_calling_llm(
    extractor,
    fake_llm_client,
):
    with pytest.raises(
        DreamExtractionError,
        match="抽取输入不能为空",
    ):
        await extractor.extract("   ")

    fake_llm_client.generate_structured.assert_not_awaited()


@pytest.mark.asyncio
async def test_provider_failure_is_wrapped_and_chained(
    extractor,
    fake_llm_client,
):
    provider_error = LLMProviderError("LLM provider failure")

    fake_llm_client.generate_structured.side_effect = provider_error

    with pytest.raises(
        DreamExtractionError,
        match="梦境信息结构化抽取失败",
    ) as exc_info:
        await extractor.extract("我梦见了一只猫")

    assert exc_info.value.__cause__ is provider_error


@pytest.mark.asyncio
async def test_structured_output_failure_is_wrapped_and_chained(
    extractor,
    fake_llm_client,
):
    structured_error = LLMStructuredOutputError("structured output failure")

    fake_llm_client.generate_structured.side_effect = structured_error

    with pytest.raises(
        DreamExtractionError,
        match="梦境信息结构化抽取失败",
    ) as exc_info:
        await extractor.extract("我梦见了一只猫")

    assert exc_info.value.__cause__ is structured_error


@pytest.mark.asyncio
async def test_context_selection_hides_raw_history(
    extractor,
    fake_llm_client,
):
    record = start_new_dream()

    record = merge_dream_record(
        record,
        DreamPatch(element_additions=DreamElements(scenes=["旧学校"])),
        raw_description_fragment=("第一句话，啰嗦的历史信息，不该发给模型"),
    )

    await extractor.extract(
        "第二句话",
        current_record=record,
    )

    user_prompt = fake_llm_client.generate_structured.await_args.kwargs["user_prompt"]

    assert "旧学校" in user_prompt
    assert "elements" in user_prompt

    assert "啰嗦的历史信息" not in user_prompt

    assert "raw_descriptions" not in user_prompt
    assert "interpretation_state" not in user_prompt
    assert '"revision"' not in user_prompt


@pytest.mark.asyncio
async def test_extraction_does_not_mutate_state(
    extractor,
):
    record = start_new_dream()

    record = merge_dream_record(
        record,
        DreamPatch(element_additions=DreamElements(people=["姐姐"])),
    )

    original = record.model_copy(deep=True)

    await extractor.extract(
        "其实不是姐姐，是同事",
        current_record=record,
    )

    assert record == original


@pytest.mark.asyncio
async def test_defensive_invalid_return_type_fails(
    extractor,
    fake_llm_client,
):
    """
    LLMClient 正常情况下已经保证 schema 类型。

    该测试保留 DreamExtractor 自身的最后一道
    defensive boundary，防止未来错误实现或测试替身
    绕过 LLMClient contract。
    """
    fake_llm_client.generate_structured.return_value = {"not": "dream_patch"}

    with pytest.raises(
        DreamExtractionError,
        match="未返回合法的 DreamPatch",
    ):
        await extractor.extract("我梦见一只猫")
