import asyncio
import json

from rich.console import Console

from guanchen_v2.config.settings import Settings
from guanchen_v2.dream.dream_merge import merge_dream_record, start_new_dream
from guanchen_v2.dream.extractor import DreamExtractor
from guanchen_v2.llm.provider import build_chat_model

console = Console()


async def run_smoke_test():
    settings = Settings()
    base_model = build_chat_model(settings=settings)
    extractor = DreamExtractor(model=base_model)

    record = start_new_dream()

    cases = [
        {"name": "Case A - 首次描述", "text": "我梦到自己回到小学，在走廊里一直找不到出口，梦里特别害怕。"},
        {"name": "Case B - 补充人物 (Delta Extraction)", "text": "后来想起来，我妈妈也在那条走廊里。"},
        {"name": "Case C - 明确 Correction", "text": "我刚才说错了，不是妈妈，是以前的班主任。"},
        {
            "name": "Case D - Reality Background",
            "text": "最近工作项目快到截止日期了，而且我确实觉得压力很大。",
        },
    ]

    for i, case in enumerate(cases):
        console.rule(f"[bold blue]执行 {case['name']}")
        console.print(f"[bold]用户输入:[/bold] {case['text']}\n")

        # 1. 抽取 Patch
        try:
            patch = await extractor.extract(user_text=case["text"], current_record=record)
        except Exception as e:
            console.print(f"[bold red]抽取失败: {e}[/bold red]")
            break

        console.print("[bold green]>>> LLM 生成的 DreamPatch:[/bold green]")
        console.print(patch.model_dump_json(indent=2, exclude_unset=True))

        # 2. 合并 State
        record = merge_dream_record(record=record, patch=patch, raw_description_fragment=case["text"])

        console.print(
            "\n[bold yellow]>>> Merge 后的当前有效状态 (Dream Elements & Background):[/bold yellow]"
        )
        state_dump = {
            "elements": record.elements.model_dump(exclude_defaults=True),
            "reality_background": record.reality_background.model_dump(exclude_defaults=True),
        }
        console.print(json.dumps(state_dump, ensure_ascii=False, indent=2))
        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
