from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.types import Command

from guanchen_v2.agents.bazi.runtime import BaziAgentRuntime
from guanchen_v2.agents.knowledge.agent import KnowledgeAgent
from guanchen_v2.dream.runtime import DreamAgentRuntime
from guanchen_v2.liuyao.workflow import LiuyaoAgentRuntime
from guanchen_v2.models.bazi import BirthProfile, Gender
from guanchen_v2.router.adapters.bazi import BaziAgentAdapter
from guanchen_v2.router.adapters.dream import DreamAgentAdapter
from guanchen_v2.router.adapters.knowledge import KnowledgeAgentAdapter
from guanchen_v2.router.adapters.liuyao import LiuyaoAgentAdapter
from guanchen_v2.router.contracts import RequiredDataType
from guanchen_v2.router.errors import RouterDispatchError
from guanchen_v2.router.requirements import RequirementContext


@pytest.mark.asyncio
async def test_bazi_adapter_happy_path_and_invariants():
    """验证 Bazi Adapter 准确提取参数并转换为 ReadyForBazi；缺失时 fail-fast"""
    mock_runtime = AsyncMock(spec=BaziAgentRuntime)
    adapter = BaziAgentAdapter(mock_runtime)

    with pytest.raises(RouterDispatchError, match="缺少已声明可用"):
        await adapter.invoke("查事业", RequirementContext())

    with pytest.raises(RouterDispatchError, match="数据类型不合法"):
        context_wrong_type = RequirementContext(available_data={RequiredDataType.BIRTH_PROFILE: "Not A Profile Object"})
        await adapter.invoke("查事业", context_wrong_type)

    profile = BirthProfile(year=2000, month=1, day=1, hour=12, minute=0, gender=Gender.MALE)
    context_valid = RequirementContext(available_data={RequiredDataType.BIRTH_PROFILE: profile})

    await adapter.invoke("查事业", context_valid)

    mock_runtime.run.assert_awaited_once()
    ready_input = mock_runtime.run.await_args.args[0]
    assert ready_input.question == "查事业"
    assert ready_input.profile == profile


@pytest.mark.asyncio
async def test_dream_adapter_happy_path_and_invariants():
    """验证 Dream Adapter 正确校验和传递纯文本内容；缺失或类型错误时 fail-fast"""
    mock_runtime = AsyncMock(spec=DreamAgentRuntime)
    adapter = DreamAgentAdapter(mock_runtime)

    with pytest.raises(RouterDispatchError, match="缺少已声明可用"):
        await adapter.invoke("解梦", RequirementContext())

    with pytest.raises(RouterDispatchError, match="必须为非空字符串"):
        context_wrong = RequirementContext(available_data={RequiredDataType.DREAM_CONTENT: {"not": "a string"}})
        await adapter.invoke("解梦", context_wrong)

    context = RequirementContext(available_data={RequiredDataType.DREAM_CONTENT: "梦见一条大蛇"})
    await adapter.invoke("我要解梦", context)

    mock_runtime.handle_turn.assert_awaited_once_with("梦见一条大蛇")


@pytest.mark.asyncio
async def test_knowledge_adapter_bypasses_context_entirely():
    """验证 Knowledge Adapter 完全忽略 Context 数据"""
    mock_agent = AsyncMock(spec=KnowledgeAgent)
    adapter = KnowledgeAgentAdapter(mock_agent)

    dirty_context = RequirementContext(available_data={RequiredDataType.BIRTH_PROFILE: "八字机密数据"})

    await adapter.invoke("什么是正印", dirty_context)
    mock_agent.answer.assert_awaited_once_with("什么是正印")


@pytest.mark.asyncio
async def test_liuyao_adapter_preserves_resume_handle():
    """验证 Liuyao Adapter 初次唤醒能透出含 thread_id 的句柄，且外部可通过同句柄接力 resume"""
    mock_runtime = MagicMock(spec=LiuyaoAgentRuntime)
    mock_graph = AsyncMock()

    # 定义两次 graph ainvoke 的返回：第一次遇到 interrupt，第二次恢复执行完返回 done
    mock_graph.ainvoke.side_effect = [
        {"__interrupt__": ["pending"]},
        {"final_response": "done"},
    ]
    mock_runtime.build_graph.return_value = mock_graph

    adapter = LiuyaoAgentAdapter(mock_runtime)

    context = RequirementContext(available_data={RequiredDataType.DECISION_QUESTION: "我该辞职吗"})

    # 第一次 Invoke 停在打断点，暴露出句柄
    first_result = await adapter.invoke("帮我起一卦", context)

    assert mock_graph.ainvoke.call_count == 1
    assert first_result.thread_id.startswith("liuyao_thread_")

    # 第二次直接基于刚才截获的 thread_id 和外部构造的 payload 进行 resume 接力
    resumed_result = await adapter.resume(first_result.thread_id, {"action": "confirm"})

    assert mock_graph.ainvoke.call_count == 2

    # 精确拦截并断言：第二次 ainvoke 时传入了准确无误的 Command 和同个 Thread ID Config
    resume_command = mock_graph.ainvoke.await_args_list[1].args[0]
    resume_config = mock_graph.ainvoke.await_args_list[1].args[1]

    assert isinstance(resume_command, Command)
    assert resume_command.resume == {"action": "confirm"}
    assert resume_config["configurable"]["thread_id"] == first_result.thread_id

    # 断言确实拿到了完成后的最终状态
    assert resumed_result == {"final_response": "done"}
