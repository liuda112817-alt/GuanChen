from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.types import Command

from guanchen_v2.knowledge.models import KnowledgeDomain, RetrievalResult, SourceType
from guanchen_v2.liuyao.casting import HexagramCastingService
from guanchen_v2.liuyao.exceptions import LiuyaoPolicyError
from guanchen_v2.liuyao.iching_adapter import IChingPyAdapter
from guanchen_v2.liuyao.policy import (
    ClarificationAssessment,
    ConfirmationAction,
    ConfirmationResponse,
    apply_confirmation_response,
    rebuild_question,
)
from guanchen_v2.liuyao.state import create_initial_liuyao_state
from guanchen_v2.liuyao.workflow import LiuyaoAgentRuntime
from guanchen_v2.models.liuyao import (
    CastingMethod,
    CoinFace,
    DecisionQuestionStatus,
    DecisionReflection,
    HexagramIdentity,
    HexagramLine,
    HexagramResult,
    LineValue,
    YinYang,
)

# =================================================================================
# Mocks & Fixtures
# =================================================================================


@pytest.fixture
def mock_deps():
    """提供纯 Fake 的外部依赖，确保测试 100% 聚焦在流程与契约"""
    caster = MagicMock(spec=HexagramCastingService)

    # 构造合法的静卦，防止格式化器抛错
    dummy_hex = HexagramResult(
        # 【修复处】：改为 MANUAL_SIX_LINES 即可合法地跳过 coin_tosses 校验
        casting_method=CastingMethod.MANUAL_SIX_LINES,
        lines=tuple(HexagramLine(position=i, value=LineValue.YOUNG_YANG, polarity=YinYang.YANG, moving=False) for i in range(1, 7)),
        primary_hexagram=HexagramIdentity(name="否", upper_trigram="乾", lower_trigram="坤"),
    )
    caster.cast_random.return_value = dummy_hex

    llm = AsyncMock()
    # 第一次提问澄清，第二次形成解释草稿
    llm.generate_structured.side_effect = [
        ClarificationAssessment(needs_clarification=False, clarified_question="未来一周可否跳槽？", reality_constraints=["房贷压力"]),
        DecisionReflection(
            situation_summary="面临跳槽抉择",
            traditional_reflection="卦象提示[Evidence 1]要谨慎。",
            reality_check="由于房贷压力，不可裸辞。",
            decision_options=["先拿到书面 offer 再说"],
            uncertainty_note="玄学仅供参考",
        ),
    ]

    retrieval = AsyncMock()
    retrieval.retrieve.return_value = [
        RetrievalResult(
            rank=1,
            chunk_id="c1",
            document_id="d1",
            domain=KnowledgeDomain.LIUYAO,
            source_title="《增删卜易》",
            source_type=SourceType.PUBLIC_DOMAIN_CLASSIC,
            section="断跳槽",
            text="应爻生世，大吉。",
            rrf_score=0.9,
            rrf_rank=1,
            reranker_score=None,
            dense_rank=1,
            sparse_rank=1,
        )
    ]

    return caster, llm, retrieval


class DummyCoinSource:
    """仅用于填充真实 HexagramCastingService 的入参契约"""

    def toss(self) -> CoinFace:
        return CoinFace.HEAD


# =================================================================================
# Stage 6 Acceptance Tests
# =================================================================================


@pytest.mark.asyncio
async def test_A01_pause_before_confirm(mock_deps):
    """1. pause before confirm：第一次 run 停在 confirmation，未确认时 cast=0"""
    caster, llm, retrieval = mock_deps
    runtime = LiuyaoAgentRuntime(caster, llm, retrieval)
    graph = runtime.build_graph()
    config = {"configurable": {"thread_id": "a01_pause"}}

    state = create_initial_liuyao_state("我想跳槽")
    await graph.ainvoke(state, config)

    paused_state = graph.get_state(config)
    assert paused_state.next == ("confirmation",)
    assert paused_state.values["question"].status == DecisionQuestionStatus.PENDING_CONFIRMATION
    assert caster.cast_random.call_count == 0


