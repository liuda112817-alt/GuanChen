"""Fixed synthetic scenarios through the real PostgreSQL + model application."""

import asyncio
import json
import sys
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import select

from guanchen_v2.application.factory import open_application
from guanchen_v2.bazi.adapter import LunarPythonBaziAdapter
from guanchen_v2.config.settings import Settings
from guanchen_v2.knowledge.persistence.models import KnowledgeChunkRow, KnowledgeDocumentRow
from guanchen_v2.memory.selector import MemorySelector


def percentile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    index = (len(values) - 1) * fraction
    lo = int(index)
    hi = min(lo + 1, len(values) - 1)
    return round(values[lo] + (values[hi] - values[lo]) * (index - lo), 2)


def error_category(exc):
    chain = []
    while exc is not None and id(exc) not in {id(e) for e in chain}:
        chain.append(exc)
        exc = exc.__cause__
    if any(type(e).__name__ in {"LLMTransientProviderError", "APIConnectionError", "APITimeoutError"} for e in chain):
        return "provider_network"
    return "application"


def route_metrics(cases):
    groups = defaultdict(list)
    for case in cases:
        for turn in case["turns"]:
            if turn.get("trace"):
                groups[turn["trace"]["route"]].append(turn["trace"])
    result = {}
    for route, runs in groups.items():
        tokens = [step["token"] for run in runs for step in run["steps"] if step["kind"] == "LLM"]
        result[route] = {
            "turns": len(runs),
            "model_call_limit": max(r["model_call_limit"] for r in runs),
            "tool_call_limit": max(r["tool_call_limit"] for r in runs),
            "model_calls_max": max(r["model_calls"] for r in runs),
            "model_calls_total": sum(r["model_calls"] for r in runs),
            "tool_calls_max": max(r["tool_calls"] for r in runs),
            "tool_calls_total": sum(r["tool_calls"] for r in runs),
            "p50_ms": percentile([r["latency_ms"] for r in runs], 0.5),
            "p95_ms": percentile([r["latency_ms"] for r in runs], 0.95),
            "token_usage": {k: sum(t.get(k, 0) for t in tokens if t) for k in ("input_tokens", "output_tokens", "total_tokens")},
            "unknown_token_calls": sum(t is None for t in tokens),
            "errors": dict(Counter(s["error"] for r in runs for s in r["steps"] if s["error"])),
        }
    return result


