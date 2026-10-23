# 观尘 GuanChen v2

面向传统文化知识问答与现实决策反思的 AI Agent 应用。通过四类业务场景，实践 **Python 后端、Tool Calling、Hybrid RAG、LangGraph HITL、领域记忆、MCP 与评测观测**的完整应用链路。

**[在线演示](https://www.guanchen.online/)** · **[后端评测报告](reports/stage11_final/report.md)** · **[前后端验收记录](reports/frontend_acceptance_2026-09-20.md)** · **[部署说明](docs/frontend_and_deployment.md)**

Web 前后端已实现，仓库包含业务代码、固定评测集、验收报告、界面截图和单机部署配置。阅读代码可从 [应用装配](src/guanchen_v2/application/factory.py)、[会话编排](src/guanchen_v2/application/orchestrator.py) 和 [API 入口](src/guanchen_v2/api/app.py) 开始。

## 产品与演示

用户通过统一对话入口提问，系统识别意图、按需补充资料，再执行对应任务。知识问答和梦境解读无需先填写出生信息；六爻流程在用户确认后才执行起卦。

| 场景 | 用户能力 | 主要工程实践 |
| --- | --- | --- |
| 传统文化知识 | 解释概念、术语与原典，查看回答引用 | 混合检索、证据约束、引用溯源 |
| 八字分析 | 补齐出生资料后获取排盘事实与解释 | 确定性工具、调用预算、结构化结果校验 |
| 梦境解读 | 多轮补充梦境和现实背景，更新同一记录 | 结构化抽取、增量合并、上下文选择 |
| 六爻决策反思 | 澄清问题、确认或修改、起卦后结合现实条件反思 | 人工确认、状态机、checkpoint 与恢复 |

### 界面预览

桌面首页：

![观尘桌面首页](reports/frontend-home-desktop.png)

知识问答与来源入口：

![观尘知识问答与引用](reports/frontend-desktop-answer.png)

<details>
<summary>查看移动端与深色主题</summary>

<img src="reports/frontend-home-mobile.png" alt="观尘移动端首页" width="320">

![观尘深色主题](reports/frontend-home-dark.png)

</details>

截图来自仓库保存的前端验收记录。可先体验“正官是什么意思？”并查看来源，再尝试补充梦境背景或六爻确认流程。传统文化解释用于文化理解与现实反思，医疗、法律、投资及危机请求由安全策略处理。

## 后端设计与实现

### 1. 有边界的 Agent 编排

- 采用高精度规则与结构化 LLM Router 两层路由，区分四个业务领域、闲聊与范围外请求。
- 在执行前检查资料完整性；单领域只调用对应 Agent，显式双领域请求最多并发两个 Agent，再汇总已有结果。
- 排盘与卦象由 `lunar_python`、`ichingpy` 的适配层生成，模型负责理解、工具选择和解释；设置模型与工具调用上限，并校验工具产物和引用编号。

代码：[Router](src/guanchen_v2/router/core.py) · [双领域调度](src/guanchen_v2/router/dual_dispatch.py) · [八字 Runtime](src/guanchen_v2/agents/bazi/runtime.py)

### 2. 共享 Hybrid RAG 与引用溯源

- 统一语料处理链路：读取、清洗、按章节及长度切片、元数据与向量入库。
- 使用 `BAAI/bge-small-zh-v1.5` 和 PostgreSQL/pgvector 做向量检索，`bm25s + jieba` 做关键词检索，通过 RRF 融合候选；领域请求使用 metadata filter 控制检索范围。
- 回答引用绑定本轮检索结果的 `chunk_id`；拒绝未授权的证据编号，证据不足时明确降级。
- 已实现可选 Reranker，当前应用默认关闭：保存的对照基准未达到排序收益和额外延迟门槛，保留 RRF 路径作为默认实现。

代码：[检索服务](src/guanchen_v2/knowledge/retrieval/service.py) · [知识 Agent](src/guanchen_v2/agents/knowledge/agent.py) · [检索对照基准](evals/retrieval/stage4_reranker_baseline.json)

### 3. 领域记忆与可恢复工作流

- 分别维护 `BirthProfile`、`DreamRecord`、`DecisionRecord`，按意图选择所需资料，避免将全量历史注入所有 Agent。
- 使用 PostgreSQL 保存会话与领域记录；出生资料只在用户明确提供或更正后更新。
- 六爻采用 `clarify → interrupt → cast → retrieve → interpret → finalize` 工作流，以 PostgreSQL checkpointer 支持跨进程恢复；确认、修改与取消对应不同分支，结合确认标识和会话锁控制重复执行。

代码：[Memory Selector](src/guanchen_v2/memory/selector.py) · [梦境 Runtime](src/guanchen_v2/dream/runtime.py) · [六爻工作流](src/guanchen_v2/liuyao/workflow.py)

### 4. API、安全与可靠性

- FastAPI 提供对话、会话、资料、引用和中断恢复接口；匿名会话凭证以哈希保存，每次读写校验访问权限。
- SSE 实时传递路由、工具与检索等进度。回答正文在完整生成并通过校验后分块发送；前端支持心跳、截断识别与状态恢复。
- 安全预检采用规则优先、模糊风险再分类的策略；输出侧约束绝对灾祸、死亡和疾病断言。
- Redis 用于限流与短期幂等记录，配合超时和有界并发控制；长期会话状态仍由 PostgreSQL 保存。
- 提供 Docker Compose、Nginx SSE 透传、Caddy HTTPS、health/readiness 与数据库备份脚本。

代码：[API Service](src/guanchen_v2/api/service.py) · [SSE](src/guanchen_v2/api/streaming.py) · [可靠性控制](src/guanchen_v2/api/reliability.py) · [部署配置](deploy/compose.yml)

### 5. MCP 与评测观测

MCP 使用官方 Python SDK，向外部 Host 暴露 `calculate_bazi`、`knowledge_search`、`cast_hexagram` 三个工具。内部 Agent 直接复用领域 service；MCP 不复制业务逻辑，也不承担内部编排。

统一评测覆盖工具、路由、检索、HITL、持久化、MCP 和 API。Trace 记录模型调用、token、工具、检索、图节点、延迟与错误，结果输出为 JSON 和 Markdown，无需依赖外部观测平台。

代码：[MCP Server](src/guanchen_v2/mcp/server.py) · [Observability](src/guanchen_v2/observability/) · [评测入口](scripts/run_evals.py)

## 系统架构

```mermaid
flowchart TD
    Web["React / TypeScript Web"] -->|HTTP / SSE| API["FastAPI / Safety / Session Access"]
    API --> Graph["ConversationGraph / Router / Requirements"]
    Graph --> Bazi["Bazi Agent"]
    Graph --> Dream["Dream Agent"]
    Graph --> Liuyao["Liuyao Agent / HITL"]
    Graph --> Knowledge["Knowledge Agent"]
    Bazi --> BaziTool["calculate_bazi / lunar_python"]
    Liuyao --> HexTool["cast_hexagram / ichingpy"]
    Bazi --> Retrieval["Shared Retrieval / Dense + BM25 + RRF"]
    Dream --> Retrieval
    Liuyao --> Retrieval
    Knowledge --> Retrieval
    Retrieval --> DB[("PostgreSQL / pgvector")]
    Graph --> Memory["Domain Memory / Conversation State"]
    Memory --> DB
    Liuyao --> Checkpoint["Postgres Checkpointer"]
    Checkpoint --> DB
    API --> Redis[("Redis / Rate Limit / Idempotency")]
    MCP["MCP Server / External Host Access"] --> BaziTool
    MCP --> Retrieval
    MCP --> HexTool
    Graph -.-> Trace["Trace / Token / Latency / Error"]
```

技术栈：Python 3.12、uv、Pydantic v2、LangChain / ChatDeepSeek、LangGraph、FastAPI、SQLAlchemy async、PostgreSQL/pgvector、BGE、BM25S、Redis、MCP、React / TypeScript / Vite、Docker Compose。

## 已保存的验证结果

以下为 **2026 年 9 月保存的固定评测与本地验收结果**，不是本次文档更新重新执行的结果，也不代表线上实时指标。

| 验证项 | 记录结果 | 来源 |
| --- | --- | --- |
| Router 主意图 / 次意图准确率 | 固定集上均为 100% | [统一后端报告](reports/stage11_final/report.md) |
| Hybrid RAG | 45 条查询，Recall@5 91.1%，MRR@10 0.761 | [检索基准](evals/retrieval/stage4_reranker_baseline.json) |
| 八字固定输入验证 | 13/13 通过 | [统一后端报告](reports/stage11_final/report.md) |
| 六爻固定输入与 HITL | 38/38 通过 | [统一后端报告](reports/stage11_final/report.md) |
| 真实模型 + PostgreSQL + HTTP/SSE | 39 项检查通过 | [API 验收](reports/stage11_backend/report.md) |
| 后端默认回归 / 数据库集成 | 470 / 43 项通过 | [前后端验收](reports/frontend_acceptance_2026-09-20.md) |
| 桌面与移动端契约浏览器测试 | 20 项通过 | [前后端验收](reports/frontend_acceptance_2026-09-20.md) |
| 桌面与移动端真实浏览器链路 | 知识、梦境、八字补全、六爻中断与恢复通过 | [前后端验收](reports/frontend_acceptance_2026-09-20.md) |

Recall 衡量固定标注集中的检索召回，不能解释为整体回答准确率。自动评测主要检查流程、状态与事实来源，语义质量仍需结合场景输出人工审阅；浏览器契约测试与真实模型联调分别记录。

## 本地运行

需要 Python 3.12、uv、Node.js 22 LTS、Docker Compose，以及有效的模型 API Key。首次导入/启动需下载 BGE 模型，依赖和模型下载耗时取决于网络与硬件。

以下以 Windows PowerShell 为例，在新克隆的仓库中执行；已有 `.env` 时保留现有配置。

```powershell
git clone https://github.com/liuda112817-alt/GuanChen.git
cd GuanChen
uv sync --frozen
Copy-Item .env.example .env
```

在 `.env` 填写 `GUANCHEN_DEEPSEEK_API_KEY`，核对模型名和数据库地址。根目录 Compose 仅用于本地开发数据库，使用默认本地连接 `postgresql+asyncpg://postgres:postgres@localhost:5432/guanchen`，生产环境使用 `deploy/` 中的独立配置。

```powershell
docker compose up -d
uv run python scripts/ingest_corpus.py
uv run python scripts/serve_api.py
```

必须先成功导入知识库，后端会拒绝以空知识库启动。另开终端启动前端：

```powershell
cd frontend
npm ci
npm run dev
```

访问 `http://127.0.0.1:5173`；Vite 将 `/api` 代理到 `127.0.0.1:8000`。本地开发默认不要求 Redis，生产模式必须配置 Redis。CLI 可运行 `uv run python scripts/chat_cli.py`。

### 验证与评测命令

```powershell
# 默认回归：排除 smoke / integration 标记的测试
uv run python -m pytest -q

# 统一评测：需要数据库、语料与模型配置，会产生 API 调用消耗
uv run python scripts/run_evals.py --include-stage11
```

前端在 `frontend/` 中运行：

```powershell
npm run build
npm test
npx playwright install chromium
npm run test:e2e
```

真实浏览器联调的启用方式见 [前后端与部署说明](docs/frontend_and_deployment.md)，MCP 启动与调用方式见 [MCP 使用说明](docs/mcp_usage.md)。

## 运行边界

- 单机部署使用一个 API worker；当前会话锁与并发控制包含进程内状态，不能直接增加 worker 或副本。
- 匿名会话凭证保存在当前标签页的 `sessionStorage`，不提供账号体系、跨设备历史或用户自助服务端删除功能。
- 知识回答基于受控语料库，不在运行时自由联网搜索；不支持真太阳时修正、模型微调或第五业务领域。
- 仓库提供单机部署配置与备份脚本；线上可用性、负载容量和备份恢复需要在部署环境验证。公开 MCP 服务未包含在 Web 部署配置中。

## 代码与文档导航

| 路径 | 内容 |
| --- | --- |
| [src/guanchen_v2/application/](src/guanchen_v2/application/) | 应用装配与会话编排 |
| [src/guanchen_v2/router/](src/guanchen_v2/router/) | 路由、需求检查、调度与汇总 |
| [src/guanchen_v2/knowledge/](src/guanchen_v2/knowledge/) | 语料导入、向量存储与混合检索 |
| [src/guanchen_v2/memory/](src/guanchen_v2/memory/) | 领域记忆与持久化 |
| [src/guanchen_v2/api/](src/guanchen_v2/api/) | API、会话权限、SSE 与可靠性 |
| [frontend/](frontend/) / [deploy/](deploy/) | Web 前端与单机部署 |
| [tests/](tests/) / [evals/](evals/) / [reports/](reports/) | 测试、固定评测集与结果 |
| [Agent 契约](docs/agent_contracts.md) / [领域模型](docs/domain_models.md) | 业务职责与数据边界 |
| [请求生命周期](docs/request_lifecycle.md) / [API 契约](docs/stage11_backend_api.md) | 执行流程与接口定义 |
| [评测设计](docs/evaluation_framework.md) / [观测设计](docs/observability_design.md) | 质量指标与 Trace 设计 |
| [架构决策 ADR](docs/adr/) / [建设路线](docs/roadmap.md) | 技术取舍与阶段演进 |

项目按冻结规划 v1.0 分阶段建设。[架构规划](docs/architecture.md)、阶段 Review、原 Bolt 设计稿和 2026-09-20 部署交接记录保留当时的目标与验收边界，部分“尚未实现/尚未上线”说明属于历史状态；当前实现请结合本页及对应代码阅读，不据此宣称整个 Stage 12 或分布式能力已验收。