@pytest.mark.asyncio
async def test_A02_confirm_resume(mock_deps):
    """2. confirm/resume：同 thread resume 后 cast=1，并完成 final response"""
    caster, llm, retrieval = mock_deps
    runtime = LiuyaoAgentRuntime(caster, llm, retrieval)
    graph = runtime.build_graph()
    config = {"configurable": {"thread_id": "a02_confirm"}}

    # 1. 停在确认点
    await graph.ainvoke(create_initial_liuyao_state("我想跳槽"), config)

    # 2. 发起确认
    resume_cmd = Command(resume={"action": "confirm"})
    await graph.ainvoke(resume_cmd, config)

    final_state = graph.get_state(config)

    # 图走到了尽头
    assert len(final_state.next) == 0
    # 状态是最终态
    assert final_state.values["question"].status == DecisionQuestionStatus.CONFIRMED
    # 工具被调用刚好 1 次
    assert caster.cast_random.call_count == 1
    # 输出了最终组合的文本
    final_text = final_state.values["final_response"]
    assert "由于房贷压力，不可裸辞" in final_text
    assert "[Evidence 1] 《增删卜易》 - 断跳槽" in final_text


@pytest.mark.asyncio
async def test_A03_modify_invalidates_downstream_and_re_interrupts(mock_deps):
    """
    3. modify/resume 特别关注场景：
       修改内容不丢，旧 hexagram/citations/reflection/final_response 全清；
       形成新 candidate 后仍然 cast=0，直到用户再次 CONFIRM。
    """
    caster, llm, retrieval = mock_deps

    # 准备一个“被历史调用污染过”的满载状态
    state = create_initial_liuyao_state("原问题")
    state["question"] = rebuild_question(state["question"], clarified_question="被历史污染的已确认问题", status=DecisionQuestionStatus.CONFIRMED)
    state["confirmed"] = True
    state["hexagram"] = "old_hexagram"
    state["retrieved_context"] = ["old_context"]
    state["citations"] = ["old_citation"]
    state["reflection"] = "old_reflection"
    state["final_response"] = "old_response"

    # [核心断言 1]：Policy 层面上，MODIFY 必须瞬间清空所有下游资产
    response = ConfirmationResponse(action=ConfirmationAction.MODIFY, modification="不测事业了，测感情")
    new_state = apply_confirmation_response(state, response)

    assert new_state["confirmed"] is False
    assert new_state["hexagram"] is None
    assert new_state["retrieved_context"] == []
    assert new_state["citations"] == []
    assert new_state["reflection"] is None
    assert new_state["final_response"] is None
    assert new_state["pending_user_input"] == "不测事业了，测感情"

    # [核心断言 2]：Graph 运行时再次推入新一轮
    runtime = LiuyaoAgentRuntime(caster, llm, retrieval)
    graph = runtime.build_graph()
    config = {"configurable": {"thread_id": "a03_modify"}}

    # 把清理完的状态放入 Graph 开始新一轮流转 (会触发 clarify_node)
    await graph.ainvoke(new_state, config)
    current_state = graph.get_state(config)

    # 再次挂起在 confirmation
    assert current_state.next == ("confirmation",)

    # 确认 modification 已经被 clarify 消费清空
    assert current_state.values["pending_user_input"] is None

    # 最重要：由于没走过 CONFIRM 节点，Caster 坚决不许碰
    assert caster.cast_random.call_count == 0


