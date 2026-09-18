"""Stage 7 full-chain Router gate. Rules-only is diagnostic and never passes the gate."""

import argparse
import asyncio
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from guanchen_v2.config.settings import Settings
from guanchen_v2.llm.client import LLMClient
from guanchen_v2.router.contracts import IntentType, RequiredDataType
from guanchen_v2.router.core import HighPrecisionRuleRouter, TwoLayerIntentRouter, build_routing_result

GOLDEN_FILE = Path("evals/router/stage7_router_golden.json")
REPORT_FILE = Path("evals/router/stage7_router_report.json")
FAILURES_FILE = Path("evals/router/stage7_router_failures.jsonl")
ACCURACY_GATE = 0.92
MIN_GOLDEN_CASES = 60
MIN_DUAL_OR_AMBIGUOUS = 10


def load_golden():
    cases = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    for case in cases:
        IntentType(case["primary_intent"])
        for intent in case.get("secondary_intents", []):
            IntentType(intent)
    return cases


async def evaluate(cases, *, rules_only=False, router=None):
    settings = None
    if not rules_only and router is None:
        settings = Settings()  # same env-file/prefix as the application; no silent fallback
        router = TwoLayerIntentRouter(HighPrecisionRuleRouter(), LLMClient.from_settings(settings))
    rules = HighPrecisionRuleRouter()
    predictions, failures, violations = [], [], []
    primary_correct = secondary_correct = covered = 0
    rule_hits = 0
    for case in cases:
        rule = rules.match(case["query"])
        rule_hits += int(rule is not None)
        if rules_only and rule is None:
            predictions.append({"id": case["id"], "status": "not_evaluated"})
            continue
        try:
            result = build_routing_result(rule) if rules_only else await router.route(case["query"])
            primary = result.primary_intent.value
            secondary = [intent.value for intent in result.secondary_intents]
            primary_ok = primary == case["primary_intent"]
            secondary_ok = secondary == case.get("secondary_intents", [])
            primary_correct += int(primary_ok)
            secondary_correct += int(secondary_ok)
            covered += 1
            row = {
                "id": case["id"],
                "status": "evaluated",
                "primary_intent": primary,
                "secondary_intents": secondary,
                "required_data": [x.value for x in result.required_data],
                "primary_correct": primary_ok,
                "secondary_correct": secondary_ok,
            }
            predictions.append(row)
            if not primary_ok or not secondary_ok:
                failures.append({**row, "expected_primary": case["primary_intent"], "expected_secondary": case.get("secondary_intents", [])})
            if (
                case["primary_intent"] in {"knowledge", "dream"}
                and not case.get("secondary_intents")
                and RequiredDataType.BIRTH_PROFILE in result.required_data
            ):
                violations.append(row)
        except Exception as exc:
            row = {"id": case["id"], "status": "error", "error_type": type(exc).__name__}
            predictions.append(row)
            failures.append(row)
    total = len(cases)
    checks = {
        "full_chain": not rules_only,
        "golden_size_ok": total >= MIN_GOLDEN_CASES,
        "six_intents_ok": {c["primary_intent"] for c in cases} == {i.value for i in IntentType},
        "dual_or_ambiguous_ok": sum(c.get("category") in {"explicit_dual", "ambiguous"} for c in cases) >= MIN_DUAL_OR_AMBIGUOUS,
        "all_evaluated": covered == total,
        "accuracy_ok": primary_correct / total >= ACCURACY_GATE,
        "no_birth_profile_violation": not violations,
    }
    return {
        "frozen_contract": "Stage 7 Router Eval",
        "mode": "rules_only" if rules_only else "full_chain",
        "accuracy_gate": ACCURACY_GATE,
        "total": total,
        "evaluated": covered,
        "correct": primary_correct,
        "accuracy": None if rules_only else primary_correct / total,
        "secondary_accuracy": None if rules_only else secondary_correct / total,
        "rule_covered": rule_hits,
        "rule_coverage": rule_hits / total,
        "rule_layer_accuracy": primary_correct / covered if rules_only and covered else None,
        "llm_fallback_needed": total - rule_hits,
        "checks": checks,
        "passed": all(checks.values()),
        "birth_profile_check": {"checked": not rules_only, "violations": violations},
        "failures": failures,
        "predictions": predictions,
        "model": settings.deepseek_model if settings else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    }


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules-only", action="store_true")
    args = parser.parse_args()
    report = await evaluate(load_golden(), rules_only=args.rules_only)
    path = REPORT_FILE.with_name("stage7_router_rules_report.json") if args.rules_only else REPORT_FILE
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.rules_only:
        FAILURES_FILE.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in report["failures"]), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("mode", "total", "evaluated", "accuracy", "secondary_accuracy", "passed")}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
