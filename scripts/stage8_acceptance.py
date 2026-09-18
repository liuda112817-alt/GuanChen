"""Stage 1-8 live acceptance through the production assembly (synthetic inputs only)."""

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from guanchen_v2.application.factory import open_application
from guanchen_v2.config.settings import Settings
from guanchen_v2.memory.selector import MemorySelector

PROFILE = dict(year=1992, month=8, day=18, hour=10, minute=0, gender="male")
OUT = Path("evals/acceptance/stage8_live_report.json")
KNOWLEDGE = [
    "什么是八字",
    "正官是什么意思",
    "正印是什么意思",
    "五行相生的顺序是什么",
    "天干和地支有什么区别",
    "六爻中的世应是什么",
    "动爻是什么意思",
    "阴阳是什么",
    "十神是什么意思",
    "周易和六爻有什么区别",
]
DREAM = [
    "我昨晚梦见在河边和爸爸散步，水很清，感觉轻松，请解释这个梦。",
    "补充现实背景：最近工作压力很大，常常加班。",
    "补充梦中人物：妈妈后来也来了，和我们一起散步。",
    "更正一下，不是爸爸，是哥哥和我散步。",
    "然后呢",
    "换一个梦：我在山上独自飞翔，感觉非常自由。",
]
DUAL = [
    "结合我的八字和昨晚的梦一起看，我梦见在海边散步，感觉平静，想了解事业方向。",
    "结合我的八字和昨晚的梦一起分析，我梦见在山上走路，感觉轻松，想了解工作状态。",
    "结合我的八字和昨晚的梦一起解读，我梦见在家里看书，感觉温暖，想了解关系相处。",
    "结合我的八字和昨晚的梦综合看，我梦见朋友来家里吃饭，感觉开心，想了解人际关系。",
    "结合我的八字和昨晚的梦一起参考，我梦见在田野散步，感觉平静，想了解近期状态。",
]


async def main():
    prefix = "acceptance-" + uuid.uuid4().hex[:8]
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "synthetic_inputs": True, "cases": [], "checks": {}}
    OUT.parent.mkdir(parents=True, exist_ok=True)

    def save():
        OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    async def turn(app, label, session, query, **kwargs):
        try:
            result = await app.execute(prefix + session, query, **kwargs)
            report["cases"].append({"id": label, "query": query, "response": result.model_dump(mode="json")})
            print(label, result.status, len(result.citations), flush=True)
            save()
            return result
        except Exception as exc:
            report["cases"].append({"id": label, "error_type": type(exc).__name__})
            save()
            raise

    async with open_application(Settings()) as app:
        for index, query in enumerate(KNOWLEDGE):
            await turn(app, f"knowledge-{index + 1}", "-knowledge", query, new_task=True)
        first = await turn(app, "bazi-missing", "-bazi", "我的八字事业怎么样")
        partial = {key: value for key, value in PROFILE.items() if key not in {"hour", "gender"}}
        await turn(app, "bazi-partial", "-bazi", "补充部分出生资料", birth_patch=partial)
        await turn(app, "bazi-hour", "-bazi", "补充出生时间", birth_patch={"hour": 10})
        await turn(app, "bazi-complete", "-bazi", "补充性别", birth_patch={"gender": "male"})
        await turn(app, "bazi-correction", "-bazi", "我的八字感情怎么样", birth_patch={"hour": 16, "minute": 30})
        ids = []
        for index, query in enumerate(DREAM):
            await turn(app, f"dream-{index + 1}", "-dream", query)
            record = await MemorySelector(app.session_factory).load_dream_memory(prefix + "-dream")
            ids.append(str(record.dream_id))
            report["cases"][-1]["dream_state"] = record.model_dump(mode="json")
            save()
        report["checks"]["same_dream_first_five"] = len(set(ids[:5])) == 1
        report["checks"]["new_dream_sixth"] = ids[5] != ids[4]
        start = await turn(app, "liuyao-start", "-liuyao", "帮我起一卦，未来三个月是否接受新公司的工程师职位？收入增加但通勤更远。")
        report["checks"]["interrupt_before_cast"] = start.status == "interrupted"
        await turn(app, "liuyao-negative", "-liuyao", "我不确认，取消")
        decision = await MemorySelector(app.session_factory).load_decision_memory(prefix + "-liuyao")
        report["checks"]["negative_no_cast"] = decision.hexagram is None and decision.status.value == "cancelled"
        await turn(app, "liuyao-restart-start", "-resume", "帮我起一卦，未来三个月是否接受新公司的工程师职位？收入增加但通勤更远。")
        for index, query in enumerate(DUAL):
            result = await turn(app, f"dual-{index + 1}", f"-dual-{index}", query, birth_patch=PROFILE)
            report["checks"][f"dual-{index + 1}-two-intents"] = len(result.used_intents) == 2
        report["checks"]["birth_requires_input"] = first.status == "needs_input"
    # Destroy engine / pool / runtimes and build the real application again.
    async with open_application(Settings()) as rebuilt:
        resumed = await turn(rebuilt, "liuyao-after-rebuild", "-resume", "确认")
        report["checks"]["resume_completed"] = resumed.status == "answered"
        await turn(rebuilt, "bazi-after-rebuild", "-bazi", "我的八字事业怎么样")
        record = await MemorySelector(rebuilt.session_factory).load_birth_profile(prefix + "-bazi")
        report["checks"]["corrected_profile_recovered"] = record.hour == 16 and record.minute == 30
        await turn(rebuilt, "dream-after-rebuild", "-dream", "然后呢")
        record = await MemorySelector(rebuilt.session_factory).load_dream_memory(prefix + "-dream")
        report["checks"]["dream_recovered"] = str(record.dream_id) == ids[-1]
    report["passed"] = all(report["checks"].values())
    save()
    print("passed=", report["passed"])


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
