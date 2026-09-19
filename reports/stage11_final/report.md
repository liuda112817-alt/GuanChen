# Stage 1–11 backend evaluation baseline

Generated: 2026-09-19T15:31:07.928832+00:00

Gate: **PASS**

| Check | Passed |
|---|---|
| all_commands_completed | True |
| router | True |
| retrieval | True |
| mcp | True |
| end_to_end | True |
| cost_observed | True |
| stage11_backend | True |

Router accuracy: 1.0; secondary: 1.0
RAG Recall@5: 0.9111111111111111
Bazi fixtures: {'total': 13, 'passed': 13, 'failed': 0, 'skipped': 0}
Liuyao fixtures / HITL: {'total': 38, 'passed': 38, 'failed': 0, 'skipped': 0}
E2E completion: 1.0; provider network errors: 0

Token cost is measured in provider tokens; monetary pricing is not assumed.

| Route | Turns | Model calls max / limit | Tools max / limit | p50 ms | p95 ms | Tokens |
|---|---:|---:|---:|---:|---:|---:|
| knowledge | 5 | 1 / 20 | 0 / 4 | 2989.14 | 3184.02 | 24175 |
| bazi | 8 | 3 / 20 | 2 / 4 | 6035.91 | 6756.3 | 64274 |
| dream | 7 | 2 / 20 | 0 / 4 | 4293.33 | 5764.54 | 50783 |
| liuyao | 8 | 3 / 20 | 1 / 4 | 1368.02 | 22432.96 | 50665 |
| bazi+dream | 1 | 5 / 20 | 2 / 4 | 10493.92 | 10493.92 | 23991 |
| chitchat | 1 | 0 / 20 | 0 / 4 | 38.42 | 38.42 | 0 |
| out_of_scope | 1 | 1 / 20 | 0 / 4 | 1521.51 | 1521.51 | 2199 |

See e2e.json for synthetic responses, checks, trace steps and error types. See stage10_cases.json for the manual review rubric.
The automated gate checks workflow and lineage; semantic answer quality requires reading the scenario outputs.
Reranker stays disabled under the saved Stage 4 quality/latency decision; this command evaluates the production RRF path.
