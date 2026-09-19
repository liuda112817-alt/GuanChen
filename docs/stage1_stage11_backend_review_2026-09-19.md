# GuanChen v2 Stage 1–11 后端 Review

日期：2026-09-19  
范围：冻结规划 v1.0 要求的 Stage 1–11；本轮按用户要求只验收后端，Bolt UI 不纳入本轮交付。

## 结论

Stage 1–11 后端建设达到进入下一阶段的条件，统一门禁为 **PASS**。Stage 1–10 重新执行既有回归、集成、MCP、路由、检索、可观测性和固定端到端场景；Stage 11 额外执行真实 FastAPI + PostgreSQL + 模型调用验收。

证据：

- [统一 Stage 1–11 报告](../reports/stage11_final/report.md)
- [Stage 11 API 验收报告](../reports/stage11_backend/report.md)
- [Bolt 后端 API 合同](stage11_backend_api.md)
- [回答表达与模型选择设计](response_style.md)

本轮还完成了统一回答表达层：最终合成及八字、梦境、六爻解释共享一套“松弛、机锋、清醒”的中文语气规范；抽取、确定性计算和安全分类仍保持严格结构化。表达风格不复制任何具体角色台词，也不改变事实、引用和安全边界。

## Review 覆盖

| 阶段 | 复核重点 | 结果 |
|---|---|---|
| 1 | LLM 抽象、结构化输出、配置和异常归一化 | 通过既有回归 |
| 2–3 | Bazi 确定性计算与单 Agent 循环 | 13/13 fixture，通过端到端 |
| 4–5 | pgvector 检索、引用链路、Dream Agent | Recall@5 0.9111，通过端到端 |
| 6 | Liuyao HITL、起卦前确认和恢复 | 38/38 fixture，Stage 11 真实恢复通过 |
| 7 | 多 Agent 路由和边界 | Router accuracy 1.0 / secondary 1.0 |
| 8 | 会话、出生资料和 PostgreSQL 持久化 | 集成与重启恢复通过 |
| 9 | MCP v2 / Streamable HTTP 工具互操作 | MCP 门禁通过 |
| 10 | 评测、Tracing、token/cost、错误和超时观测 | 回归与 observability 门禁通过 |
| 11 | Safety、FastAPI、SSE、匿名会话、Profile/Citation、Resume | 真实 API 验收全部通过 |

## Stage 11 发现并修复的缺口

1. 补齐 FastAPI 生命周期、版本化 API、CORS、请求校验、统一错误响应和超时取消。
2. 补齐匿名 session token 的哈希存储与跨请求授权，阻断跨会话读取。
3. 补齐 `start/route/need_input/tool_start/tool_end/retrieval/token/interrupt/done/error` SSE 事件合同。
4. 补齐 Liuyao 的确认、修改、取消、过期确认、重启恢复和幂等保护；修改不会重复起卦。
5. 补齐显式危机、医疗、投资、法律高风险规则与结构化分类器边界，并阻止确定性死亡、疾病、灾难断言。
6. 补齐 Profile readiness、Citation 只读授权、错误脱敏和 output safety；修复 Stage 10 run telemetry 在 API 分支中的回归。
7. 增加统一回答风格 Prompt 与 thinking 配置；将本地模型配置从兼容旧名切换到官方规范名 `deepseek-flash`，默认关闭 thinking，保留显式开启高推理强度的部署开关。

## 验收数据

- Python 回归：468 passed，44 deselected。
- PostgreSQL 集成：43 passed。
- Stage 11 API acceptance：报告中的全部检查为 True。
- Router accuracy：1.0；RAG Recall@5：0.911111；Bazi fixtures：13/13；Liuyao fixtures：38/38。
- 固定 E2E completion：1.0；provider network errors：0。
- `localhost:5432` 已连接并用于真实 PostgreSQL 验收。
- `ruff check .` 与 `git diff --check` 通过。

## 边界

Bolt 前端页面尚未在本仓库实现，前端只需按 [stage11_backend_api.md](stage11_backend_api.md) 消费 API/SSE 合同。Redis、多 worker 公网部署、限流和生产运维属于 Stage 12，不作为本轮后端门禁。
