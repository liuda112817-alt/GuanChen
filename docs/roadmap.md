# GuanChen v2 Frozen Roadmap

- Status: **Frozen**
- Version: **v1.0**
- Rule: 当前 Stage 只做当前 Stage 固定任务；Gate 未通过不得进入下一 Stage。

| Stage | Theme | Core Deliverable | Gate |
|---:|---|---|---|
| 0 | Product / Architecture Freeze | Charter, Contracts, Flows, Domain Models, Lifecycle, ADR, Architecture | 所有设计阻塞项关闭 |
| 1 | Engineering Skeleton + LLM Foundation | CLI, config, Pydantic contracts, LLMClient | text / structured 调用稳定 |
| 2 | Bazi Deterministic Tool | BirthProfile → BaziChart Tool | fixtures 100% 合法 |
| 3 | Bazi Agent Vertical Slice | NeedUserInput → Tool Calling → Explanation | 第一条 Agent 闭环可用 |
| 4 | Shared RAG + Knowledge Agent | Hybrid Retrieval, Citation, Bazi RAG | Recall / Source / Degradation 达标 |
| 5 | Dream Agent | Structured DreamRecord + multi-turn context + RAG | 连续更新不丢状态 |
| 6 | Liuyao + LangGraph HITL | Clarify → Confirm → Cast → RAG → Reflection | 可暂停 / 恢复 / 拒绝 |
| 7 | Router + Multi-Agent | Single-domain routing + explicit double-domain fan-out | routing accuracy 达标 |
| 8 | Memory + Persistence | Postgres long-term data + persistent thread | restart 后关键状态可恢复 |
| 9 | MCP | 3 mature capabilities exposed as MCP tools | external client 可发现并调用 |
| 10 | Evaluation + Observability | eval runner, trace, baseline report | 一条命令生成可复现报告 |
| 11 | Safety + API + SSE | FastAPI, SSE, frontend integration, safety | 4 Agent 网页可完整使用 |
| 12 | Production + Job Delivery | Docker Compose, Redis, CI/CD, public demo | 可公开演示、可复现部署 |

---

# Stage 0 — Product / Domain / Architecture Freeze

## Goal

不写业务代码。

一次性定义：

- 做什么；
- 不做什么；
- 四 Agent 负责什么；
- 关键领域模型；
- 请求生命周期；
- 关键技术决策；
- 终局架构；
- Backlog 规则。

## Artifacts

- `README.md`
- `docs/product_charter.md`
- `docs/agent_contracts.md`
- `docs/user_flows.md`
- `docs/domain_models.md`
- `docs/request_lifecycle.md`
- `docs/architecture.md`
- `docs/roadmap.md`
- `docs/backlog_v2_1.md`
- `docs/adr/*`
- `docs/learning_knowledge_map.md`

## Gate

- 四 Agent 职责无重叠或歧义；
- Tool 与 Agent 边界清晰；
- 确定性计算没有被设计成 Agent；
- v2.0 Non-goals 已确认；
- Stage 1–12 路线冻结；
- Stage 0 正式产物已落库；
- 能不用代码解释关键设计选择。

---

# Stage 1 — Engineering Skeleton + LLM Foundation

## Goal

建立最小但可长期演进的 Python 项目骨架。

## Fixed Scope

- Python 3.12 + uv + pyproject.toml
- config / models / llm / prompts / core / scripts / tests
- pydantic-settings
- LLMClient
- text call
- Pydantic structured output
- unified exception boundary
- limited retry
- prompt organization
- minimal logging
- smoke_llm.py
- Ruff

## Tests

- fake model: empty structured result / parse failure / retry exhaustion
- one live smoke: text + structured

## Not Do

- Tool Calling
- Agent
- Web API
- persistence
- RAG
- LangGraph

---

# Stage 2 — Bazi Deterministic Tool

## Goal

把 BirthProfile 稳定转换成自己的 BaziChart。

## Fixed Scope

- BirthProfile
- BaziChart
- lunar_python Adapter
- calculation_method
- calculate_bazi Tool
- fixed fixtures
- bazi_calculation_contract.md

## Tests

至少 8 个 fixture，覆盖：

- 普通时刻；
- 23 点边界；
- 闰月附近；
- 男女大运等。

至少 2 个 fixture 对照官方示例。

## Not Do

- Bazi interpretation
- RAG
- geocoding
- true solar time
- Agent memory

---

# Stage 3 — Bazi Agent Vertical Slice

## Goal

第一条真实 Agent 闭环：

```text
User Query
→ Requirement Check
→ Tool Calling
→ Explanation
```

## Fixed Scope

- BaziAgentInput / Result / NeedUserInput
- high-level LangChain Agent / tool binding
- calculate_bazi Tool
- missing data check
- fact / interpretation separation
- call budget
- CLI conversation

## Acceptance

至少 6 类场景：

- 资料完整
- 缺时间
- 缺性别
- 重复补充
- 事业
- 感情

---

