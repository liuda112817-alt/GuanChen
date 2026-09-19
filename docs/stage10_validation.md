# Stage 10 验收门槛

唯一完整入口：`uv run python scripts/run_evals.py`。实际结论见 [JSON](../reports/stage10_baseline/report.json) / [Markdown](../reports/stage10_baseline/report.md)。

| 规划要求 | 当前验证方式 |
|---|---|
| 复用 Stage 1–8 必测资产 | 默认 pytest + 独立 PostgreSQL integration；报告提取真实八字 fixture / 六爻 HITL 结果 |
| MCP 外部互操作 | 独立 HTTP 服务 + 官方 SDK v2 客户端发现并调用全部三个真实 service |
| Router 准确率 | 65 条 full-chain，主/次意图分别统计，不允许 rules-only 冒充完整通过 |
| RAG Recall@5 | 冻结 45 条、bazi/dream/yijing 三领域，各领域及总体门槛 |
| AgentRun / RunStep | app / MCP / LLM / Tool / Retrieval / Graph 同一请求 trace，stderr JSON |
| 成本与上限 | 实际模型调用（包含重试）、业务工具调用、输入输出 token、p50/p95、错误类型 |
| 端到端 | 20 个固定场景、多轮共 31 次请求；流程、来源、错误 Agent/Tool、边界检查 |
| 人工审阅 | 保存合成场景回答与逐例审阅要点；语义审阅结论见本轮 review 文档 |
| 失败不可伪装成功 | 缺报告、缺评测器、子命令失败、缺领域、缺 token 均不能通过 |
| 本地可复现 | 不依赖 LangSmith；数据库、模型、语料是显式前置依赖 |

正常 HITL interrupt 不算失败。模型网络故障单列，但不从总完成率分母删除。旧报告的无条件 PASS 文本已移除，单元测试只写临时目录。
