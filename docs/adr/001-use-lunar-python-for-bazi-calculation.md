# ADR-001: Use lunar_python for Bazi Deterministic Calculation

- Status: **Accepted**
- Stage: **Stage 0 / implemented in Stage 2**
- Decision Owners: GuanChen v2

## Context

GuanChen 的 Bazi Agent 需要稳定生成：

- 四柱；
- 五行；
- 十神；
- 大运等确定性排盘结果。

项目原则要求确定性计算不交给 LLM，并优先复用成熟库，而不是自行重写历法、干支、十神等基础算法。

## Decision

GuanChen v2 使用 `lunar_python` 作为八字基础计算引擎。

```text
BirthProfile
→ Bazi Calculation Service
→ lunar_python Adapter
→ BaziChart
```

业务层只认识 GuanChen 自己的 `BirthProfile` 和 `BaziChart`。

第三方对象不泄露到业务层。

## Rationale

1. 八字排盘属于确定性领域计算；
2. 项目重点是 Agent / LLM 应用工程，而不是自研历法；
3. 成熟库降低基础算法错误风险；
4. Adapter 隔离第三方 API；
5. fixed fixtures 可以验证确定性输出。

## Alternatives Considered

### Self-developed Bazi Calculation

Rejected.

原因：

- 偏离 Agent 学习主线；
- 正确性成本高；
- 会消耗大量时间在历法和流派细节；
- 不增加当前旗舰项目核心工程价值。

### Let LLM Generate Bazi Facts

Rejected.

确定性事实不能依赖概率性生成。

## Consequences

### Positive

- 可 fixture 测试；
- LLM 与确定性事实边界清晰；
- 第三方库升级影响被 Adapter 限制；
- Agent 只负责“什么时候调用”和“如何解释”。

### Negative / Trade-offs

- 依赖第三方库支持范围；
- 必须明确库默认规则；
- Adapter 字段映射是重要风险点；
- 需要固定依赖版本与 calculation contract。

## Scope

影响：

- Stage 2 Bazi Tool
- Stage 3 Bazi Agent
- Stage 4 Bazi + Retrieval
- Stage 9 MCP calculate_bazi

## Revisit Triggers

只有出现：

- `lunar_python` 严重不可用；
- 缺少 v2.0 必需计算字段；
- 无法适配的正确性问题；

才重新评估。

即使重新评估，也优先最小派生映射，不重写完整历法。
