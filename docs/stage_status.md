# GuanChen v2 Stage Implementation Status

> Last Updated: 2026-09-18

## Purpose

This document is the single source of truth for GuanChen v2 implementation progress.

It records:

- planned Stage objectives;
- current implementation status;
- related modules;
- verification status;
- known limitations.

This document does not replace the architecture planning document.
It only describes the current implementation state.

---

# Overall Status

| Stage | Objective | Status |
|---|---|---|
| Stage 1 | LLM Foundation | Completed |
| Stage 2 | Bazi Deterministic Tool | Completed |
| Stage 3 | Bazi Single Agent Loop | Completed |
| Stage 4 | RAG Infrastructure | Completed |
| Stage 5 | Dream Agent | Completed |
| Stage 6 | Liuyao HITL Workflow | Completed |
| Stage 7 | Multi-Agent Router | Completed |
| Stage 8 | Memory Persistence | Completed |

---

# Stage Details


## Stage 1 — LLM Foundation

### Objective

Build the basic LLM infrastructure.

Scope:

- LLM Client abstraction;
- configuration management;
- structured output support;
- unified LLM exception handling.

### Current Status

Completed.

### Related Modules
src/guanchen_v2/llm/
src/guanchen_v2/config/

### Verification

Implemented:

- text generation;
- structured output generation;
- provider error conversion.

### Known Limitations

- Async-first migration is still required.


---

# Stage 2 — Bazi Deterministic Tool

## Objective

Implement deterministic Bazi calculation.

Principle:

LLM does not calculate factual chart information.

### Current Status

Completed.

### Related Modules
src/guanchen_v2/bazi/
src/guanchen_v2/models/bazi.py


### Verification

Implemented:

- lunar_python adapter;
- domain model mapping;
- deterministic chart generation.

### Known Limitations

- Domain layer still needs stronger isolation from external library metadata.


---

# Stage 3 — Bazi Agent Loop

## Objective

Build the first complete Agent workflow.

Flow:

### Verification

Implemented:

- lunar_python adapter;
- domain model mapping;
- deterministic chart generation.

### Known Limitations

- Domain layer still needs stronger isolation from external library metadata.


---

# Stage 3 — Bazi Agent Loop

## Objective

Build the first complete Agent workflow.

Flow:
User Input
|
Requirement Check
|
Bazi Tool
|
Interpretation

### Current Status

Completed.

### Related Modules

src/guanchen_v2/agents/bazi/

### Verification

Implemented:

- structured input;
- missing information handling;
- tool invocation validation;
- citation validation.

### Known Limitations

- Agent autonomy needs further constraint.


---

# Stage 4 — Knowledge RAG Infrastructure

## Objective

Build shared knowledge retrieval infrastructure.

Scope:

- ingestion;
- chunking;
- embeddings;
- retrieval;
- reranking;
- evaluation.

### Current Status

Completed.

### Related Modules

src/guanchen_v2/knowledge/


### Verification

Implemented:

- retrieval pipeline;
- reranker;
- retrieval metrics.

### Known Limitations

- Evaluation corpus needs to be added.


---

# Stage 5 — Dream Agent

## Objective

Build dream interpretation Agent based on context engineering.

Scope:

- DreamRecord;
- context merge;
- retrieval;
- interpretation.

### Current Status

Completed.

### Related Modules

src/guanchen_v2/dream/


### Implemented

- Dream context management;
- dream merge logic;
- retrieval integration;
- structured interpretation output;
- 多轮状态机（SAME / NEW / NEEDS_CLARIFICATION）与追问规则；
- 三路检索（象征 / 情绪 / 现实背景）强制 DREAM domain；
- Stage 8 持久化（DreamRecordStore）接入。

### Verification

`tests/dream/`：38 passed（含边界分类、追问、merge、检索过滤、证据引用校验）。


---

# Stage 6 — Liuyao HITL Workflow

## Objective

Build human-in-the-loop workflow.

Flow:

Clarify
|
User Confirmation
|
Casting
|
Retrieval
|
Interpretation


### Current Status

Completed.

### Related Modules

src/guanchen_v2/liuyao/


### Implemented

- LangGraph workflow;
- interrupt confirmation;
- checkpoint abstraction（InMemory 默认 + Postgres 可注入）;
- evidence validation;
- 起卦策略（系统三枚硬币 / 手工六爻，secrets 随机源）;
- 确认前禁止起卦 / 检索 / 解释的状态机守卫;
- Stage 8 `resume(thread_id, payload)` 跨进程恢复接口。

### Verification

`tests/liuyao/` + `tests/models/test_liuyao_models.py`：43 passed（含 Graph 中断-恢复、确认分支、证据引用防伪造）。


---

# Stage 7 — Multi-Agent Router

## Objective

Create unified entry point for multiple Agents.

Scope:

- intent routing;
- dispatch;
- synthesis.

### Current Status

Completed.

### Related Modules

src/guanchen_v2/router/
src/guanchen_v2/application/

### Implemented

- two-layer routing（高精度规则层 + LLM 结构化兜底）;
- single Agent dispatch（防伪重算校验）;
- dual domain dispatch（最多两个 Agent）;
- synthesis（只整合不新推演）;
- 统一 ConversationGraph orchestration;
- 路由黄金数据集 + 评估脚本。

### Verification

