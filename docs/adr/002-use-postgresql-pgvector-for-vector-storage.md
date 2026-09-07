# ADR-002: Use PostgreSQL + pgvector for Vector Storage

- Status: **Accepted**
- Stage: **Stage 0 / implemented from Stage 4**
- Decision Owners: GuanChen v2

## Context

Stage 4 需要建立项目唯一的共享 Retrieval Service。

Stage 8 同时需要 PostgreSQL 存储：

- profiles；
- conversations；
- domain records；
- long-term memory；
- agent runs。

当前项目没有证据需要独立向量数据库服务。

## Decision

使用：

```text
PostgreSQL + pgvector
```

作为 GuanChen v2 的向量存储方案。

```text
PostgreSQL
├── business data
├── memory
├── conversations
├── agent runs
└── knowledge chunks + vectors
```

## Rationale

当前规模下：

> 减少基础设施数量比追求独立向量数据库的极限能力更重要。

## Alternatives Considered

### Chroma

适合快速本地原型，但 GuanChen 最终已经需要 PostgreSQL。

再引入一个独立 Vector Store 对当前规模收益有限。

### Qdrant / Milvus

具有更专业的向量检索能力，但会：

- 增加基础设施；
- 增加部署与运维成本；
- 与“不过度架构”原则冲突。

当前没有真实性能证据证明需要。

## Consequences

### Positive

- 一套数据库承载业务数据和向量；
- Stage 8 直接复用 Stage 4 PostgreSQL；
- 减少生产服务数量；
- metadata filtering 与 SQL 统一。

### Negative / Trade-offs

- 业务数据与向量检索共享基础设施；
- 超大规模向量检索不是当前目标；
- 需要学习 pgvector；
- ingestion / retrieval schema 必须严格一致。

## Revisit Triggers

只有出现真实证据：

- 向量规模显著扩大；
- PostgreSQL 成为性能瓶颈；
- 需要 pgvector 无法提供的关键检索能力；

才评估独立 Vector DB。

不能仅因为“专用向量库更专业”而替换。
