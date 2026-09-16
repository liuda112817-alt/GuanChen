from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.types import Command

from guanchen_v2.knowledge.models import Citation, KnowledgeDomain, RetrievalResult, SourceType
from guanchen_v2.liuyao.exceptions import LiuyaoPolicyError
from guanchen_v2.liuyao.policy import ClarificationAssessment, rebuild_question
from guanchen_v2.liuyao.state import create_initial_liuyao_state
from guanchen_v2.liuyao.workflow import LiuyaoAgentRuntime
from guanchen_v2.models.liuyao import (
    CastingMethod,
    DecisionQuestionStatus,
    DecisionReflection,
    HexagramIdentity,
    HexagramLine,
    HexagramResult,
    LineValue,
    YinYang,
)


@pytest.fixture
def mock_deps():
    caster = MagicMock()
    llm = AsyncMock()
    retrieval = AsyncMock()
    return caster, llm, retrieval


def create_dummy_hexagram() -> HexagramResult:
    """提供一个极其标准的静卦用于骗过格式化器"""
    return HexagramResult(
        casting_method=CastingMethod.MANUAL_SIX_LINES,
        lines=tuple(HexagramLine(position=i, value=LineValue.YOUNG_YANG, polarity=YinYang.YANG, moving=False) for i in range(1, 7)),
        primary_hexagram=HexagramIdentity(upper_trigram="乾", lower_trigram="乾"),
    )


@pytest.mark.asyncio
async def test_clarify_node_populates_assessment_correctly(mock_deps):
    """验证 LLM 提案通过 apply_policy 正确写入状态"""
    caster, llm, retrieval = mock_deps

    # 模拟 LLM 成功结构化提取
    llm.generate_structured.return_value = ClarificationAssessment(
        needs_clarification=True, reality_constraints=["不想异地"], clarification_prompt="具体是什么工作类型？"
    )

    runtime = LiuyaoAgentRuntime(caster, llm, retrieval)
    state = create_initial_liuyao_state("外地有个 offer 去不去")

    new_state = await runtime.clarify_node(state)

    assert new_state["question"].status == DecisionQuestionStatus.NEEDS_CLARIFICATION
    assert new_state["clarification"] == "具体是什么工作类型？"
    assert new_state["question"].reality_constraints == ["不想异地"]


@pytest.mark.asyncio
async def test_retrieve_fails_fast_without_hexagram(mock_deps):
    """验证 retrieve_node 自身硬门槛：缺失卦象绝不调用数据库"""
    caster, llm, retrieval = mock_deps
    runtime = LiuyaoAgentRuntime(caster, llm, retrieval)

    state = create_initial_liuyao_state("测试检索")
    state["question"] = rebuild_question(state["question"], status=DecisionQuestionStatus.CONFIRMED, clarified_question="已确认")
    state["confirmed"] = True
    state["hexagram"] = None  # 漏掉了卦象

    with pytest.raises(LiuyaoPolicyError, match="缺少 HexagramResult，无法执行六爻知识检索"):
        await runtime.retrieve_node(state)

    assert retrieval.retrieve.call_count == 0


def test_finalize_node_deterministic_rendering():
    """验证 Finalize 节点没有使用大模型，只做确定性拼接"""
    runtime = LiuyaoAgentRuntime(None, None, None)

    reflection = DecisionReflection(
        situation_summary="面临职业分水岭",
        traditional_reflection="卦象平平",
        reality_check="资金不足，建议按兵不动",
        decision_options=["先干着", "积累人脉"],
        uncertainty_note="玄学参考不可尽信",
    )

    state = create_initial_liuyao_state("测试问题")
    state["reflection"] = reflection

    out = runtime.finalize_node(state)
    final_text = out["final_response"]

    assert "### 【文化推演】\n卦象平平" in final_text
    assert "### 【现实校验】\n资金不足，建议按兵不动" in final_text
    assert "- 先干着" in final_text
    assert "> *注：玄学参考不可尽信*" in final_text


def test_finalize_rejects_fake_evidence_reference():
    """验证 Finalize 节点能通过 _EVIDENCE_REF_PATTERN 精准抓取越界的伪造 Evidence"""
    runtime = LiuyaoAgentRuntime(None, None, None)
    state = create_initial_liuyao_state("测试")

    state["reflection"] = DecisionReflection(
        situation_summary="测试情境",
        traditional_reflection="某传统解释。[Evidence 3] 这句话越界了。",
        reality_check="现实条件优先",
        decision_options=["继续收集信息"],
        uncertainty_note="仅作文化反思参考",
    )

    state["citations"] = [Citation(chunk_id="1", document_id="1", source_title="测试来源", section="测试章节")]

    with pytest.raises(LiuyaoPolicyError, match="不存在的 Evidence"):
        runtime.finalize_node(state)


