# ADR-003: Use ichingpy for Liuyao Deterministic Calculation

- Status: **Accepted**
- Stage: **Stage 0 / implemented in Stage 6**
- Decision Owners: GuanChen v2

## Context

Liuyao Agent 需要稳定产生：

- 起卦结果；
- 卦象确定性结构；
- 项目真正使用的装卦相关信息。

解释仍由 Retrieval + LLM 完成。

## Decision

使用 `ichingpy` 作为六爻确定性计算基础库。

```text
cast input
→ ichingpy Adapter
→ HexagramResult
```

## Rationale

核心边界：

```text
确定性卦象
→ code / library

卦象知识解释
→ Retrieval + LLM
```

LLM 不同时承担“生成卦象”和“解释卦象”。

## Alternatives Considered

### Self-developed Full Liuyao Engine

Rejected.

原因：

- 流派与规则复杂；
- 会消耗大量非 Agent 工程时间；
- v2.0 只需要满足冻结业务流程。

### Let LLM Randomly Cast

Rejected.

随机过程必须由程序执行，并向用户透明说明。

## Consequences

### Positive

- 固定输入可 fixture 测试；
- HexagramResult 保持确定性；
- Tool 和 Agent 责任清晰。

### Negative / Trade-offs

- 依赖 `ichingpy` 实际能力；
- Stage 6 必须验证真实 API；
- 不假设覆盖所有六爻流派；
- 业务 schema 只保留实际需要的数据。

## Revisit Triggers

只有当：

- `ichingpy` 严重不兼容；
- 无法产生 v2.0 必需的确定性结构；

才允许考虑最小自研 fallback。
