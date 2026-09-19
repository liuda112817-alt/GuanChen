# 观尘 GuanChen v2

> 传统文化智能推演与知识服务 AI Agent Application  
> 建设基线：**GuanChen v2 冻结规划 v1.0**  
> 当前状态：**Stage 1–11 后端已建设；Bolt UI 对接与 Stage 12 仍为后续工作**

## 1. Overview

观尘 GuanChen v2 是一个面向中文传统文化场景的垂直 AI Agent 应用。

项目通过：

- 确定性领域计算；
- 可追溯知识检索；
- 多轮上下文维护；
- 可恢复工作流；
- 严格的 Agent / Tool / Retrieval / Memory 边界；

为用户提供传统文化知识解释、结构化推演与现实反思服务。

项目同时服务于第二个目标：系统实践 AI Agent / LLM Application Engineering，并形成一个能够用于中国大陆 AI Agent / LLM 应用开发岗位求职展示的旗舰项目。

本项目不是“AI 算命大全”，也不以堆叠更多玄学 Agent 为目标。

---

## 2. Product Scope

GuanChen v2.0 只包含四个核心领域 Agent：

| Agent | 核心职责 | 主要工程模式 |
|---|---|---|
| Bazi Analysis Agent | 基于确定性排盘事实与知识依据解释个人八字问题 | Tool-centric |
| Dream Interpretation Agent | 在多轮对话中维护 DreamRecord，并提供传统文化 + 非诊断性情境解释 | Context-centric |
| Liuyao Decision Reflection Agent | 澄清问题、用户确认后起卦，并生成现实决策反思 | Workflow-centric / HITL |
| Traditional Culture Knowledge Agent | 基于受控知识库回答传统文化知识问题并提供来源 | Retrieval-centric |

v2.0 不增加第五业务 Agent。

---

## 3. Engineering Principles

1. **确定性计算不交给 LLM。**  
   八字排盘、六爻卦象等由代码 / 成熟库完成；LLM 负责理解、选择、解释和整合。

2. **优先复用成熟能力。**  
   能稳定调用成熟库 / 官方 API 的能力，不重复造轮子。

3. **Agent 只用于真正需要决策、语言理解和编排的地方。**  
   确定性能力优先设计为 Tool / Service。

4. **Retrieval 是共享基础设施。**  
   不为每个 Agent 单独建设一套 RAG。

5. **Memory 按领域选择，而不是全量注入。**  
   不把用户全部历史无脑塞给所有 Agent。

6. **LangGraph 在真实 Workflow 需求出现后再引入。**  
   不为了统一技术栈而提前 Graph 化。

7. **评价和可观测性是最终产品能力的一部分。**  
   项目不以“感觉能用”作为质量标准。

8. **阶段内不扩项。**  
   新想法进入 v2.1 Backlog；除非阻塞正确性、安全性或可运行性。

---

## 4. Target Architecture

> 下图描述的是 **Stage 12 完成后的目标架构**。  
> 它不代表当前已经实现这些组件。

```mermaid
flowchart TD
    U[Web Frontend] -->|HTTP / SSE| API[FastAPI Gateway + Safety]

    API --> CG[ConversationGraph / Router]

    CG --> B[Bazi Agent]
    CG --> D[Dream Agent]
    CG --> L[Liuyao Agent]
    CG --> K[Knowledge Agent]

    B --> BT[calculate_bazi Tool]
    BT --> LP[lunar_python]

    D --> DC[Dream Context / Memory]

    L --> LG[LangGraph HITL]
    LG --> HT[cast_hexagram Tool]
    HT --> IP[ichingpy]

    B --> R[Shared Retrieval Service]
    D --> R
    L --> R
    K --> R

    R --> DR[Dense: BGE]
    R --> SR[Sparse: BM25S]
    DR --> F[RRF + Optional Reranker]
    SR --> F
    F --> PG[(PostgreSQL + pgvector)]

    CG --> MEM[(PostgreSQL: profiles / conversations / memory)]
    CG --> OBS[Evaluation / Observability]

    MCP[MCP Server] --> BT
    MCP --> R
    MCP --> HT

    REDIS[(Redis: rate limit / idempotency / short TTL cache)]
    API --> REDIS
```

