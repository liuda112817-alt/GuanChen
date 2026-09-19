# Stage 1–10 代码 review 与整改记录（2026-09-19）

## 范围与依据

依据用户提供的冻结版 v1.0 建设规划（仓库参考文本 `docs/reference/项目规划.txt`），完整回归 Stage 1–10，重点逐条审查 Stage 9/10。代码起点 `110adb9`；Stage 1–8 的前次整改已包含在 `decc12a`。文档作为建设要求，不执行其中与本次 review 无关的操作指令。

最终阶段结论以 [统一基线报告](../reports/stage10_baseline/report.md) 与下述修复验证为准；不把前次 Stage 8 通过或本轮初始 mock 测试通过视为 Stage 10 已通过。

## 本次发现与整改

| 优先级 | 问题与影响 | 修复与验证 |
|---|---|---|
| P1 | MCP 为 v1/stdio，未提供规划要求的 v2 / Streamable HTTP | 依赖锁定官方 mcp 2.2.0，使用 MCPServer；HTTP 为默认演示入口，保留 stdio |
| P1 | MCP 启动给只接受 keyword 参数的数据库工厂传 positional 参数，真实启动失败 | 改为 database_url=；启动/关闭由 SDK lifespan 管理并释放 engine |
| P1 | MCP / KnowledgeEvaluator 调用不存在的 search，读取不存在的 content；MagicMock 掩盖问题 | 调用真实 retrieve / RetrievalResult.text；测试使用实际 dataclass，HTTP smoke 读取真实 DB |
| P1 | MCP smoke 只调用八字，知识和六爻未经外部客户端验证 | 自动启动独立 HTTP 进程，发现并成功调用三工具；测试鉴权与非法参数 |
| P1 | MCP 输入另起一份宽松模型，非法 method 会进入随机起卦；六爻输出丢失方法、爻值和随机事实 | 复用 BirthProfile、RetrievalFilter、ManualCastingInput，限定参数；返回完整领域事实 |
| P1 | 入口给匿名请求硬编码所有权限，权限测试未覆盖真实 HTTP | 回环 HTTP 强制 Bearer，配置 scopes 并传播至 registry；stdio 的本地用户信任边界明确 |
| P1 | 缺 scripts/run_evals.py；旧报告只有少量 capability 用例且无条件写 Stage 10 Passed | 统一真实回归/集成/MCP/Router/RAG/E2E，一次命令输出 JSON/Markdown；缺项和失败返回非零 |
| P1 | 观测只有零散入口与适配器，无法回答真实模型次数、token、检索来源、图节点成本 | 新增 AgentRun/RunStep、模型工厂 callback、重试计数、Tool/Retrieval/Graph hooks，实际预算拦截 |
| P1 | 缺 20 个固定端到端场景、完成率和逐路由基线 | 固定 20 场景/31 轮真实应用请求，校验来源、调用边界、更正、持久化、路由与成本 |
| P1 | 双领域 synthesizer 丢失八字事实、六爻嵌套引用和已完成工作流句柄 | 服务端保留各领域 facts/citations/thread_id；新增回归并通过真实双领域场景 |
| P1 | 梦境结构化输出有正文却无引用，重复生成仍违反契约，造成流程失败 | 无配对证据时丢弃传统文字/孤立引用，保留独立现实反思；未知证据 ID 仍拒绝，不编造引用 |
| P2 | 梦境回答把用户纠错当心理证据，或把乘车证据套用为散步 | 收紧解释条件与纠错语义，逐例审阅真实输出；不能仅依靠 citation ID 存在判断语义支持 |
| P1 | 六爻可召回其他卦的《周易》章节，模型借用其爻辞解释当前卦 | 基于确定性上下卦与章节元数据过滤；本卦/变卦分别适用，新增反例测试与真实场景复测 |
| P2 | 评测器缺失时静默跳过；预期错误可把任意内部异常算通过 | 未注册评测器报错，预期输入错误仅接受 ValueError；统一验收使用权威 fixture |
| P2 | 单元测试写入真实 reports/stage10_report.json，覆盖基线 | 改写 tmp_path，删除空用例却标记 100% 的旧占位报告；缺失/旧报告不作为新一轮通过证据 |
| P2 | trace 保存原始异常消息，metrics 无限保留每次耗时；正常 interrupt 记为错误 | 只存错误类别；有界样本及累计统计；HITL 单列 INTERRUPTED |
| P2 | SDK 参数校验失败发生在 registry 之前，缺少失败观测 | 官方 SDK middleware 从校验前跟踪；真实 SDK Client 失败路径测试 |
| P2 | tests/dream/test_runtime.py 实为重复的八字运行时代码，零测试 | 移除错置副本，替换为 Dream 无证据降级和伪造引用拒绝回归 |
| P2 | 43 项初始 Ruff 问题；文档同时宣称 Stage 8 完成、Stage 9 未开始和 Stage 10 通过 | 修复静态问题并更新 README、MCP、观测、评测和阶段状态文档 |