async def evaluate(output: Path):
    dataset = json.loads(Path("evals/e2e/stage10_cases.json").read_text(encoding="utf-8"))
    report = {"synthetic_inputs": True, "cases": [], "passed": False}
    prefix = "stage10-" + uuid.uuid4().hex
    output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    async with open_application(Settings()) as app:
        # Authoritative lineage, not a mock providing whichever properties the adapter expects.
        async with app.session_factory() as session:
            rows = (
                await session.execute(
                    select(KnowledgeChunkRow, KnowledgeDocumentRow).join(
                        KnowledgeDocumentRow, KnowledgeChunkRow.document_id == KnowledgeDocumentRow.document_id
                    )
                )
            ).all()
            lineage = {chunk.chunk_id: (chunk.document_id, doc.source_title, chunk.section) for chunk, doc in rows}
        for case in dataset:
            entry = {"id": case["id"], "expected_route": case["route"], "manual_review": case["manual_review"], "turns": [], "passed": True}
            report["cases"].append(entry)
            previous_dream_id = None
            expected_profile = {}
            for expected in case["turns"]:
                traces = []
                app.trace_sink = traces.append
                row = {"query": expected["query"], "checks": {}}
                entry["turns"].append(row)
                try:
                    response = await app.execute(
                        prefix + "-" + case["id"],
                        expected["query"],
                        **({"birth_patch": expected["birth_patch"]} if "birth_patch" in expected else {}),
                    )
                    row["response"] = response.model_dump(mode="json")
                    trace = traces[-1]
                    row["trace"] = asdict(trace)
                    checks = row["checks"]
                    checks["status"] = response.status == expected["status"]
                    checks["route"] = set(trace.route.split("+")) == set(case["route"].split("+"))
                    checks["nonempty_response"] = bool(response.content.strip())
                    checks["bounded_calls"] = trace.model_calls <= trace.model_call_limit and trace.tool_calls <= trace.tool_call_limit
                    checks["token_observation"] = all(s.token is not None for s in trace.steps if s.kind == "LLM" and s.status == "SUCCESS")
                    retrieved = {c for s in trace.steps for c in s.retrieved_chunk_ids}
                    checks["citation_lineage"] = all(
                        c.chunk_id in retrieved and lineage.get(c.chunk_id) == (c.document_id, c.source_title, c.section) for c in response.citations
                    )
                    checks["required_citations"] = not expected.get("citations") or bool(response.citations)
                    tools = [s.tool for s in trace.steps if s.kind == "TOOL"]
                    allowed = set()
                    if "bazi" in case["route"] and response.status == "answered":
                        allowed.update(["calculate_bazi", "retrieve_bazi_knowledge"])
                        checks["chart_from_tool"] = tools.count("calculate_bazi") == 1 and bool(response.facts)
                    if "liuyao" in case["route"] and response.status == "answered":
                        allowed.add("cast_hexagram")
                        checks["cast_once"] = tools.count("cast_hexagram") == 1
                    checks["no_wrong_tools"] = set(tools) <= allowed
                    checks["no_unrelated_agents"] = {s.agent for s in trace.steps if s.agent} <= set(case["route"].split("+"))
                    checks["no_birth_requirement"] = not (case["route"] in {"knowledge", "dream"} and response.status == "needs_input")
                    memory = MemorySelector(app.session_factory)
                    session_id = prefix + "-" + case["id"]
                    if case["route"] == "dream":
                        dream = await memory.load_dream_memory(session_id)
                        row["dream_state"] = dream.model_dump(mode="json")
                        if previous_dream_id is not None:
                            checks["dream_boundary"] = (str(dream.dream_id) != previous_dream_id) == (case["id"] == "dream-new")
                            if case["id"] == "dream-correction":
                                people = " ".join(dream.elements.people)
                                checks["corrected_people"] = "哥哥" in people and "爸爸" not in people and "父亲" not in people
                        previous_dream_id = str(dream.dream_id)
                    if "bazi" in case["route"]:
                        expected_profile.update(expected.get("birth_patch", {}))
                        if response.status == "answered":
                            profile = await memory.load_birth_profile(session_id)
                            checks["profile_persisted"] = all(getattr(profile, key) == value for key, value in expected_profile.items())
                            chart = LunarPythonBaziAdapter().calculate(profile).model_dump(mode="json")
                            checks["chart_matches_profile"] = response.facts.get("bazi", response.facts) == chart
                    if case["route"] == "liuyao":
                        decision = await memory.load_decision_memory(session_id)
                        checks["confirmation_boundary"] = (decision.hexagram is not None) == (response.status == "answered")
                    row["passed"] = all(checks.values())
                except Exception as exc:
                    row.update(passed=False, error_type=type(exc).__name__, error_category=error_category(exc))
                    if traces:
                        row["trace"] = asdict(traces[-1])
                entry["passed"] &= row["passed"]
                print(case["id"], expected["status"], row["passed"], flush=True)
                save()
    report["total"] = len(dataset)
    report["completed"] = sum(c["passed"] for c in report["cases"])
    report["provider_network_errors"] = sum(t.get("error_category") == "provider_network" for c in report["cases"] for t in c["turns"])
    report["completion_rate"] = report["completed"] / len(dataset) if dataset else 0
    report["routes"] = route_metrics(report["cases"])
    report["passed"] = len(dataset) >= 20 and report["completion_rate"] >= 0.95
    save()
    return report


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    result = asyncio.run(evaluate(Path(sys.argv[1] if len(sys.argv) > 1 else "reports/stage10_e2e.json")))
    raise SystemExit(0 if result["passed"] else 1)
