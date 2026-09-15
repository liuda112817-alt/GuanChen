from pydantic import BaseModel, Field

from guanchen_v2.knowledge.models import (
    KnowledgeDomain,
    RetrievalFilter,
    RetrievalResult,
)
from guanchen_v2.knowledge.retrieval.service import RetrievalService
from guanchen_v2.models.dream import (
    DreamRecord,
    DreamRetrievalAspect,
    DreamRetrievalQuery,
    NonBlankText,
)

DREAM_RETRIEVAL_FILTER = RetrievalFilter(domains=frozenset({KnowledgeDomain.DREAM}))


class DreamRetrievalEvidence(BaseModel):
    """一个 Dream retrieval aspect 对应的检索结果集合。"""

    aspect: DreamRetrievalAspect
    query: NonBlankText
    results: list[RetrievalResult] = Field(default_factory=list)


def _join_values(values: list[str]) -> str:
    return "、".join(values)


def build_dream_retrieval_queries(
    record: DreamRecord,
) -> list[DreamRetrievalQuery]:
    """
    将当前 DreamRecord 转换为确定性的 Dream retrieval queries。

    只使用已经结构化确认的梦境状态，
    不使用 raw_descriptions、revision 或模型自行推断的信息。
    """
    queries: list[DreamRetrievalQuery] = []

    elements = record.elements
    background = record.reality_background

    symbol_parts: list[str] = []

    if elements.people:
        symbol_parts.append(f"人物：{_join_values(elements.people)}")

    if elements.scenes:
        symbol_parts.append(f"场景：{_join_values(elements.scenes)}")

    if elements.objects:
        symbol_parts.append(f"对象：{_join_values(elements.objects)}")

    if elements.actions:
        symbol_parts.append(f"行为：{_join_values(elements.actions)}")

    if elements.anomalies:
        symbol_parts.append(f"异常现象：{_join_values(elements.anomalies)}")

    if symbol_parts:
        queries.append(
            DreamRetrievalQuery(
                aspect=DreamRetrievalAspect.SYMBOL,
                query=(f"梦境传统象征 {'；'.join(symbol_parts)}"),
            )
        )

    emotion_parts: list[str] = []

    if elements.emotions:
        emotion_parts.append(f"梦中情绪：{_join_values(elements.emotions)}")

    if elements.subjective_feelings:
        emotion_parts.append(f"醒后感受：{_join_values(elements.subjective_feelings)}")

    if emotion_parts:
        queries.append(
            DreamRetrievalQuery(
                aspect=DreamRetrievalAspect.EMOTION,
                query=(f"梦境情绪传统解释 {'；'.join(emotion_parts)}"),
            )
        )

    reality_parts: list[str] = []

    if background.recent_events:
        reality_parts.append(f"近期事件：{_join_values(background.recent_events)}")

    if background.ongoing_contexts:
        reality_parts.append(f"当前情境：{_join_values(background.ongoing_contexts)}")

    if background.stressors:
        reality_parts.append(f"压力：{_join_values(background.stressors)}")

    if background.user_associations:
        reality_parts.append(f"主观联想：{_join_values(background.user_associations)}")

    if reality_parts:
        queries.append(
            DreamRetrievalQuery(
                aspect=DreamRetrievalAspect.REALITY_CONTEXT,
                query=(f"梦境与现实情境传统解释 {'；'.join(reality_parts)}"),
            )
        )

    return queries


def dedupe_retrieval_results(
    evidence_list: list[DreamRetrievalEvidence],
) -> list[RetrievalResult]:
    """
    跨 Dream retrieval aspect 对 Chunk 做稳定去重。

    保留同一 chunk 第一次出现的位置，
    不根据 score 再次排序。
    """
    deduped: list[RetrievalResult] = []
    seen_chunk_ids: set[str] = set()

    for evidence in evidence_list:
        for result in evidence.results:
            if result.chunk_id in seen_chunk_ids:
                continue

            seen_chunk_ids.add(result.chunk_id)
            deduped.append(result)

    return deduped


class DreamRetrievalService:
    """
    Dream Agent 的领域检索适配层。

    领域边界：
    - 所有 Dream query 必须限定在 KnowledgeDomain.DREAM；
    - 调用方不能覆盖或关闭该过滤条件；
    - Shared RetrievalService 继续负责 Dense/Sparse/RRF/Reranker。
    """

    def __init__(
        self,
        retrieval_service: RetrievalService,
    ) -> None:
        self._retrieval_service = retrieval_service

    async def retrieve(
        self,
        record: DreamRecord,
    ) -> list[DreamRetrievalEvidence]:
        queries = build_dream_retrieval_queries(record)

        evidence_groups: list[DreamRetrievalEvidence] = []

        for retrieval_query in queries:
            results = await self._retrieval_service.retrieve(
                query=retrieval_query.query,
                filters=DREAM_RETRIEVAL_FILTER,
            )

            evidence_groups.append(
                DreamRetrievalEvidence(
                    aspect=retrieval_query.aspect,
                    query=retrieval_query.query,
                    results=results,
                )
            )

        return evidence_groups