统一汇总器开发时发现的三领域名称误判已修正：冻结检索集为 bazi 30 / dream 10 / yijing 5，六爻知识包含在现有 yijing 评测范围，未降低已有召回门槛。

## Stage 1–8 全量回归覆盖

| 阶段 | 本轮核查与证据 |
|---|---|
| 1 | Settings、provider、同步/异步 LLM、结构化校验与有限重试；真实场景实际调用 DeepSeek；callback 记录每次请求 |
| 2 | lunar_python 固定四柱/边界 fixture、BirthProfile 校验、确定性 service/tool；MCP 与内部同一实现 |
| 3 | 原生 LangChain Tool Calling、排盘 artifact、模型/工具次数限制；补资料与更正后的实际 chart 全量一致 |
| 4 | 语料/切块/持久化/filter/hybrid retrieval、45 条 golden、真实回答 citation 与实际 retrieval/DB 对应 |
| 5 | 增量 DreamContext、人物更正、新梦隔离、传统/现实分段、无引用内容降级与伪造引用拒绝 |
| 6 | 手工/随机起卦事实与记录；确认前不调用，取消、修改重新确认、确认后一次起卦，持久化恢复 |
| 7 | 65 条真实 Router、双领域 LangGraph Send、参数前置检查、综合响应不丢事实、轻量/范围外短路 |
| 8 | PostgreSQL 资料写回、更正覆盖、会话/领域隔离、checkpointer 跨实例恢复与中断续跑；测试库隔离 |

## 已知边界

Reranker 历史实测 MRR 相对收益为负、增加延迟超过门槛，因此继续关闭；保存独立历史基线，当前生产路径为 RRF。此为规划允许的 gate 决策，不是未完成事项。

Stage 11 的 Safety/FastAPI/SSE/前端尚未建设，Stage 12 的公网部署/可靠性尚未建设。当前 Stage 10 结论不能用于宣称公网产品已验收。模型输出仍需在后续变更中按固定集持续复测。

## 最终验证

本轮统一命令 `python scripts/run_evals.py` 已通过，结果见 [Stage 10 基线报告](../reports/stage10_baseline/report.md)：

- 回归测试 397/397 通过；PostgreSQL 集成测试 42/42 通过（使用 `localhost:5432` 测试库）。
- MCP HTTP smoke 通过：Bearer 鉴权、非法输入拒绝、工具发现，并由官方 v2 Client 依次调用 `calculate_bazi`、`knowledge_search`、`cast_hexagram`。
- Router 主/次准确率均为 1.0；生产 RRF 路径 RAG Recall@5 为 0.9111。
- 固定 20 个 E2E 场景全部完成，完成率 1.0，provider network error 为 0；各路由均记录模型调用、工具调用、延迟、token 与错误类型。
- 八字 fixture 13/13、六爻 fixture/HITL 38/38；Ruff 与 diff 检查通过。

因此 Stage 1–10 满足冻结规划中的进入门槛，可以进入 Stage 11。Stage 11 的 Safety/FastAPI/SSE/前端仍属于后续建设范围。
