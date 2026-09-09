from guanchen_v2.agents.bazi.models import ReadyForBazi
from guanchen_v2.agents.bazi.runtime import BaziAgentRuntime
from guanchen_v2.config.settings import Settings
from guanchen_v2.models.bazi import BirthProfile, Gender


def run_smoke():
    settings = Settings()
    runtime = BaziAgentRuntime(settings=settings)

    ready = ReadyForBazi(
        question="请从传统八字视角分析一下我的事业倾向。",
        profile=BirthProfile(year=2000, month=2, day=16, hour=7, minute=20, gender=Gender.MALE),
    )

    result = runtime.run(ready=ready)

    print(" Bazi Agent 业务结果")
    print("=" * 40)
    print(f"原问题: {result.question}")
    print(f"排盘底座日主: {result.chart.day_master.value}")
    print(f"\n大模型结构化命理解释\n{result.answer}")
    print("=" * 40)


if __name__ == "__main__":
    run_smoke()