@pytest.mark.asyncio
async def test_retrieve_node_success_path_mappings(mock_deps):
    """验证 retrieve_node 正确转换 RetrievalResult -> Context & Citations"""
    caster, llm, retrieval_builder = mock_deps
    runtime = LiuyaoAgentRuntime(caster, llm, retrieval_builder)

    state = create_initial_liuyao_state("测试映射")
    state["question"] = rebuild_question(state["question"], status=DecisionQuestionStatus.CONFIRMED, clarified_question="正式的已确认问题")
    state["confirmed"] = True
    state["hexagram"] = create_dummy_hexagram()  # 使用真实的 Dummy Hexagram

    mock_res1 = RetrievalResult(
        rank=1,
        chunk_id="chunkA",
        document_id="doc1",
        domain=KnowledgeDomain.LIUYAO,
        source_title="Book A",
        source_type=SourceType.PUBLIC_DOMAIN_CLASSIC,
        section="S1",
        text="Txt",
        rrf_score=0.9,
        rrf_rank=1,
        reranker_score=None,
        dense_rank=1,
        sparse_rank=1,
    )
    mock_res2 = RetrievalResult(
        rank=2,
        chunk_id="chunkB",
        document_id="doc1",
        domain=KnowledgeDomain.LIUYAO,
        source_title="Book A",
        source_type=SourceType.PUBLIC_DOMAIN_CLASSIC,
        section="S2",
        text="Txt",
        rrf_score=0.8,
        rrf_rank=2,
        reranker_score=None,
        dense_rank=2,
        sparse_rank=2,
    )
    retrieval_builder.retrieve.return_value = [mock_res1, mock_res2]

    out = await runtime.retrieve_node(state)

    # 验证透传原文
    assert len(out["retrieved_context"]) == 2
    assert out["retrieved_context"][0] == mock_res1

    # 验证 Citation 映射顺序
    assert len(out["citations"]) == 2
    assert out["citations"][0].chunk_id == "chunkA"
    assert out["citations"][1].chunk_id == "chunkB"


@pytest.mark.asyncio
async def test_full_runtime_integration(mock_deps):
    """验证整张 LangGraph 的完整串联：Pause -> Resume -> Tool -> Retrieve -> LLM -> Finalize"""
    caster, llm, retrieval_builder = mock_deps

    # --- Mocks ---
    dummy_hex = create_dummy_hexagram()
    caster.cast_random.return_value = dummy_hex  # 注入真实的 HexagramResult

    # 第一次 LLM 返回澄清问题，第二次 LLM 返回解释草稿
    llm.generate_structured.side_effect = [
        ClarificationAssessment(needs_clarification=False, clarified_question="未来一周可否跳槽？", reality_constraints=["房贷"]),
        DecisionReflection(
            situation_summary="现状", traditional_reflection="推演", reality_check="现实", decision_options=["方向A"], uncertainty_note="玄学参考"
        ),
    ]

    retrieval_builder.retrieve.return_value = []  # 模拟未查到资料的边界

    runtime = LiuyaoAgentRuntime(caster, llm, retrieval_builder)
    graph = runtime.build_graph()
    config = {"configurable": {"thread_id": "test_e2e_runtime"}}

    # --- Step 1: Execute till Pause ---
    initial_state = create_initial_liuyao_state("该跳槽吗？")
    await graph.ainvoke(initial_state, config)

    paused_state = graph.get_state(config)
    assert paused_state.next == ("confirmation",)
    assert paused_state.values["question"].status == DecisionQuestionStatus.PENDING_CONFIRMATION

    # --- Step 2: Resume with Confirm ---
    resume_cmd = Command(resume={"action": "confirm"})
    await graph.ainvoke(resume_cmd, config)

    final_state = graph.get_state(config)

    # --- Asserts ---
    assert len(final_state.next) == 0  # 到达 END
    assert final_state.values["question"].status == DecisionQuestionStatus.CONFIRMED
    assert final_state.values["hexagram"] == dummy_hex
    assert "### 【决策参考】" in final_state.values["final_response"]
    assert "- 方向A" in final_state.values["final_response"]

    # Tool and LLM Call count validation
    assert caster.cast_random.call_count == 1
    assert llm.generate_structured.call_count == 2
