from pydantic import ValidationError

from guanchen_v2.agents.bazi.exceptions import BaziAgentError
from guanchen_v2.agents.bazi.models import (
    BaziAgentInput,
    BaziAgentResult,
    BaziBirthDataPatch,
    InvalidBaziInput,
    MissingField,
    NeedUserInput,
)
from guanchen_v2.agents.bazi.runtime import BaziAgentRuntime
from guanchen_v2.agents.bazi.session import BaziTaskSession
from guanchen_v2.config.settings import Settings

FIELD_PROMPTS = {
    MissingField.YEAR: "请输入出生年份 (例 1998) > ",
    MissingField.MONTH: "请输入出生月份 (1-12) > ",
    MissingField.DAY: "请输入出生日期 (1-31) > ",
    MissingField.HOUR: "请输入出生小时 (0-23) > ",
    MissingField.MINUTE: "请输入出生分钟 (0-59) > ",
    MissingField.GENDER: "请输入性别 (male/female) > ",
}


def run_cli():
    print("========================================")
    print("        GuanChen Bazi CLI")
    print("========================================")

    question = input("\n请描述你想咨询的问题。出生年月日等资料稍后会单独收集。\n>")
    try:
        initial_input = BaziAgentInput(question=question)
    except ValidationError:
        print("初始输入无效")
        return

    print("\n 系统初始化与排盘引擎加载中...")
    settings = Settings()
    runtime = BaziAgentRuntime(settings=settings)
    session = BaziTaskSession(initial_input=initial_input, runtime=runtime)

    result = session.evaluate()

    while True:
        if isinstance(result, BaziAgentResult):
            print("\n========================================")
            print(" 排盘与解读已完成")
            print("========================================")
            print(f"【原问题】: {result.question}")
            print(f"【日主等权威事实】: {result.chart.day_master.value}")
            print(f"\n【大模型结构化命理解释】\n{result.answer}\n")
            break

        elif isinstance(result, NeedUserInput):
            print(f"\n [系统提示] 出生资料不完整，请继续补充 (针对问题: '{result.original_question}')")
            patch_kwargs = {}
            for field in result.missing_fields:
                prompt_str = FIELD_PROMPTS.get(field, f"请输入 {field}: ")
                val = input(prompt_str).strip()
                if val:
                    patch_kwargs[field] = val

            try:
                patch = BaziBirthDataPatch(**patch_kwargs)
                result = session.supplement(patch=patch)
            except ValidationError:
                print("字段输入校验失败，请检查并重新输入")
                continue

        elif isinstance(result, InvalidBaziInput):
            print(f"\n [系统提示] {result.reason}")
            print("请修正出生资料（输入新值覆盖，回车跳过）。")

            patch_kwargs = {}
            patch_kwargs["year"] = input("修改年份 > ").strip() or None
            patch_kwargs["month"] = input("修改月份 > ").strip() or None
            patch_kwargs["day"] = input("修改日期 > ").strip() or None

            patch_kwargs = {k: v for k, v in patch_kwargs.items() if v is not None}

            try:
                patch = BaziBirthDataPatch(**patch_kwargs)
                result = session.supplement(patch=patch)
            except ValidationError:
                print("字段输入校验失败")
                continue


if __name__ == "__main__":
    try:
        run_cli()
    except KeyboardInterrupt:
        print("\n\n 会话已终止。")
    except BaziAgentError:
        print("\n\n Agent错误")
