from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from guanchen_v2.bazi.adapter import LunarPythonBaziAdapter
from guanchen_v2.models.bazi import BirthProfile
from guanchen_v2.router.contracts import IntentType
from guanchen_v2.router.dual_dispatch import AgentExecutionResult
from guanchen_v2.router.synthesis import SynthesisDraft, SynthesisInput
from guanchen_v2.router.synthesizer import AgentSynthesizer


@pytest.mark.asyncio
async def test_dual_synthesis_preserves_authoritative_chart_without_extra_llm():
    chart = LunarPythonBaziAdapter().calculate(BirthProfile(year=1992, month=8, day=18, hour=10, minute=0, gender="male"))
    llm = SimpleNamespace(generate_structured=AsyncMock(return_value=SynthesisDraft(content="combined")))
    result = await AgentSynthesizer(llm).synthesize(
        SynthesisInput(
            query="dual",
            results=(
                AgentExecutionResult(IntentType.BAZI, SimpleNamespace(answer="bazi", chart=chart, citations=())),
                AgentExecutionResult(IntentType.KNOWLEDGE, SimpleNamespace(answer="knowledge", citations=())),
            ),
        )
    )
    assert result.facts["bazi"] == chart.model_dump(mode="json")
    assert "6 年 9 个月 10 天 0 小时" in result.content
    llm.generate_structured.assert_awaited_once()
