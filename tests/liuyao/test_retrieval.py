from dataclasses import replace
from unittest.mock import AsyncMock

import pytest

from guanchen_v2.knowledge.models import KnowledgeDomain, RetrievalResult, SourceType
from guanchen_v2.liuyao.casting import HexagramCastingService, ManualCastingInput, SystemRandomCoinSource
from guanchen_v2.liuyao.iching_adapter import IChingPyAdapter
from guanchen_v2.liuyao.retrieval import LIUYAO_RETRIEVAL_FILTER, LiuyaoRetrievalBuilder
from guanchen_v2.models.liuyao import CastingMethod, HexagramIdentity, HexagramLine, HexagramResult, LineValue, YinYang


def create_mock_result(chunk_id: str) -> RetrievalResult:
    return RetrievalResult(
        rank=1,
        chunk_id=chunk_id,
        document_id="doc1",
        domain=KnowledgeDomain.LIUYAO,
        source_title="测试书",
        source_type=SourceType.PUBLIC_DOMAIN_CLASSIC,
        section="第一章",
        text="测试文本",
        rrf_score=0.9,
        rrf_rank=1,
        reranker_score=None,
        dense_rank=1,
        sparse_rank=1,
    )


@pytest.mark.asyncio
async def test_liuyao_retrieval_builder_dedupes_and_filters():
    """验证检索建造器能过滤重复 chunk_id 并传递正确的 domain 限制过滤"""
    mock_shared_service = AsyncMock()

    # 模拟底层的多次检索返回了重复的 Chunk_ID
    # 根据我们 retrieval_builder 的逻辑，静卦会产生 2 条 Query (本卦查询、事象映射)
    mock_shared_service.retrieve.side_effect = [
        [create_mock_result("A"), create_mock_result("B")],
        [create_mock_result("B"), create_mock_result("C")],
    ]

    # 构造一个符合所有 Pydantic 严格校验的真实合法的假卦象
    mock_hexagram = HexagramResult(
        casting_method=CastingMethod.MANUAL_SIX_LINES,
        lines=tuple(HexagramLine(position=i, value=LineValue.YOUNG_YANG, polarity=YinYang.YANG, moving=False) for i in range(1, 7)),
        primary_hexagram=HexagramIdentity(name="否", upper_trigram="乾", lower_trigram="坤"),
    )

    builder = LiuyaoRetrievalBuilder(mock_shared_service)
    results = await builder.retrieve("我要不要离职", mock_hexagram)

    # 去重后应只有 A, B, C
    assert len(results) == 3
    assert {r.chunk_id for r in results} == {"A", "B", "C"}

    # 验证底层被传了合法的 Filter
    assert mock_shared_service.retrieve.call_count == 2
    for call in mock_shared_service.retrieve.call_args_list:
        assert call.kwargs["filters"] == LIUYAO_RETRIEVAL_FILTER


@pytest.mark.asyncio
async def test_other_hexagram_judgements_cannot_enter_current_cast_evidence():
    service = HexagramCastingService(IChingPyAdapter(), SystemRandomCoinSource())
    facts = service.cast_manual(ManualCastingInput(lines=(8, 7, 7, 6, 9, 8)))
    shared = AsyncMock()
    shared.retrieve.return_value = [
        replace(create_mock_result("wrong"), source_title="《周易》", section="第五十七卦 巽 巽上巽下"),
        replace(create_mock_result("primary"), source_title="《周易》", section="第四十八卦 井 坎上巽下"),
        replace(create_mock_result("changed"), source_title="《周易》", section="第三十二卦 恒 震上巽下"),
        create_mock_result("general"),
    ]
    results = await LiuyaoRetrievalBuilder(shared).retrieve("职业选择", facts)
    assert {r.chunk_id for r in results} == {"primary", "changed", "general"}