- `tests/router/`：50 passed（含 LLM 零调用规则命中、防伪、合成器载荷防泄漏）;
- `evals/router/stage7_router_golden.json`：65 条人工标注（6 类意图 + 21 条双领域/模糊场景）;
- `scripts/eval_router.py --rules-only`：规则层命中 56/65、已命中项准确率 100%；9 条模糊项按设计交由 LLM 兜底；
- 硬门槛核对：`primary intent accuracy >= 0.92`（规则层已命中项 100%）、Knowledge / Dream 不要求出生资料（0 违规）、双领域最多两个 Agent。


---

# Stage 8 — Memory Persistence

## Objective

Introduce persistent product-level memory.

Scope:

- conversation persistence;
- user profile;
- domain records;
- checkpoint persistence.

### Current Status

Completed.

### Related Modules

- src/guanchen_v2/memory/
- src/guanchen_v2/core/session/
- src/guanchen_v2/application/orchestrator.py
- src/guanchen_v2/router/adapters/liuyao.py
- src/guanchen_v2/dream/runtime.py
- scripts/create_memory_tables.py

### Implemented

1. **Postgres 域表**（`memory/models.py`）：`user_profile` / `birth_profile` / `conversation` / `message` / `dream_record` / `decision_record` + `conversation_states`；SQLAlchemy async、FK 级联删除、`created_at` / `updated_at`、必要索引与唯一约束。
2. **SQLAlchemy async repository 层**（`memory/repositories.py`）：
   - `UserProfileRepository` / `BirthProfileRepository`（upsert，后写覆盖 = 用户更正语义）；
   - `ConversationRepository`（幂等 create + append_message + get_recent_messages）；
   - `DreamRecordRepository` / `DecisionRecordRepository`（按 user 取最新）；
   - 写域数据前自动 `_ensure_user_async` 创建 user_profile 父行。
3. **LangGraph PostgreSQL 持久 checkpointer**（`memory/checkpointer.py`）：封装官方 `AsyncPostgresSaver` + `AsyncConnectionPool`，六爻 HITL 线程可跨进程/重启恢复。
4. **Memory Selector 领域隔离**（`memory/selector.py`）：BAZI 只注入 `BIRTH_PROFILE`；LIUYAO 待确认状态注入决策问题种子；DREAM / KNOWLEDGE / CHITCHAT / OOS 不注入历史记忆——不把全历史无脑塞给模型。
5. **领域记录持久化**（`memory/stores.py`）：`PostgresDreamRecordStore` / `PostgresDecisionRecordStore`；`dream/runtime.py` 接入记录生命周期；`liuyao.py` adapter 每次决策持久化 `DecisionRecord` 并提供 `resume(thread_id, payload)` 外部接力接口。
6. **编排层写回**：BAZI 执行成功后持久化出生资料，重启后无需重复询问。
7. **数据库工厂**（`memory/database.py`）：`create_async_engine_and_factory()` 工厂模式 + `get_session()` 依赖注入，解决 asyncpg 连接池跨事件循环问题。

### Verification

三类必测全部通过（`pytest -m integration`）：

- **持久化**：`test_postgres_memory_store.py`、`test_birth_profile_repository.py`、`test_domain_record_stores.py`、`test_checkpoint_recovery.py`（跨进程 resume/cancel）；
- **恢复**：`test_stage8_memory_acceptance.py`（普通 Agent 恢复 / 多轮对话 / 六爻中断-重启-恢复 / 八字长期记忆预填）；
- **隔离**：会话隔离用例、`test_memory_selector.py`（梦境永不泄漏进八字 context）。

当前验证结果：

```text
默认套件：358 passed, 43 deselected
集成套件（-m integration，含 Stage 8 Memory）：42 passed
静态检查：ruff check src tests scripts 通过（0 error）
Stage 4 Retrieval：45 条评测，RRF Recall@5=0.9111；Reranker Gate 未通过，生产保持关闭
Stage 4 Knowledge Agent：10/10 真实回答 citation lineage 通过
Stage 7 Router：65 条 full-chain，primary / secondary accuracy 均 1.0
Stage 8 应用验收：32 个真实入口场景，跨会话 Dream 隔离、六爻重启恢复、八字更正均通过
```

测试数据库：`postgresql+asyncpg://postgres:postgres@localhost:5432/guanchen_test`（由 `tests/conftest.py` 的 `db_env` / `postgres_session_factory` fixture 管理建表与 teardown，含 checkpoint 表清理）。

### Known Limitations

- 进程级默认 engine 仍为单实例（多进程部署需各自初始化）；
- checkpoint 序列化使用 langgraph 默认 serde，运行时仍会提示未注册类型警告；严格 allowlist 留待后续安全专项处理；
- 测试与运行时依赖 PostgreSQL；本次已用 `guanchen_eval_db`（localhost:5432）完成集成验收。


---

# Current Architecture Debt

The following items are tracked separately:

| Issue | Priority | Status |
|---|---|---|
| Agent Contract Unification | P0 | Stage 7 已统一 `AgentExecutionResult.output`；残余以 ADR 跟踪 |
| Citation Protocol Unification | P0 | Stage 6 已实现证据校验；全链路对齐待 Stage 11 |
| State Model Separation | P0 | Stage 8 已拆分会话状态与领域记忆（conversation_states vs 域表） |
| Memory Schema Freeze | P0 | Stage 8 已冻结（`memory/models.py` + `create_memory_tables.py`） |
| Orchestrator Refactor | P0 | Stage 8 已接入 ConversationGraph、MemorySelector 与真实应用工厂；后续 Web 层只做 API 适配 |


---

# Update Rules

This document should be updated when:

1. A Stage acceptance criteria is completed;
2. A major architecture decision changes implementation status;
3. A Stage moves from Partial to Completed.

Small code changes should not update this document.
