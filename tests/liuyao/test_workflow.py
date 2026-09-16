from unittest.mock import MagicMock

import pytest
from langgraph.types import Command

from guanchen_v2.liuyao.exceptions import LiuyaoPolicyError
from guanchen_v2.liuyao.policy import rebuild_question
from guanchen_v2.liuyao.state import create_initial_liuyao_state
from guanchen_v2.liuyao.workflow import LiuyaoAgentRuntime
from guanchen_v2.models.liuyao import CastingMethod, DecisionQuestionStatus, LineValue


@pytest.fixture
def mock_caster():
    caster = MagicMock()
    caster.cast_random.return_value = "fake_hexagram_result"
    caster.cast_manual.return_value = "fake_manual_hexagram"
    return caster


def test_cast_node_guard_blocks_unconfirmed(mock_caster):
    """1. 验证 cast_node() 独立防御：即使绕过路由，也会因 can_cast 失败死死防住。"""
    runtime = LiuyaoAgentRuntime(casting_service=mock_caster)
    state = create_initial_liuyao_state("测试直接进入 cast")

    with pytest.raises(LiuyaoPolicyError, match="未就绪或未通过用户确认"):
        runtime.cast_node(state)

    assert mock_caster.cast_random.call_count == 0


def test_cast_node_allows_confirmed(mock_caster):
    """2. 验证 cast_node() 对完全合法的已确认状态放行，并直接调用 Tool。"""
    runtime = LiuyaoAgentRuntime(casting_service=mock_caster)
    state = create_initial_liuyao_state("合法进入")

    q = rebuild_question(
        state["question"],
        clarified_question="被用户彻底确认的问题",
        status=DecisionQuestionStatus.CONFIRMED,
    )
    state["question"] = q
    state["confirmed"] = True

    result = runtime.cast_node(state)
    assert mock_caster.cast_random.call_count == 1
    assert result["hexagram"] == "fake_hexagram_result"


def test_workflow_confirmation_interrupt_and_resume_confirm(mock_caster):
    """3. 验证 Graph 中断契约及确认后调用起卦服务。"""
    runtime = LiuyaoAgentRuntime(casting_service=mock_caster)

    def mock_clarify(state):
        q = rebuild_question(
            state["question"],
            clarified_question="未来一周是否该跳槽？",
            reality_constraints=["薪资要求"],
            status=DecisionQuestionStatus.PENDING_CONFIRMATION,
        )
        return {"question": q, "pending_user_input": None}

    runtime.clarify_node = mock_clarify
    graph = runtime.build_graph()
    config = {"configurable": {"thread_id": "test_confirm"}}
    state = create_initial_liuyao_state("跳槽？")

    # [首次执行] 触发流程，将被 interrupt() 挂起
    graph.invoke(state, config)
    current_state = graph.get_state(config)

    assert current_state.next == ("confirmation",)

    interrupt_payload = current_state.tasks[0].interrupts[0].value
    assert interrupt_payload["type"] == "liuyao_confirmation"
    assert interrupt_payload["question"] == "未来一周是否该跳槽？"
    assert interrupt_payload["reality_constraints"] == ["薪资要求"]
    assert "confirm" in interrupt_payload["allowed_actions"]

    assert mock_caster.cast_random.call_count == 0

    # [外部恢复]
    resume_cmd = Command(resume={"action": "confirm"})
    final_state = graph.invoke(resume_cmd, config)

    assert mock_caster.cast_random.call_count == 1
    assert final_state["question"].status == DecisionQuestionStatus.CONFIRMED
    assert final_state["hexagram"] == "fake_hexagram_result"


def test_workflow_resume_modify_preserves_user_input_and_routes(mock_caster):
    """4. 验证 MODIFY 保留用户修改内容，并在 Clarify 被消费后产生新候选问题重新挂起等待确认。"""
    runtime = LiuyaoAgentRuntime(casting_service=mock_caster)

    def mock_clarify(state):
        if state.get("pending_user_input"):
            runtime.test_captured_input = state["pending_user_input"]
            q = rebuild_question(
                state["question"],
                clarified_question="测事业？",
                status=DecisionQuestionStatus.PENDING_CONFIRMATION,
            )
            # LLM 消费完毕，清空
            return {"question": q, "pending_user_input": None}

        q = rebuild_question(
            state["question"],
            clarified_question="初始候选问题",
            status=DecisionQuestionStatus.PENDING_CONFIRMATION,
        )
        return {"question": q}

    runtime.clarify_node = mock_clarify
    graph = runtime.build_graph()
    config = {"configurable": {"thread_id": "test_modify"}}

    graph.invoke(create_initial_liuyao_state("测感情"), config)

    # [外部恢复] MODIFY 并带修改意见
    resume_cmd = Command(resume={"action": "modify", "modification": "别测感情了，改测事业吧。"})
    graph.invoke(resume_cmd, config)

    current_state = graph.get_state(config)

    # 验证新问题必须重新挂起确认（不可直接起卦）
    assert current_state.next == ("confirmation",)
    assert current_state.values["question"].status == DecisionQuestionStatus.PENDING_CONFIRMATION
    assert current_state.values["question"].clarified_question == "测事业？"

    # 验证 pending_user_input 在 clarify 节点确实被消费/清空了
    assert current_state.values["pending_user_input"] is None

    # 验证修改后工具仍未调用
    assert mock_caster.cast_random.call_count == 0
    assert getattr(runtime, "test_captured_input", None) == "别测感情了，改测事业吧。"


def test_workflow_resume_cancel_routes_to_end(mock_caster):
    """5. 验证 CANCEL 切断流向 END。"""
    runtime = LiuyaoAgentRuntime(casting_service=mock_caster)

    def mock_clarify(state):
        q = rebuild_question(
            state["question"],
            clarified_question="初始候选问题",
            status=DecisionQuestionStatus.PENDING_CONFIRMATION,
        )
        return {"question": q}

    runtime.clarify_node = mock_clarify
    graph = runtime.build_graph()
    config = {"configurable": {"thread_id": "test_cancel"}}

    graph.invoke(create_initial_liuyao_state("算卦"), config)

    # [外部恢复]
    resume_cmd = Command(resume={"action": "cancel"})
    graph.invoke(resume_cmd, config)

    current_state = graph.get_state(config)
    assert len(current_state.next) == 0
    assert current_state.values["question"].status == DecisionQuestionStatus.CANCELLED
    assert mock_caster.cast_random.call_count == 0


def test_cast_node_dispatches_manual_cast(mock_caster):
    """6. 验证 Task 2 的 Manual Six Lines 正确分发"""
    runtime = LiuyaoAgentRuntime(casting_service=mock_caster)
    state = create_initial_liuyao_state("测试手工起卦")

    state["question"] = rebuild_question(
        state["question"],
        clarified_question="已确认的问题",
        status=DecisionQuestionStatus.CONFIRMED,
    )
    state["confirmed"] = True
    state["casting_method"] = CastingMethod.MANUAL_SIX_LINES
    state["manual_lines"] = (
        LineValue.YOUNG_YANG,
        LineValue.YOUNG_YANG,
        LineValue.YOUNG_YANG,
        LineValue.YOUNG_YANG,
        LineValue.YOUNG_YANG,
        LineValue.YOUNG_YANG,
    )

    runtime.cast_node(state)

    assert mock_caster.cast_manual.call_count == 1
    assert mock_caster.cast_random.call_count == 0