详细说明见 [`docs/architecture.md`](docs/architecture.md)。

---

## 5. Unified Request Lifecycle

目标请求生命周期：

```text
User Request
→ Request Context Initialization
→ Safety Pre-check
→ Load Minimal Routing Context
→ Route
→ Requirement Check
→ Load Selected Domain Context
→ Execute Selected Agent(s)
→ Tool / Retrieval As Needed
→ Response + Citation
→ Explicit / Confirmed Memory Update
→ Complete
```

以下能力属于横切关注点，而不是单一业务节点：

- Trace / Observability
- Persistence / Checkpoint
- Error Handling
- Streaming / SSE

详细说明见 [`docs/request_lifecycle.md`](docs/request_lifecycle.md)。

---

## 6. Roadmap

| Stage | Theme |
|---:|---|
| 0 | Product / Domain / Architecture Freeze |
| 1 | Engineering Skeleton + LLM Foundation |
| 2 | Bazi Deterministic Tool |
| 3 | Bazi Agent Vertical Slice |
| 4 | Shared RAG + Knowledge Agent |
| 5 | Dream Agent + Context Engineering |
| 6 | Liuyao Agent + LangGraph HITL |
| 7 | Router + Multi-Agent Orchestration |
| 8 | Memory + Persistence |
| 9 | MCP Standardization |
| 10 | Evaluation + Observability |
| 11 | Safety + FastAPI + SSE + Frontend Integration |
| 12 | Production Deployment + Interview Delivery |

详细路线见 [`docs/roadmap.md`](docs/roadmap.md)。

---

## 7. Current Implementation Status

Stage 1–11 后端当前实现与验收见 [阶段状态](docs/stage_status.md)、[Stage 11 后端 API 说明](docs/stage11_backend_api.md) 和 [统一评测报告](reports/stage11_final/report.md)。

回答表达规范和模型 thinking 选择见 [回答表达设计](docs/response_style.md)。

- 真实应用：`uv run python scripts/chat_cli.py`；依赖 `.env`、PostgreSQL + pgvector 和已导入语料。
- MCP：官方 SDK v2、Streamable HTTP、三个复用领域 service 的工具，见 [使用说明](docs/mcp_usage.md)。内部 Agent 直接调用 service，MCP 用于外部应用互操作。
- Evaluation：`uv run python scripts/run_evals.py --include-stage11` 一条命令重跑 Stage 1–11 后端的回归、集成、MCP、Router、Retrieval、固定端到端场景和真实 API 验收，输出 JSON + Markdown，失败返回非零。
- Observability：LLM/token、Tool、Retrieval、Graph node 和每路由调用上限；日志 stderr，无需 LangSmith。
- Stage 11 后端（Safety / FastAPI / SSE / API contract）已完成；Bolt UI 对接及 Stage 12（Redis / 部署）仍为后续建设。

---

## 8. Documentation

- [`docs/product_charter.md`](docs/product_charter.md)
- [`docs/agent_contracts.md`](docs/agent_contracts.md)
- [`docs/user_flows.md`](docs/user_flows.md)
- [`docs/domain_models.md`](docs/domain_models.md)
- [`docs/request_lifecycle.md`](docs/request_lifecycle.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/roadmap.md`](docs/roadmap.md)
- [`docs/backlog_v2_1.md`](docs/backlog_v2_1.md)
- [`docs/learning_knowledge_map.md`](docs/learning_knowledge_map.md)
- [`docs/adr/`](docs/adr/)

---

## 9. Stage Discipline

每一个 Stage：

1. 开始前确认目标、固定任务、新知识、调用 / 自研边界、测试范围、非目标和完成标准；
2. Stage 内只完成当前 Stage 的冻结任务；
3. Gate 未通过，不进入下一 Stage；
4. 新想法进入 v2.1 Backlog；
5. 只有正确性、安全性或不可运行的阻塞问题可以触发最小方案变更，并记录 ADR。

Stage 1–11 后端以 `scripts/run_evals.py --include-stage11` 生成的统一报告和 [完整 review 结论](docs/stage1_stage11_backend_review_2026-09-19.md) 为准。
