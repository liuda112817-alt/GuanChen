# GuanChen v2.1 Backlog

- Status: **Active Backlog**
- Applies To: ideas explicitly excluded from v2.0
- Rule: **Record only. Do not pre-implement in v2.0.**

---

# 1. v2.0 Non-goals

v2.0 明确不做：

- 第五业务 Agent；
- 真太阳时 / 天文修正；
- 地理编码参与八字核心排盘；
- 自研农历 / 干支 / 十神 / 大运 / 六十四卦基础算法；
- LLM fine-tuning；
- Embedding fine-tuning；
- Reranker fine-tuning；
- Knowledge Graph；
- Agentic RAG；
- 运行时自由联网搜索；
- 大规模网页抓取；
- 向量化长期记忆；
- 自动人格画像；
- 自动从所有聊天抽取长期事实；
- 大规模 LLM-as-a-Judge 平台；
- “Agent debate / voting” 等无业务必要的多 Agent 演示结构；
- 3–4 Agent 同轮会诊；
- 动态创建 Agent；
- 内部运行链强制 MCP 化；
- WebSocket；
- 完整前端重写；
- 支付 / 会员 / 社区 / CMS / 原生 App；
- Kubernetes；
- Kafka；
- Celery；
- 微服务拆分；
- Service Mesh；
- 多区域高可用。

---

# 2. Current v2.1 Backlog

## 2.1 True Solar Time / School Configuration

### Problem / Motivation

部分八字流派会采用真太阳时或更细流派规则。

### Candidate Scope

```text
birth place
→ geocoding
→ longitude
→ solar time correction
→ configurable Bazi calculation method
```

### Why Not v2.0

- 领域存在流派争议；
- 增加地理编码和天文计算；
- 对当前 Agent / LLM 工程学习主线价值较低；
- v2.0 先保证确定性排盘契约稳定。

### Revisit Trigger

v2.1 需要增强八字流派可配置性时重新评估。

---

## 2.2 New Domain Agents

候选：

- 紫微斗数；
- 风水；
- 其他传统文化业务域。

v2.0 不实施。

---

## 2.3 Multimodal Traditional-Culture Features

候选：

- 户型图；
- 手相；
- 面相。

需要单独评估多模态模型、隐私和产品价值。

---

## 2.4 Agentic RAG

候选：

- query planning；
- iterative retrieval；
- retrieval self-reflection。

只有 Stage 4 固定 Hybrid Retrieval 不能满足真实需求时重新评估。

---

## 2.5 Vectorized Long-term Memory / Automatic Memory Extraction

当前 v2.0 只保存用户明确提供 / 确认的结构化资料。

未来如出现真实跨任务语义检索需求，再评估向量化长期记忆。

---

## 2.6 Admin Corpus Management

候选：

- corpus upload；
- metadata management；
- ingestion status；
- corpus versioning。

v2.0 不建设 Admin CMS。

---

## 2.7 Account / OAuth / Membership / Payment

v2.0 只做最小匿名 / session identity。

商业账号能力未来另行评估。

---

## 2.8 Complex Model Routing / Model Fallback / A-B Testing

只有在真实质量、成本或可用性数据出现后重新评估。

---

## 2.9 Distributed Production Architecture

候选：

- Kubernetes；
- replicas；
- message queue；
- service split。

只有实际流量 / reliability 需求证明单机 Docker Compose 不够时重新评估。

---

# 3. Scope Rules

## Rule 1 — Current Stage Tasks Only

新想法第一问：

> 是否属于当前 Stage 固定任务？

如果不是，默认进入 Backlog / Parking Lot。

## Rule 2 — Non-blocking Optimization Does Not Change DoD

非阻塞优化：

```text
→ observation / backlog
→ continue current Stage
```

## Rule 3 — Only Three Blocker Types May Change Frozen Scope

- correctness blocker
- safety blocker
- unrunnable blocker

遇到 blocker：

```text
confirm blocker
→ check predefined fallback
→ use fallback if available
→ otherwise minimal alternative
→ record ADR
```

## Rule 4 — Gate Failure Means Fix Current Stage

不得提前进入下一 Stage。

## Rule 5 — Backlog Is Not a Pre-implementation Zone

放入 Backlog 表示：

> 只记录，不写 class、不加字段、不提前接依赖。

## Rule 6 — Parking Lot Labels

讨论出现后续阶段概念时：

```text
[Parking Lot / Stage X]
```

可以解释概念，但不进入实现。

## Rule 7 — Industry Popularity Is Not a v2.0 Requirement

“大家都在用”不是引入新技术的理由。

新组件必须回答：

1. 它解决了什么已经出现的问题？
2. 当前方案为什么不足？
3. 它是否明显增加 GuanChen 的真实工程价值？
