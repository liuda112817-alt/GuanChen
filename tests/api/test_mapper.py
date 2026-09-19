import pytest

from guanchen_v2.api.contracts import ChatStatus
from guanchen_v2.api.mapper import ChatResponseMapper
from guanchen_v2.core.session.models import ConversationState
from guanchen_v2.router.contracts import IntentType, RequiredDataType
from guanchen_v2.router.requirements import RequirementCheckResult, RequirementStatus
from guanchen_v2.router.synthesis import SynthesizedResponse


def test_mapper_rejects_unknown_status():
    mapper = ChatResponseMapper()
    resp = SynthesizedResponse(session_id="s1", status="waiting", content="", used_intents=[], citations=[])
    with pytest.raises(ValueError, match="Unsupported runtime response status: waiting"):
        mapper.map(resp, safety=None, state=None)


def test_mapper_maps_answered():
    mapper = ChatResponseMapper()
    resp = SynthesizedResponse(session_id="s1", status="answered", content="Done", used_intents=[IntentType.KNOWLEDGE], citations=[])
    result = mapper.map(resp, safety=None, state=None)
    assert result.status == ChatStatus.ANSWERED
    assert result.required_input is None


def test_mapper_maps_bazi_needs_input():
    mapper = ChatResponseMapper()
    resp = SynthesizedResponse(session_id="s1", status="needs_input", content="Missing", used_intents=[IntentType.BAZI], citations=[])
    state = ConversationState(session_id="s1")
    state.requirement_result = RequirementCheckResult(
        intent=IntentType.BAZI,
        status=RequirementStatus.NEEDS_INPUT,
        required_data=(RequiredDataType.BIRTH_PROFILE,),
        missing_data=(RequiredDataType.BIRTH_PROFILE,),
    )
    state.agent_states.bazi["input_requirement"] = {"missing_fields": ["year", "month"]}

    result = mapper.map(resp, safety=None, state=state)
    assert result.status == ChatStatus.NEEDS_INPUT
    assert result.required_input.kind == "birth_profile"
    assert "year" in result.required_input.fields


def test_mapper_dream_needs_clarification():
    mapper = ChatResponseMapper()
    resp = SynthesizedResponse(session_id="s1", status="needs_clarification", content="", used_intents=[IntentType.DREAM], citations=[])
    result = mapper.map(resp, safety=None, state=None)
    assert result.status == ChatStatus.NEEDS_INPUT
    assert result.required_input.kind == "dream_content"


def test_mapper_liuyao_needs_input():
    mapper = ChatResponseMapper()
    resp = SynthesizedResponse(session_id="s1", status="needs_input", content="", used_intents=[IntentType.LIUYAO], citations=[])
    state = ConversationState(session_id="s1")
    state.requirement_result = RequirementCheckResult(
        intent=IntentType.LIUYAO,
        status=RequirementStatus.NEEDS_INPUT,
        required_data=(RequiredDataType.DECISION_QUESTION,),
        missing_data=(RequiredDataType.DECISION_QUESTION,),
    )
    result = mapper.map(resp, safety=None, state=state)
    assert result.status == ChatStatus.NEEDS_INPUT
    assert result.required_input.kind == "decision_question"


def test_mapper_cancelled():
    mapper = ChatResponseMapper()
    resp = SynthesizedResponse(session_id="s1", status="cancelled", content="取消", used_intents=[IntentType.LIUYAO], citations=[])
    result = mapper.map(resp, safety=None, state=None)
    assert result.status == ChatStatus.CANCELLED


def test_mapper_rejects_interrupted_without_thread():
    mapper = ChatResponseMapper()
    resp = SynthesizedResponse(session_id="s1", status="interrupted", content="prompt", used_intents=[IntentType.LIUYAO], citations=[])
    with pytest.raises(ValueError, match="Interrupted runtime response must contain thread_id"):
        mapper.map(resp, safety=None, state=None)


def test_mapper_citation_lineage():
    mapper = ChatResponseMapper()
    citation_dict = {"chunk_id": "chunk1", "document_id": "doc1", "source_title": "Title", "section": "Section"}
    resp = SynthesizedResponse(
        session_id="s1",
        status="answered",
        content="",
        used_intents=[IntentType.KNOWLEDGE],
        citations=[citation_dict],  # 使用 dict
    )
    result = mapper.map(resp, safety=None, state=None)
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == "chunk1"
    assert result.citations[0].document_id == "doc1"
    assert result.citations[0].source_title == "Title"
    assert result.citations[0].section == "Section"
