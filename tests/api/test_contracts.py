import pytest
from pydantic import ValidationError

from guanchen_v2.agents.bazi.models import BaziBirthDataPatch
from guanchen_v2.api.contracts import APIErrorResponse, ChatRequest, ChatResponse, ChatStatus, CitationResponse, ProfileUpdateRequest, ResumeRequest
from guanchen_v2.safety.models import RiskDomain, RiskLevel, SafetyAction, SafetyDecision


def test_chat_request_rejects_empty_message():
    with pytest.raises(ValidationError):
        ChatRequest(message="")
    with pytest.raises(ValidationError):
        ChatRequest(message="   ")


def test_resume_request_validation():
    with pytest.raises(ValidationError):
        ResumeRequest(session_id="s1", thread_id="t1", action="yes")  # 无效 action

    with pytest.raises(ValidationError):
        ResumeRequest(session_id="s1", thread_id="   ", action="confirm")  # thread_id为空白


def test_profile_update_rejects_empty_patch():
    with pytest.raises(ValidationError, match="contain at least one field"):
        ProfileUpdateRequest(session_id="s1", birth_profile=BaziBirthDataPatch())


def test_chat_response_needs_input_consistency():
    with pytest.raises(ValidationError, match="required_input must be present"):
        ChatResponse(
            session_id="s1",
            status=ChatStatus.NEEDS_INPUT,
            content="请补充",
        )


def test_chat_response_interrupted_consistency():
    with pytest.raises(ValidationError, match="interrupt must be present"):
        ChatResponse(
            session_id="s1",
            status=ChatStatus.INTERRUPTED,
            content="请确认",
        )


def test_chat_response_blocked_consistency():
    with pytest.raises(ValidationError, match="safety must be present"):
        ChatResponse(session_id="s1", status=ChatStatus.BLOCKED, content="拒绝")

    with pytest.raises(ValidationError, match="SAFE_RESPONSE"):
        ChatResponse(
            session_id="s1",
            status=ChatStatus.BLOCKED,
            content="拒绝",
            safety=SafetyDecision(
                risk_domain=RiskDomain.MEDICAL, risk_level=RiskLevel.SENSITIVE, action=SafetyAction.ALLOW_WITH_BOUNDARY, reason_code="XX"
            ),
        )


def test_forbid_extra_fields():
    with pytest.raises(ValidationError):
        ChatRequest(message="hello", new_taks=True)  # 错别字或额外字段应被阻拦


def test_api_error_does_not_contain_exception_objects():
    err = APIErrorResponse(code="RUNTIME_ERROR", message="Internal server processing failed.", trace_id="tr-123456")
    assert not hasattr(err, "exception")
    assert not hasattr(err, "stack_trace")


def test_citation_response_is_safe():
    citation = CitationResponse(chunk_id="chunk-001", document_id="doc-001", source_title="《渊海子平》", section="卷之一")
    assert not hasattr(citation, "text")
    assert not hasattr(citation, "score")
