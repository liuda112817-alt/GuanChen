# GuanChen v2 Stage 0 Frozen Artifacts Index

本包整理了 GuanChen v2 Stage 0 已冻结内容，可直接作为仓库正式产物的基础。

## Recommended Repository Structure

```text
GuanChen/
├── README.md
└── docs/
    ├── product_charter.md
    ├── agent_contracts.md
    ├── user_flows.md
    ├── domain_models.md
    ├── request_lifecycle.md
    ├── architecture.md
    ├── roadmap.md
    ├── backlog_v2_1.md
    ├── learning_knowledge_map.md
    └── adr/
        ├── 000-template.md
        ├── 001-use-lunar-python-for-bazi-calculation.md
        ├── 002-use-postgresql-pgvector-for-vector-storage.md
        ├── 003-use-ichingpy-for-liuyao-calculation.md
        ├── 004-introduce-langgraph-only-when-required.md
        └── 005-use-mcp-as-external-interoperability-layer.md
```

## Formal Stage 0 Required Artifacts

冻结规划明确要求的核心正式产物：

- `product_charter.md`
- `agent_contracts.md`
- `architecture.md`
- `roadmap.md`
- `backlog_v2_1.md`
- ADRs
- README skeleton

本包另外保留以下已经冻结、且后续工程会直接依赖的设计文档：

- `user_flows.md`
- `domain_models.md`
- `request_lifecycle.md`

以及学习治理文档：

- `learning_knowledge_map.md`

## Suggested Landing Procedure

1. 创建仓库根目录。
2. 复制 README.md。
3. 创建 docs/ 与 docs/adr/。
4. 按本包结构复制文档。
5. 检查 Markdown / Mermaid 渲染。
6. Git commit。
7. 提交这些文档做 Stage 0 Final Gate Review。
8. Gate PASS 后才开始 Stage 1。
