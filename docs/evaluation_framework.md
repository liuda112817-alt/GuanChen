# Stage 10 统一评测

```powershell
uv run python scripts/run_evals.py
```

默认生成 `reports/stage10_baseline/report.json` 与 `report.md`，各阶段原始证据、JUnit 和执行日志位于同目录。需要已配置的 LLM、已导入语料的 PostgreSQL/pgvector 与本地 BGE 模型；只有 integration 套件会清理独立的 `guanchen_test` 数据库，真实端到端使用合成用户资料和唯一 session。

执行顺序：默认回归 → PostgreSQL 集成 → 独立 HTTP MCP smoke → Router 65 条 full-chain → Retrieval 45 条生产 RRF → 20 个端到端场景。串行执行重型进程，避免在本机并发加载多个 BGE/Torch 实例。

统一复用 tests/bazi 固定四柱/节气 fixture、tests/liuyao 起卦和 HITL fixtures、evals/router、evals/retrieval。不得用只检查字段存在的 toy cases 替代权威 fixture。

评测场景 `evals/e2e/stage10_cases.json` 包含完整多轮业务及人工审核要点；e2e.json 保存**合成资料**的输出供人工核查。自动验收校验完成状态、选中 Agent、工具次数、确认边界、资料持久化、更正和梦境隔离、citation 与实际检索/数据库的对应关系，不把这些结构检查冒充事实语义总评分。

Gate：命令全部成功、Router gate、RRF 总 Recall@5 ≥ 0.85 且每领域 ≥ 0.80、MCP 三工具真实成功、20 场景完成率 ≥ 95%、token 和调用上限可回答。模型供应商网络异常单列，失败场景仍留在总完成率分母中，不靠排除失败刷高通过率。

报告缺失、过期、测试失败都不能通过；最终退出码 0=通过、1=失败。旧 `python -m guanchen_v2.evaluation.stage10_report` 兼容入口调用同一完整套件，不再无条件生成 PASS。

Reranker 的既有实测保存在 `evals/retrieval/stage4_reranker_baseline.json`；因收益/延迟未过 gate，生产保持关闭，统一命令验证实际 RRF 路径。后续若改 reranker，需重新运行完整 Stage 4 benchmark。

基线不是对未来模型波动的保证；每次重要变更都应重新执行此命令。人工语义审核结论与本轮 review 一并保存在 docs。
