# Stage 10 观测设计

`AgentRun` 记录 trace_id、route、status、总耗时、模型与工具调用次数及硬上限；`RunStep` 记录 agent、node、tool、kind、latency_ms、token、error、retrieved_chunk_ids、status。

Application 每次请求创建独立 tracer，ContextVar 传播到 LangGraph、异步双领域分支和领域工具。MCP 使用官方 SDK middleware 从协议校验前开始跟踪，再沿 registry → adapter → service 传播同一 trace_id。

- LLM：模型工厂装配 LangChain callback，覆盖 LLMClient 和八字原生 Agent；每次重试单独计数，读取 provider usage_metadata，未知 token 显式为 null。
- Tool：排盘、八字知识工具、手工/随机起卦 service 边界计数，在工具执行前检查预算。
- Retrieval：统一 retrieve hook 记录实际 chunk IDs，禁止记录原始知识文本。
- Graph：Conversation 各业务节点、六爻各节点与 Agent 调用记录耗时；正常 GraphInterrupt 标记 INTERRUPTED，不作为应用失败。
- Application：结束时写 metadata-only AgentRun JSON 至 stderr，可用 trace_sink 保存报告。无 prompts、完整出生资料、梦境或回答文本。
- 异常：只记录异常类型，不记录 provider body、校验器输入或 str(exc)。

每个路由请求统一硬上限为 **20 次实际模型调用 / 4 次业务 Tool 调用**；LLMClient 最多配置 5 次重试，八字另有 3 次模型 / 每工具 1 次限制，LangGraph 也有递归上限。预算在回调/工具边界执行，非事后统计。

MetricsCollector 累计计数与累计均值；每指标只保留最近 1000 个耗时样本。评测 p50/p95 直接按固定场景的每次完整请求计算，报告同时包含失败分类和未知 token 次数，不假设货币价格。

项目日志默认 stderr，不污染 stdio MCP。LangSmith 可通过 LangChain 标准环境变量选择启用；默认不需要账号、key 或外部 SaaS。可观测性不自行打开远程 tracing。
