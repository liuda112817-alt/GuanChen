from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from guanchen_v2.dream.retrieval import (
    DREAM_RETRIEVAL_FILTER,
    DreamRetrievalEvidence,
    DreamRetrievalService,
    build_dream_retrieval_queries,
    dedupe_retrieval_results,
)
from guanchen_v2.knowledge.models import (
    KnowledgeDomain,
    RetrievalResult,
    SourceType,
)
from guanchen_v2.knowledge.retrieval.service import (
    RetrievalService,
)
from guanchen_v2.models.dream import (
    DreamElements,
    DreamRecord,
    DreamRetrievalAspect,
    RealityBackground,
)


def create_mock_retrieval_result(
    chunk_id: str,
) -> RetrievalResult:
    return RetrievalResult(
        rank=1,
        chunk_id=chunk_id,
        document_id=str(uuid4()),
        domain=KnowledgeDomain.DREAM,
        source_title="《周公解梦》",
        source_type=SourceType.PUBLIC_DOMAIN_CLASSIC,
        section="动物",
        text="梦见蛇。",
        rrf_score=0.9,
        rrf_rank=1,
        reranker_score=None,
        dense_rank=None,
        sparse_rank=None,
    )


def test_query_builder_all_aspects():
    record = DreamRecord(
        elements=DreamElements(
            objects=["黑猫"],
            emotions=["害怕"],
        ),
        reality_background=RealityBackground(stressors=["考试压力"]),
        raw_descriptions=["不要把我放进检索文本里"],
    )

    queries = build_dream_retrieval_queries(record)

    assert len(queries) == 3

    aspects = {query.aspect: query.query for query in queries}

    assert "黑猫" in aspects[DreamRetrievalAspect.SYMBOL]

    assert "害怕" in aspects[DreamRetrievalAspect.EMOTION]

    assert "考试压力" in aspects[DreamRetrievalAspect.REALITY_CONTEXT]

    assert not any("不要把我放进检索文本里" in query.query for query in queries)


def test_query_builder_missing_aspects():
    record = DreamRecord(elements=DreamElements(objects=["蛇"]))

    queries = build_dream_retrieval_queries(record)

    assert len(queries) == 1
    assert queries[0].aspect == DreamRetrievalAspect.SYMBOL


def test_dream_retrieval_filter_is_domain_locked():
    assert DREAM_RETRIEVAL_FILTER.domains == frozenset(
        {
            KnowledgeDomain.DREAM,
        }
    )

    assert DREAM_RETRIEVAL_FILTER.source_types is None
    assert DREAM_RETRIEVAL_FILTER.source_titles is None
    assert DREAM_RETRIEVAL_FILTER.sections is None


@pytest.mark.asyncio
async def test_retrieval_service_forces_dream_domain():
    shared_service = MagicMock(spec=RetrievalService)

    mock_result = create_mock_retrieval_result("chunk-1")

    shared_service.retrieve = AsyncMock(return_value=[mock_result])

    service = DreamRetrievalService(shared_service)

    record = DreamRecord(
        elements=DreamElements(
            objects=["蛇"],
            emotions=["恐惧"],
        )
    )

    evidence = await service.retrieve(record)

    assert len(evidence) == 2

    assert shared_service.retrieve.await_count == 2

    for call in shared_service.retrieve.await_args_list:
        assert call.kwargs["filters"] == DREAM_RETRIEVAL_FILTER

        assert call.kwargs["filters"].domains == frozenset(
            {
                KnowledgeDomain.DREAM,
            }
        )

    for evidence_group in evidence:
        assert evidence_group.results[0].chunk_id == "chunk-1"


def test_stable_chunk_dedupe():
    result_a = create_mock_retrieval_result("A")
    result_b = create_mock_retrieval_result("B")
    result_c = create_mock_retrieval_result("C")

    symbol_evidence = DreamRetrievalEvidence(
        aspect=DreamRetrievalAspect.SYMBOL,
        query="q1",
        results=[
            result_a,
            result_b,
        ],
    )

    emotion_evidence = DreamRetrievalEvidence(
        aspect=DreamRetrievalAspect.EMOTION,
        query="q2",
        results=[
            result_b,
            result_c,
        ],
    )

    deduped = dedupe_retrieval_results(
        [
            symbol_evidence,
            emotion_evidence,
        ]
    )

    assert len(deduped) == 3

    assert [result.chunk_id for result in deduped] == [
        "A",
        "B",
        "C",
    ]


@pytest.mark.asyncio
async def test_empty_retrieval_is_valid():
    shared_service = MagicMock(spec=RetrievalService)

    shared_service.retrieve = AsyncMock(return_value=[])

    service = DreamRetrievalService(shared_service)

    record = DreamRecord(elements=DreamElements(objects=["独角兽"]))

    evidence = await service.retrieve(record)

    assert len(evidence) == 1
    assert evidence[0].results == []

    shared_service.retrieve.assert_awaited_once()

    filters = shared_service.retrieve.await_args.kwargs["filters"]

    assert filters.domains == frozenset(
        {
            KnowledgeDomain.DREAM,
        }
    )