# Stage 4 — Shared RAG + Knowledge Agent

## Goal

建立项目唯一共享知识检索底座。

## Fixed Scope

- legal / public-domain corpus
- KnowledgeDocument / KnowledgeChunk
- ingestion
- BGE dense embedding
- BM25S + jieba sparse retrieval
- RRF
- metadata filter
- optional BGE reranker
- Citation
- Knowledge Agent
- Bazi Retrieval Tool
- retrieval eval

## Gate

- 至少 30 条 golden query
- Recall@5 >= 0.85
- 记录 MRR@10
- Reranker 默认开启条件：
  - relative MRR@10 improvement >= 5%
  - p95 added retrieval latency <= 800ms

## Not Do

- Knowledge Graph
- Agentic RAG
- custom embedding
- large-scale web crawling

---

# Stage 5 — Dream Agent

## Goal

构建 Context-centric Agent。

## Fixed Scope

- DreamElements
- DreamRecord
- structured extraction
- necessary clarification rule
- multi-query retrieval
- traditional + non-diagnostic contextual perspective
- in-process session state

## Tests

- DreamRecord merge / update pure functions
- at least 6 multi-turn acceptance scenarios

## Not Do

- psychological diagnosis
- long-term memory
- LangGraph
- multimodal dream image

---

# Stage 6 — Liuyao + LangGraph HITL

## Goal

首次在真实暂停 / 确认 / 恢复业务中引入 LangGraph。

## Fixed Scope

- DecisionQuestion
- ichingpy Adapter
- HexagramResult
- random coin method
- manual line input
- LiuyaoState
- clarify → interrupt → cast → retrieve → interpret → finalize
- InMemory checkpointer

## Tests

- Hexagram fixed-input fixtures
- interrupt / resume
- before confirm: cast calls = 0
- reject / modify branch

## Not Do

- full school coverage
- automatic real-world decision
- cross-process checkpoint

---

# Stage 7 — Router + Multi-Agent Orchestration

## Goal

统一四个已经独立可用的 Agent。

## Fixed Scope

- IntentType
- RoutingResult
- rule + structured LLM router
- single-domain route
- explicit two-domain fan-out
- Synthesizer
- top-level ConversationGraph
- routing golden dataset

## Gate

- at least 60 labeled queries
- primary intent accuracy >= 0.92
- max two Agents for double-domain

## Not Do

- 3–4 Agent consultation
- Agent debate
- dynamic Agent creation

---

# Stage 8 — Memory + Persistence

## Goal

把进程内状态升级为可恢复产品状态。

## Fixed Scope

- PostgreSQL domain tables
- SQLAlchemy async repository
- PostgreSQL LangGraph checkpointer
- explicit long-term memory only
- Memory Selector
- domain isolation
- user correction

## Tests

- BirthProfile write/read/correction
- cross-process HITL resume
- DreamRecord not visible in Bazi memory context

## Not Do

- vectorized long-term memory
- automatic personality profile
- full version tree

---

# Stage 9 — MCP

## Goal

把成熟能力标准化暴露给外部 Agent Host。

## Fixed Scope

- official MCP Python SDK
- calculate_bazi
- knowledge_search
- cast_hexagram
- Streamable HTTP
- minimal access boundary
- client / Inspector smoke

## Not Do

- MCP marketplace
- many third-party MCPs
- internal runtime depends on MCP

---

# Stage 10 — Evaluation + Observability

## Goal

从“感觉能用”升级为“知道质量与成本表现”。

## Fixed Scope

- unify previous evaluation assets
- AgentRun / RunStep
- trace hook
- run_evals.py
- JSON + Markdown report
- p50 / p95
- token usage
- end-to-end business cases
- optional LangSmith

## Gate

- e2e fixed scenarios >= 95% expected flow completion
- all routes have model/tool call limits
- baseline report saved

---

# Stage 11 — Safety + FastAPI + SSE + Frontend

## Goal

把成熟 Agent Runtime 变成真实 Web 产品。

## Fixed Scope

- stable API contract
- FastAPI
- ConversationGraph integration
- SSE event protocol
- rule-first safety precheck
- high-risk boundary
- output safety
- existing frontend adaptation
- minimal anonymous/session identity

## Tests

- chat
- need_input
- interrupt/resume
- error
- safety fixtures

## Not Do

- visual redesign
- complex account center
- payment
- WebSocket

---

# Stage 12 — Production + Job Delivery

## Goal

公开可访问、可复现部署、可展示架构演进与评价数据。

## Fixed Scope

- Docker Compose
- PostgreSQL + pgvector
- Redis
- Nginx / HTTPS
- health / readiness
- timeout / retry / dependency degradation
- secret management
- GitHub Actions
- deployment docs
- final eval
- interview demo docs
- v1 → v2 refactor retrospective

## Gate

- public URL works
- README can guide startup
- CI passes
- secrets not committed
- final eval report exists
- 3 stable interview demos
- developer can explain why Agent / Tool / LangGraph boundaries are designed this way
