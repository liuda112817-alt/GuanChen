# Stage 10 Validation Gate

| Category | Item | Expected Criteria | Status |
| :--- | :--- | :--- | :--- |
| **Evaluation Framework** | Framework core tests pass | `test_framework.py` green | ✅ |
| **Bazi Evaluation** | Dataset + Evaluator + Report | `test_bazi_evaluator.py` green | ✅ |
| **Knowledge Evaluation** | Dataset + real Retrieval evaluation | DB connected, `test_knowledge_evaluator.py` green | ✅ |
| **Liuyao Evaluation** | normal + expected failure cases | `test_liuyao_evaluator.py` green | ✅ |
| **Application Trace** | application → router same trace_id | Context propagation verified | ✅ |
| **MCP Trace** | mcp request → tool → service same trace_id | Verified in `test_runtime_trace.py` | ✅ |
| **Failure Trace** | FAILED status propagated | isError and Exceptions trapped | ✅ |
| **Metrics** | counters + latency + errors available | Snapshot generated | ✅ |
| **Structured Logging** | JSON logs, stderr-safe | stdio uncontaminated | ✅ |
| **Regression** | existing suite remains green | integration and unit tests pass | ✅ |
| **Static Check** | Ruff green | `uv run ruff check` pass | ✅ |
