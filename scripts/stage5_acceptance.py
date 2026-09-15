import asyncio
import json

from rich.console import Console

# 请根据你项目的实际路径调整导入
from guanchen_v2.config.settings import Settings
from guanchen_v2.dream.context import DreamContextService
from guanchen_v2.dream.extractor import DreamExtractor
from guanchen_v2.dream.retrieval import DreamRetrievalService
from guanchen_v2.dream.runtime import DreamAgentRuntime, DreamAgentStatus
from guanchen_v2.llm.client import LLMClient

console = Console()


async def print_turn_result(turn_num: int, user_text: str, result, runtime: DreamAgentRuntime):
    console.print(f"\n[bold magenta]================ TURN {turn_num} ================[/bold magenta]")
    console.print(f"[bold]user_text:[/bold] {user_text}\n")

    # --- CONTEXT RESULT ---
    console.print("[bold cyan]=== CONTEXT RESULT ===[/bold cyan]")
    console.print(f"status: {result.status.value}")
    # 这里我们通过内部状态变化来判断是否新梦
    # （实际可以改造 handle_turn 让其返回 started_new_dream，目前我们观察 ID 变化即可）
    console.print("\n[bold cyan]=== STATE ===[/bold cyan]")
    record = result.record
    console.print(f"dream_id: {record.dream_id}")
    console.print(f"revision: {record.revision}")
    console.print(f"interpretation_status: {record.interpretation_state.status.value}")
    console.print(f"last_interpreted_revision: {record.interpretation_state.last_interpreted_revision}")
    console.print(
        f"elements:\n{json.dumps(record.elements.model_dump(exclude_defaults=True), ensure_ascii=False, indent=2)}"
    )
    console.print(
        f"reality_background:\n{json.dumps(record.reality_background.model_dump(exclude_defaults=True), ensure_ascii=False, indent=2)}"
    )

    if result.status == DreamAgentStatus.NEEDS_CLARIFICATION:
        console.print(
            f"\n[bold yellow]>>> NEEDS CLARIFICATION: {result.clarification_question}[/bold yellow]"
        )
        return

    # --- ANSWER / CITATIONS ---
    console.print("\n[bold green]=== ANSWER ===[/bold green]")
    console.print(f"[bold]traditional_view:[/bold]\n{result.response.traditional_view}\n")
    console.print(f"[bold]psychological_context_view:[/bold]\n{result.response.psychological_context_view}\n")

    console.print("[bold green]=== CITATIONS ===[/bold green]")
    if not result.citations:
        console.print("[] (No citations)")
    else:
        for i, c in enumerate(result.citations, 1):
            console.print(f"[{i}] {c.source_title} - {c.section} (Chunk: {c.chunk_id})")


async def run_acceptance():
    # 1. 真实系统初始化 (请替换为你真实的 RetrievalService 初始化逻辑)
    console.print("[bold yellow]正在初始化真实大模型与检索服务...[/bold yellow]")

    settings = Settings()
    llm_client = LLMClient.from_settings(settings)

    extractor = DreamExtractor(llm_client=llm_client)

    # TODO: 实例化你真实的 Stage 4 RetrievalService
    # retrieval_service_base = RetrievalService(...)
    # 为了防止你本地没有真实数据跑不起来，此处伪造一个假的，如果你有真实环境，请务必换成真实的！
    from unittest.mock import AsyncMock, MagicMock

    retrieval_service_base = MagicMock()
    retrieval_service_base.retrieve = AsyncMock(return_value=[])

    extractor = DreamExtractor(model=llm_client)
    context_service = DreamContextService(extractor=extractor)
    dream_retrieval_service = DreamRetrievalService(retrieval_service=retrieval_service_base)

    runtime = DreamAgentRuntime(
        context_service=context_service,
        retrieval_service=dream_retrieval_service,
        llm_client=llm_client,
        retrieval_filters=None,  # 如果你有合法的 Domain Filter，请传入
    )

    # 验收剧本 (连续对话)
    scenarios = [
        (
            "Scenario A (首次完整解释)",
            "我梦到自己回到小学，在一条很长的走廊里一直找不到出口，后来看到一扇红色的门。我在梦里特别害怕，醒来以后还觉得很真实。",
        ),
        ("Scenario B1 (补充人物)", "后来想起来，我以前的班主任也在走廊尽头。"),
        (
            "Scenario B2 (连续补充)",
            "还有一扇一直打不开的门。梦里我妈妈站在门边。",
        ),  # 顺便为下一个Correction铺垫“妈妈”
        ("Scenario C (明确 Correction)", "我刚才记错了，不是妈妈，是以前的班主任。"),
        ("Scenario D (现实背景补充)", "最近工作项目快到截止日期了，我现在确实压力很大。"),
        ("CONTINUE Smoke", "然后呢？"),
        ("Scenario E (模糊新梦边界)", "昨晚我又梦见自己在树林里。"),  # 预期触发 Needs Clarification
        ("Scenario F (明确切换新梦)", "换一个梦。我梦见自己在海边，看到很大的浪。"),
    ]

    for i, (name, text) in enumerate(scenarios, 1):
        console.rule(f"[bold red]{name}[/bold red]")
        result = await runtime.handle_turn(text)
        await print_turn_result(i, text, result, runtime)
        # 短暂休眠避免并发触发大模型频率限制
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(run_acceptance())
