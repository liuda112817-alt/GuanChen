"""Application assembly acceptance: real adapters/graph/repos with deterministic model responses."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from guanchen_v2.application.factory import GuanChenApplication
from guanchen_v2.config.settings import Settings
from guanchen_v2.dream.runtime import DreamInterpretationDraft
from guanchen_v2.liuyao.policy import ClarificationAssessment
from guanchen_v2.memory.checkpointer import PostgresCheckpointerFactory
from guanchen_v2.memory.implementations.postgres import PostgresMemoryStore
from guanchen_v2.memory.selector import MemorySelector
from guanchen_v2.models.dream import DreamElements, DreamPatch, RealityBackground
from guanchen_v2.models.liuyao import DecisionReflection
from tests.conftest import TEST_DATABASE_URL

pytestmark = pytest.mark.integration


def fake_llm():
    async def generate(**kwargs):
        schema = kwargs["schema"]
        if schema == DreamPatch:
            text = kwargs["user_prompt"]
            if "工作压力" in text:
                return DreamPatch(background_additions=RealityBackground(stressors=["工作压力"]))
            return DreamPatch(element_additions=DreamElements(scenes=["海边"] if "海边" in text else ["山上"], emotions=["平静"]))
        if schema == DreamInterpretationDraft:
            return DreamInterpretationDraft(psychological_context_view="请结合现实感受反思。")
        if schema == ClarificationAssessment:
            return ClarificationAssessment(needs_clarification=False, clarified_question="是否接受新工作", reality_constraints=["收入稳定"])
        if schema == DecisionReflection:
            return DecisionReflection(
                situation_summary="工作选择",
                traditional_reflection="证据不足，不做具体传统判断",
                reality_check="比较收入和工作条件",
                decision_options=["比较后再决定"],
                uncertainty_note="仅供反思",
            )
        raise AssertionError(schema)

    return MagicMock(generate_structured=AsyncMock(side_effect=generate))


@pytest.mark.asyncio
async def test_real_factory_dream_isolation_and_liuyao_restart(db_env):
    _, factory = db_env
    settings = Settings(deepseek_api_key="test", deepseek_model="test", database_url=TEST_DATABASE_URL)
    retrieval = MagicMock(retrieve=AsyncMock(return_value=[]))
    saver_a, pool_a = await PostgresCheckpointerFactory.create(TEST_DATABASE_URL)
    try:
        app = GuanChenApplication(settings, factory, saver_a, retrieval, fake_llm())
        await app.execute("dream-a", "我梦见在海边，非常平静")
        await app.execute("dream-b", "我梦见在山上，非常平静")
        await app.execute("dream-a", "最近工作压力很大")
        selector = MemorySelector(factory)
        record_a = await selector.load_dream_memory("dream-a")
        record_b = await selector.load_dream_memory("dream-b")
        assert record_a.dream_id != record_b.dream_id
        assert record_a.elements.scenes == ["海边"]
        assert record_b.elements.scenes == ["山上"]
        assert record_a.reality_background.stressors == ["工作压力"]
        first = await app.execute("decision", "帮我起一卦，是否接受新工作")
        assert first.status == "interrupted"
        assert (await selector.load_decision_memory("decision")).hexagram is None
    finally:
        await pool_a.close()
    saver_b, pool_b = await PostgresCheckpointerFactory.create(TEST_DATABASE_URL)
    try:
        rebuilt = GuanChenApplication(settings, factory, saver_b, retrieval, fake_llm())
        resumed = await rebuilt.execute("decision", "确认")
        assert resumed.status == "answered"
        assert resumed.thread_id == first.thread_id
        record = await selector.load_decision_memory("decision")
        assert record.hexagram is not None
        assert record.final_response
        state = await PostgresMemoryStore(factory).load("decision")
        assert state.agent_states.liuyao["status"] == "COMPLETED"
        assert state.pending_interrupt is None
        await rebuilt.execute("dream-a", "然后呢")
        assert (await selector.load_dream_memory("dream-a")).dream_id == record_a.dream_id
    finally:
        await pool_b.close()


@pytest.mark.asyncio
async def test_birth_and_dual_application_roundtrip(db_env, monkeypatch):
    from guanchen_v2.agents.bazi.models import BaziAgentResult
    from guanchen_v2.bazi.adapter import LunarPythonBaziAdapter
    from guanchen_v2.router.synthesis import SynthesisDraft

    _, factory = db_env
    profiles = []

    class BaziRuntime:
        def __init__(self, *args):
            pass

        async def run(self, ready):
            profiles.append(ready.profile)
            return BaziAgentResult(
                question=ready.question, chart=LunarPythonBaziAdapter().calculate(ready.profile), answer="确定性排盘后的测试解释", citations=()
            )

    monkeypatch.setattr("guanchen_v2.application.factory.BaziAgentRuntime", BaziRuntime)
    llm = fake_llm()
    original = llm.generate_structured.side_effect

    async def generate(**kwargs):
        if kwargs["schema"] == SynthesisDraft:
            return SynthesisDraft(content="两种视角")
        return await original(**kwargs)

    llm.generate_structured.side_effect = generate
    settings = Settings(deepseek_api_key="test", deepseek_model="test", database_url=TEST_DATABASE_URL)
    retrieval = MagicMock(retrieve=AsyncMock(return_value=[]))
    saver, pool = await PostgresCheckpointerFactory.create(TEST_DATABASE_URL)
    try:
        app = GuanChenApplication(settings, factory, saver, retrieval, llm)
        await app.execute("birth-dual", "结合我的八字和昨晚的梦一起看，我梦见海边，感觉平静")
        assert (await PostgresMemoryStore(factory).load("birth-dual")).requirement_result.status == "needs_input"
        await app.execute("birth-dual", "补充资料", birth_patch=dict(year=1992, month=8, day=18, hour=10, minute=0, gender="male"))
        assert (await PostgresMemoryStore(factory).load("birth-dual")).requirement_result.status == "ready"
        rebuilt = GuanChenApplication(settings, factory, saver, retrieval, llm)
        await rebuilt.execute("birth-dual", "我的八字事业怎么样", birth_patch={"hour": 16})
        assert profiles[-1].hour == 16
        assert (await MemorySelector(factory).load_birth_profile("birth-dual")).hour == 16
        rebuilt2 = GuanChenApplication(settings, factory, saver, retrieval, llm)
        await rebuilt2.execute("birth-dual", "我的八字事业怎么样")
        assert profiles[-1].hour == 16
        assert (await rebuilt2.execute("other-user", "我的八字事业怎么样")).status == "needs_input"
    finally:
        await pool.close()
