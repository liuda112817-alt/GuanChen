"""One command, fresh evidence, fail-closed stage gates; no SaaS dependency."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def verdict(phases, router, retrieval, e2e, mcp):
    return {
        "all_commands_completed": {p.get("name") for p in phases} == {"regression", "integration", "mcp", "router", "retrieval", "e2e"}
        and all(p["returncode"] == 0 for p in phases),
        "router": router.get("passed") is True and router.get("mode") == "full_chain",
        "retrieval": retrieval.get("query_count", 0) >= 45
        and retrieval.get("rrf", {}).get("recall_at_5", 0) >= 0.85
        and all(retrieval.get("domain_metrics", {}).get(d, {}).get("rrf", {}).get("recall_at_5", 0) >= 0.8 for d in ("bazi", "dream", "yijing")),
        "mcp": mcp.get("passed") is True and len(mcp.get("tools", {})) == 3,
        "end_to_end": e2e.get("total", 0) >= 20 and e2e.get("completion_rate", 0) >= 0.95,
        "cost_observed": bool(e2e.get("routes"))
        and all(
            r.get("unknown_token_calls", 1) == 0 and r["model_calls_max"] <= r["model_call_limit"] and r["tool_calls_max"] <= r["tool_call_limit"]
            for r in e2e.get("routes", {}).values()
        ),
    }


def test_counts(path, prefix=None):
    if not path.exists():
        return {"total": 0, "passed": 0, "failed": 0, "skipped": 0}
    cases = [c for c in ET.parse(path).iter("testcase") if not prefix or c.get("classname", "").startswith(prefix)]
    failed = sum(c.find("failure") is not None or c.find("error") is not None for c in cases)
    skipped = sum(c.find("skipped") is not None for c in cases)
    return {"total": len(cases), "passed": len(cases) - failed - skipped, "failed": failed, "skipped": skipped}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/stage10_baseline")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    phases = []
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    definitions = [
        ("regression", ["-m", "pytest", "-q", f"--junitxml={output / 'regression.xml'}"], None),
        ("integration", ["-m", "pytest", "-m", "integration", "-q", f"--junitxml={output / 'integration.xml'}"], None),
        ("mcp", ["scripts/smoke/smoke_mcp.py"], ROOT / "reports/mcp_smoke.json"),
        ("router", ["scripts/eval_router.py"], ROOT / "evals/router/stage7_router_report.json"),
        ("retrieval", ["scripts/eval_retrieval.py", "--skip-reranker"], ROOT / "evals/retrieval/stage4_retrieval_report.json"),
        ("e2e", ["-m", "guanchen_v2.evaluation.end_to_end", str(output / "e2e.json")], None),
    ]
    for name, command, source in definitions:
        started = datetime.now(timezone.utc)
        print(f"Running {name}; log: {output / (name + '.log')}", flush=True)
        with (output / f"{name}.log").open("w", encoding="utf-8") as log:
            try:
                code = subprocess.run([sys.executable, *command], cwd=ROOT, env=env, stdout=log, stderr=log, timeout=3600).returncode
            except subprocess.TimeoutExpired:
                code = 124
        phases.append(
            {
                "name": name,
                "returncode": code,
                "started_at": started.isoformat(),
                "duration_seconds": (datetime.now(timezone.utc) - started).total_seconds(),
            }
        )
        # Copy only reports written by this invocation; never approve from stale artifacts.
        if source is not None:
            target = output / f"{name}.json"
            if source.exists() and source.stat().st_mtime >= started.timestamp():
                shutil.copyfile(source, target)
            else:
                target.write_text("{}", encoding="utf-8")
        print(f"{name}: exit {code}", flush=True)
    router, retrieval, e2e, mcp = [read_json(output / f"{name}.json") for name in ("router", "retrieval", "e2e", "mcp")]
    checks = verdict(phases, router, retrieval, e2e, mcp)
    hashes = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((ROOT / "evals").rglob("*.json"))
        if "golden" in p.name or p.name == "stage10_cases.json"
    }
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "working_tree_diff_sha256": hashlib.sha256(subprocess.check_output(["git", "diff", "HEAD"], cwd=ROOT)).hexdigest(),
        "dataset_sha256": hashes,
        "phases": phases,
        "checks": checks,
        "passed": all(checks.values()),
        "regression": test_counts(output / "regression.xml"),
        "integration": test_counts(output / "integration.xml"),
        "bazi_fixtures": test_counts(output / "regression.xml", "tests.bazi.test_bazi_fixtures"),
        "liuyao_fixtures_and_hitl": test_counts(output / "regression.xml", "tests.liuyao"),
        "router_accuracy": router.get("accuracy"),
        "router_secondary_accuracy": router.get("secondary_accuracy"),
        "rag_recall_at_5": retrieval.get("rrf", {}).get("recall_at_5"),
        "e2e_completion_rate": e2e.get("completion_rate"),
        "provider_network_errors": e2e.get("provider_network_errors"),
        "routes": e2e.get("routes", {}),
        "reranker_enabled": False,
    }
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Stage 1–10 evaluation baseline",
        "",
        f"Generated: {report['generated_at']}",
        "",
        f"Gate: **{'PASS' if report['passed'] else 'FAIL'}**",
        "",
        "| Check | Passed |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v} |" for k, v in checks.items()]
    lines += [
        "",
        f"Router accuracy: {report['router_accuracy']}; secondary: {report['router_secondary_accuracy']}",
        f"RAG Recall@5: {report['rag_recall_at_5']}",
        f"Bazi fixtures: {report['bazi_fixtures']}",
        f"Liuyao fixtures / HITL: {report['liuyao_fixtures_and_hitl']}",
        f"E2E completion: {report['e2e_completion_rate']}; provider network errors: {report['provider_network_errors']}",
        "",
        "Token cost is measured in provider tokens; monetary pricing is not assumed.",
        "",
        "| Route | Turns | Model calls max / limit | Tools max / limit | p50 ms | p95 ms | Tokens |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for route, r in report["routes"].items():
        lines.append(
            f"| {route} | {r['turns']} | {r['model_calls_max']} / {r['model_call_limit']} | "
            f"{r['tool_calls_max']} / {r['tool_call_limit']} | {r['p50_ms']} | {r['p95_ms']} | {r['token_usage']['total_tokens']} |"
        )
    lines += [
        "",
        "See e2e.json for synthetic responses, checks, trace steps and error types. See stage10_cases.json for the manual review rubric.",
        "The automated gate checks workflow and lineage; semantic answer quality requires reading the scenario outputs.",
        "Reranker stays disabled under the saved Stage 4 quality/latency decision; this command evaluates the production RRF path.",
    ]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Stage 1–10 gate: {report['passed']}; {output / 'report.md'}", flush=True)
    return 0 if report["passed"] else 1