@pytest.mark.asyncio
async def test_A04_cancel_routes_to_end(mock_deps):
    """4. cancel/resume：END，cast=0，无 downstream"""
    caster, llm, retrieval = mock_deps
    runtime = LiuyaoAgentRuntime(caster, llm, retrieval)
    graph = runtime.build_graph()
    config = {"configurable": {"thread_id": "a04_cancel"}}

    await graph.ainvoke(create_initial_liuyao_state("测运势"), config)

    # 取消动作
    resume_cmd = Command(resume={"action": "cancel"})
    await graph.ainvoke(resume_cmd, config)

    final_state = graph.get_state(config)
    assert len(final_state.next) == 0
    assert final_state.values["question"].status == DecisionQuestionStatus.CANCELLED

    # 彻底断开，没有起卦，没有引文
    assert caster.cast_random.call_count == 0
    assert final_state.values["hexagram"] is None
    assert final_state.values["final_response"] is None


@pytest.mark.asyncio
async def test_A05_manual_fixed_fixture(mock_deps):
    """5. manual fixed fixture：固定六爻输入得到稳定本卦/变卦/装卦结构。注入真实的起卦引擎测试全连通。"""
    _, llm, retrieval = mock_deps

    # 使用真实的起卦器！
    adapter = IChingPyAdapter()
    real_caster = HexagramCastingService(adapter, DummyCoinSource())

    runtime = LiuyaoAgentRuntime(real_caster, llm, retrieval)
    graph = runtime.build_graph()
    config = {"configurable": {"thread_id": "a05_manual_fixed"}}

    # 给初始状态强制插入手工指定模式 (7,7,7,7,7,7 为纯乾卦静卦)
    state = create_initial_liuyao_state("测试手工模式流转")
    state["casting_method"] = CastingMethod.MANUAL_SIX_LINES
    state["manual_lines"] = (
        LineValue.YOUNG_YANG,
        LineValue.YOUNG_YANG,
        LineValue.YOUNG_YANG,
        LineValue.YOUNG_YANG,
        LineValue.YOUNG_YANG,
        LineValue.YOUNG_YANG,
    )

    await graph.ainvoke(state, config)

    resume_cmd = Command(resume={"action": "confirm"})
    await graph.ainvoke(resume_cmd, config)

    final_state = graph.get_state(config)
    hexagram = final_state.values["hexagram"]

    # 验证真实的起卦算法被触发，装卦信息正确留存
    assert hexagram.primary_hexagram.upper_trigram == "乾"
    assert hexagram.moving_line_positions == []


@pytest.mark.asyncio
async def test_A06_projection_and_security_gates(mock_deps):
    """6. projection/security gate：非 confirmed、投影不一致、非法 resume 都不能穿透到 cast"""
    caster, llm, retrieval = mock_deps
    runtime = LiuyaoAgentRuntime(caster, llm, retrieval)
    graph = runtime.build_graph()
    config = {"configurable": {"thread_id": "a06_security"}}

    state = create_initial_liuyao_state("测试越权")
    await graph.ainvoke(state, config)

    # 1. 发送非法的 resume payload -> Confirmation Response Schema 会阻拦并抛出 PolicyError
    resume_cmd = Command(resume={"action": "illegal_action"})
    with pytest.raises(LiuyaoPolicyError, match="无效的六爻确认响应"):
        await graph.ainvoke(resume_cmd, config)

    # 2. 直接构造破损的状态投喂给 cast_node
    broken_state = create_initial_liuyao_state("恶意穿透")
    broken_state["question"] = rebuild_question(
        broken_state["question"], clarified_question="恶意穿透的假问题", status=DecisionQuestionStatus.CONFIRMED
    )
    broken_state["confirmed"] = False  # 投影不一致！

    with pytest.raises(LiuyaoPolicyError, match="确认状态不一致"):
        runtime.cast_node(broken_state)

    broken_state["question"] = rebuild_question(
        broken_state["question"], clarified_question="恶意穿透的假问题", status=DecisionQuestionStatus.PENDING_CONFIRMATION
    )
    broken_state["confirmed"] = False

    with pytest.raises(LiuyaoPolicyError, match="未就绪或未通过用户确认"):
        runtime.cast_node(broken_state)

    # 从头到尾，假工具从未被真正调用过
    assert caster.cast_random.call_count == 0
    assert caster.cast_manual.call_count == 0
