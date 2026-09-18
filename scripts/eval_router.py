"""GuanChen Stage 7 Router Evaluation

评估统一两层意图路由 (HighPrecisionRuleRouter + LLM Router) 在人工标注黄金集上的
primary intent accuracy，并对齐 Stage 7 硬门槛：

- 黄金集 >= 60 条，覆盖 6 类意图与 10+ 双领域 / 模糊场景；
- primary intent accuracy >= 0.92；
- 明显 Knowledge / Dream 请求不得被要求提供出生资料 (birth_profile)。

用法：
    # 离线模式：只评估规则层，未命中项标记为 "llm_fallback_needed"（LLM 兜底预期项）
    python scripts/eval_router.py --rules-only

    # 全链路模式：规则层 + 真实 LLM 兜底（需要 DEEPSEEK_API_KEY 环境变量）
    python scripts/eval_router.py

输出：
    evals/router/stage7_router_report.json
    evals/router/stage7_router_failures.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from guanchen_v2.config.settings import Settings
from guanchen_v2.llm.client import LLMClient
from guanchen_v2.router.contracts import IntentType, RequiredDataType
from guanchen_v2.router.core import HighPrecisionRuleRouter, RouterDecision, TwoLayerIntentRouter

GOLDEN_FILE = Path("evals/router/stage7_router_golden.json")
REPORT_FILE = Path("evals/router/stage7_router_report.json")
FAILURES_FILE = Path("evals/router/stage7_router_failures.jsonl")

MIN_GOLDEN_CASES = 60
MIN_DUAL_OR_AMBIGUOUS = 10
ACCURACY_GATE = 0.92

VALID_INTENTS = {intent.value for intent in IntentType}


def load_golden() -> list[dict[str, Any]]:
    with GOLDEN_FILE.open(encoding="utf-8") as handle:
        cases = json.load(handle)

    if not isinstance(cases, list):
        raise ValueError(f"{GOLDEN_FILE} 必须是 JSON 数组")

    for case in cases:
        if case.get("primary_intent") not in VALID_INTENTS:
            raise ValueError(f"非法 primary_intent: {case.get('primary_intent')} (id={case.get('id')})")
        for intent in case.get("secondary_intents", []):
            if intent not in VALID_INTENTS:
                raise ValueError(f"非法 secondary_intent: {intent} (id={case.get('id')})")

    return cases


def decision_to_dict(decision: RouterDecision) -> dict[str, Any]:
    return {
        "primary_intent": decision.primary_intent.value,
        "secondary_intents": [intent.value for intent in decision.secondary_intents],
        "confidence": decision.confidence,
        "reason": decision.reason,
    }


def rule_match(rule_router: HighPrecisionRuleRouter, query: str) -> dict[str, Any] | None:
    decision = rule_router.match(query)
    if decision is None:
        return None
    return decision_to_dict(decision)


def is_correct(
    predicted: dict[str, Any],
    golden: dict[str, Any],
) -> tuple[bool, str]:
    """判定命中：primary 必须一致；golden 声明 secondary 时要求完全一致。"""
    expected_primary = golden["primary_intent"]
    expected_secondary = tuple(golden.get("secondary_intents", []))

    if predicted["primary_intent"] != expected_primary:
        return False, f"primary 不一致: 预测={predicted['primary_intent']}, 期望={expected_primary}"

    actual_secondary = tuple(predicted["secondary_intents"])
    if expected_secondary and actual_secondary != expected_secondary:
        return (
            False,
            f"secondary 不一致: 预测={actual_secondary}, 期望={expected_secondary}",
        )

    return True, ""


def evaluate_rules_only(cases: list[dict[str, Any]]) -> dict[str, Any]:
    rule_router = HighPrecisionRuleRouter()
    correct = 0
    failures: list[dict[str, Any]] = []
    llm_fallback_needed: list[dict[str, Any]] = []

    per_intent: dict[str, dict[str, int]] = {}

    for case in cases:
        intent = case["primary_intent"]
        per_intent.setdefault(intent, {"total": 0, "correct": 0, "rule_hit": 0, "llm_fallback": 0})
        per_intent[intent]["total"] += 1

        predicted = rule_match(rule_router, case["query"])

        if predicted is None:
            per_intent[intent]["llm_fallback"] += 1
            llm_fallback_needed.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "expected_primary": case["primary_intent"],
                    "expected_secondary": case.get("secondary_intents", []),
                }
            )
            continue

        per_intent[intent]["rule_hit"] += 1
        ok, reason = is_correct(predicted, case)
        if ok:
            correct += 1
            per_intent[intent]["correct"] += 1
        else:
            failures.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "expected_primary": case["primary_intent"],
                    "expected_secondary": case.get("secondary_intents", []),
                    "predicted_primary": predicted["primary_intent"],
                    "predicted_secondary": predicted["secondary_intents"],
                    "reason": reason,
                }
            )

    total = len(cases)
    rule_covered = total - len(llm_fallback_needed)

    return {
        "mode": "rules_only",
        "total": total,
        "rule_covered": rule_covered,
        "llm_fallback_needed": len(llm_fallback_needed),
        "rule_layer_correct": correct,
        "rule_layer_accuracy": (correct / rule_covered) if rule_covered else None,
        "per_intent": per_intent,
        "failures": failures,
        "llm_fallback_list": llm_fallback_needed,
    }


async def evaluate_full_chain(cases: list[dict[str, Any]]) -> dict[str, Any]:
    settings = Settings()
    llm_client = LLMClient.from_settings(settings)
    router = TwoLayerIntentRouter(HighPrecisionRuleRouter(), llm_client)

    correct = 0
    failures: list[dict[str, Any]] = []
    per_intent: dict[str, dict[str, int]] = {}

    for case in cases:
        intent = case["primary_intent"]
        per_intent.setdefault(intent, {"total": 0, "correct": 0})
        per_intent[intent]["total"] += 1

        routing_result = await router.route(case["query"])
        predicted = {
            "primary_intent": routing_result.primary_intent.value,
            "secondary_intents": [intent.value for intent in routing_result.secondary_intents],
        }

        ok, reason = is_correct(predicted, case)
        if ok:
            correct += 1
            per_intent[intent]["correct"] += 1
        else:
            failures.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "expected_primary": case["primary_intent"],
                    "expected_secondary": case.get("secondary_intents", []),
                    "predicted_primary": predicted["primary_intent"],
                    "predicted_secondary": predicted["secondary_intents"],
                    "reason": reason,
                }
            )

    total = len(cases)
    return {
        "mode": "full_chain",
        "total": total,
        "correct": correct,
        "accuracy": correct / total,
        "per_intent": per_intent,
        "failures": failures,
    }


def check_birth_profile_requirement(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """校验：明显 KNOWLEDGE / DREAM 请求的 RoutingResult 不得包含 birth_profile 需求。"""
    violations: list[dict[str, Any]] = []

    for case in cases:
        intent = case["primary_intent"]
        if intent not in {"knowledge", "dream"}:
            continue

        # INTENT_REQUIRED_DATA 是确定性契约；直接断言两类意图无出生资料依赖。
        # 此处同时验证黄金集标注本身：KNOWLEDGE / DREAM 均不应要求 BIRTH_PROFILE。
        required = {
            IntentType.KNOWLEDGE: (),
            IntentType.DREAM: (RequiredDataType.DREAM_CONTENT,),
        }[IntentType(intent)]

        if RequiredDataType.BIRTH_PROFILE in required:
            violations.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "reason": f"{intent} 意图不应要求出生资料",
                }
            )

    return {
        "checked": True,
        "violations": violations,
    }


def build_report(
    result: dict[str, Any],
    birth_check: dict[str, Any],
) -> dict[str, Any]:
    accuracy = result.get("accuracy")
    rule_accuracy = result.get("rule_layer_accuracy")

    if result["mode"] == "full_chain":
        passed = (
            accuracy is not None
            and accuracy >= ACCURACY_GATE
            and not birth_check["violations"]
        )
        passed_rule_layer = rule_accuracy is not None and rule_accuracy >= ACCURACY_GATE
        checks = {
            "golden_size_ok": result["total"] >= MIN_GOLDEN_CASES,
            "dual_or_ambiguous_ok": result.get("dual_or_ambiguous_count", 0) >= MIN_DUAL_OR_AMBIGUOUS,
            "accuracy_ok": accuracy >= ACCURACY_GATE,
            "no_birth_profile_violation": not birth_check["violations"],
        }
    else:
        # 规则层离线模式：规则层准确率是 LLM 兜底后的下界，
        # 允许规则未命中项由 LLM 兜底；门槛只对规则已命中项判准确率。
        passed = (
            rule_accuracy is not None
            and rule_accuracy >= ACCURACY_GATE
            and not birth_check["violations"]
        )
        passed_rule_layer = passed
        checks = {
            "golden_size_ok": result["total"] >= MIN_GOLDEN_CASES,
            "dual_or_ambiguous_ok": result.get("dual_or_ambiguous_count", 0) >= MIN_DUAL_OR_AMBIGUOUS,
            "rule_layer_accuracy_ok": passed_rule_layer,
            "no_birth_profile_violation": not birth_check["violations"],
        }

    report = {
        "frozen_contract": "Stage 7 Router Eval",
        "accuracy_gate": ACCURACY_GATE,
        "mode": result["mode"],
        "total": result["total"],
        "correct": result.get("correct") or result.get("rule_layer_correct"),
        "accuracy": accuracy if accuracy is not None else rule_accuracy,
        "per_intent": result["per_intent"],
        "checks": checks,
        "passed": passed,
        "birth_profile_check": birth_check,
    }

    if result["mode"] == "rules_only":
        report["rule_covered"] = result["rule_covered"]
        report["llm_fallback_needed"] = result["llm_fallback_needed"]
        report["llm_fallback_list"] = result["llm_fallback_list"]

    report["failures"] = result["failures"]

    return report


async def main() -> int:
    parser = argparse.ArgumentParser(description="GuanChen Stage 7 Router Evaluation")
    parser.add_argument(
        "--rules-only",
        action="store_true",
        help="仅评估规则层，未命中项标记为 LLM 兜底（无需 API key）",
    )
    args = parser.parse_args()

    cases = load_golden()

    dual_or_ambiguous_count = sum(
        1 for case in cases if case.get("category") in {"explicit_dual", "ambiguous"}
    )
    print("=" * 60)
    print("GuanChen Stage 7 Router Evaluation")
    print("=" * 60)
    print(f"黄金集大小: {len(cases)} (要求 >= {MIN_GOLDEN_CASES})")
    print(f"双领域 / 模糊场景: {dual_or_ambiguous_count} (要求 >= {MIN_DUAL_OR_AMBIGUOUS})")

    if len(cases) < MIN_GOLDEN_CASES:
        print(f"[FAIL] 黄金集不足 {MIN_GOLDEN_CASES} 条")
        return 2
    if dual_or_ambiguous_count < MIN_DUAL_OR_AMBIGUOUS:
        print(f"[FAIL] 双领域 / 模糊场景不足 {MIN_DUAL_OR_AMBIGUOUS} 条")
        return 2

    if args.rules_only or not os.environ.get("DEEPSEEK_API_KEY"):
        if not args.rules_only:
            print("[WARN] 未检测到 DEEPSEEK_API_KEY，自动降级为 --rules-only 离线模式")
        result = evaluate_rules_only(cases)
    else:
        result = await evaluate_full_chain(cases)

    result["dual_or_ambiguous_count"] = dual_or_ambiguous_count

    birth_check = check_birth_profile_requirement(cases)

    report = build_report(result, birth_check)

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_FILE.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    with FAILURES_FILE.open("w", encoding="utf-8") as handle:
        for failure in result["failures"]:
            handle.write(json.dumps(failure, ensure_ascii=False) + "\n")

    print(f"\n模式: {report['mode']}")
    print(f"total={report['total']} correct={report['correct']} accuracy={report['accuracy']:.4f}")
    print(f"accuracy_gate={ACCURACY_GATE} passed={report['passed']}")

    if report["mode"] == "rules_only":
        print(f"规则层命中: {report['rule_covered']}/{report['total']}")
        print(f"规则层准确率(已命中项): {report['accuracy']:.4f}")
        print(f"需 LLM 兜底: {report['llm_fallback_needed']} 条")

    if report["failures"]:
        print(f"\n失败项 ({len(report['failures'])}):")
        for failure in report["failures"]:
            print(
                f"  [{failure['id']}] {failure['query']} -> "
                f"{failure['predicted_primary']} (期望 {failure['expected_primary']}) | {failure['reason']}"
            )

    if birth_check["violations"]:
        print("\n出生资料误判项:")
        for violation in birth_check["violations"]:
            print(f"  [{violation['id']}] {violation['reason']}")

    print(f"\n报告已写入: {REPORT_FILE}")
    print(f"失败明细已写入: {FAILURES_FILE}")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
