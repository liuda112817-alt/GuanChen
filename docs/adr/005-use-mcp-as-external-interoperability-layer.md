# ADR-005: Use MCP as an External Interoperability Layer

- Status: **Accepted**
- Stage: **Stage 0 / implemented in Stage 9**
- Decision Owners: GuanChen v2

## Context

GuanChen 需要展示 MCP 能力，但不希望为了 MCP 重写已有业务。

Stage 9 只暴露成熟能力：

- calculate_bazi
- knowledge_search
- cast_hexagram

## Decision

MCP 架构位置：

```text
External Agent Host
→ MCP
→ GuanChen Existing Services
```

而不是：

```text
GuanChen internal Agent
→ MCP
→ GuanChen internal Tool
```

内部 Agent 继续直接调用已有 Tool / Service。

## Rationale

MCP 解决：

> 跨应用能力发现与标准化调用。

内部处于同一代码库、已知 contract，不需要额外协议层。

## Alternatives Considered

### Force All Internal Tools Through MCP

Rejected.

会增加：

- 协议层；
- 故障点；
- 延迟；
- 调试复杂度。

### Do Not Use MCP

Rejected.

GuanChen 有多个成熟 Tool，非常适合作为外部 Agent Host 可发现能力，也有明确 Agent 工程学习价值。

## Consequences

### Positive

- MCP 有真实业务落点；
- 内部系统保持简单；
- MCP Server 不复制业务逻辑；
- 可验证 schema interoperability。

### Negative / Trade-offs

- 同时存在 internal Tool interface 与 external MCP interface；
- 需要明确 contract 映射；
- MCP Server 必须避免成为第二套业务实现。

## Revisit Triggers

如果未来真正拆为多个独立服务或多个 Agent Host，需要统一跨进程能力调用时再评估。

v2.0 不讨论。
