import pytest

from guanchen_v2.agents.bazi.exceptions import (
    BaziAgentCitationError,
    BaziAgentError,
    BaziAgentExecutionError,
    BaziAgentInvariantError,
)
from guanchen_v2.bazi.exceptions import (
    BaziAdapterError,
    BaziCalculationError,
    BaziError,
)
from guanchen_v2.core.errors import ProjectError
from guanchen_v2.dream.exceptions import (
    DreamError,
    DreamExtractionError,
    DreamInterpretationError,
    DreamMergeConflictError,
)
from guanchen_v2.knowledge.errors import (
    KnowledgeAgentError,
    KnowledgeEmbeddingError,
    KnowledgeError,
    KnowledgePersistenceError,
    KnowledgeRerankerError,
    KnowledgeRetrievalError,
    KnowledgeTransactionError,
)
from guanchen_v2.llm.exceptions import (
    LLMEmptyResponseError,
    LLMError,
    LLMProviderError,
    LLMResponseError,
    LLMRetryExhaustedError,
    LLMStructuredOutputError,
    LLMTransientProviderError,
)


def test_project_error_is_runtime_error():
    assert issubclass(
        ProjectError,
        RuntimeError,
    )


@pytest.mark.parametrize(
    "root_error",
    [
        LLMError,
        KnowledgeError,
        BaziError,
        DreamError,
    ],
)
def test_subsystem_roots_inherit_project_error(
    root_error,
):
    assert issubclass(
        root_error,
        ProjectError,
    )


@pytest.mark.parametrize(
    "error_type",
    [
        LLMProviderError,
        LLMTransientProviderError,
        LLMResponseError,
        LLMEmptyResponseError,
        LLMStructuredOutputError,
        LLMRetryExhaustedError,
        KnowledgeEmbeddingError,
        KnowledgePersistenceError,
        KnowledgeTransactionError,
        KnowledgeRetrievalError,
        KnowledgeRerankerError,
        KnowledgeAgentError,
        BaziAdapterError,
        BaziCalculationError,
        BaziAgentError,
        BaziAgentExecutionError,
        BaziAgentInvariantError,
        BaziAgentCitationError,
        DreamMergeConflictError,
        DreamExtractionError,
        DreamInterpretationError,
    ],
)
def test_all_stable_errors_inherit_project_error(
    error_type,
):
    assert issubclass(
        error_type,
        ProjectError,
    )


def test_bazi_agent_is_inside_bazi_hierarchy():
    assert issubclass(
        BaziAgentError,
        BaziError,
    )

    assert issubclass(
        BaziAgentExecutionError,
        BaziError,
    )


def test_dream_errors_are_inside_dream_hierarchy():
    assert issubclass(
        DreamExtractionError,
        DreamError,
    )

    assert issubclass(
        DreamInterpretationError,
        DreamError,
    )


def test_cross_module_project_error_boundary():
    errors = [
        LLMProviderError("llm failure"),
        KnowledgeRetrievalError("retrieval failure"),
        BaziCalculationError("bazi failure"),
        BaziAgentInvariantError("agent failure"),
        DreamExtractionError("dream failure"),
    ]

    for error in errors:
        with pytest.raises(ProjectError):
            raise error
