# Stage 1–11 backend evaluation baseline

Generated: 2026-09-19T14:39:41.610663+00:00

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
| knowledge | 5 | 1 / 20 | 0 / 4 | 2747.28 | 3248.56 | 21794 |
| bazi | 8 | 3 / 20 | 2 / 4 | 5466.43 | 6489.67 | 58728 |
| dream | 7 | 2 / 20 | 0 / 4 | 3284.74 | 4448.83 | 46166 |
| liuyao | 8 | 1 / 20 | 1 / 4 | 1242.96 | 9686.67 | 24075 |
| bazi+dream | 1 | 5 / 20 | 2 / 4 | 12145.61 | 12145.61 | 21798 |
| chitchat | 1 | 0 / 20 | 0 / 4 | 38.41 | 38.41 | 0 |
| out_of_scope | 1 | 1 / 20 | 0 / 4 | 962.5 | 962.5 | 2198 |

See e2e.json for synthetic responses, checks, trace steps and error types. See stage10_cases.json for the manual review rubric.
The automated gate checks workflow and lineage; semantic answer quality requires reading the scenario outputs.
Reranker stays disabled under the saved Stage 4 quality/latency decision; this command evaluates the production RRF path.
