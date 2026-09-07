# ADR-004: Introduce LangGraph Only When Workflow Requirements Justify It

- Status: **Accepted**
- Stage: **Stage 0 / first custom workflow in Stage 6**
- Decision Owners: GuanChen v2

## Context

GuanChen 会使用 LangGraph，但项目不希望从第一天就把所有 Agent 设计成复杂 StateGraph。

Bazi Stage 3 不需要自定义 Graph。

Liuyao Stage 6 首次出现真实需求：

```text
clarify
→ interrupt
→ confirm
→ cast
→ retrieve
→ interpret
```

Stage 7 再出现统一多 Agent orchestration。

## Decision

自定义 LangGraph workflow 的正式引入时间冻结为：

```text
Stage 6
```

用于 Liuyao HITL。

Stage 7 用于 ConversationGraph / limited multi-Agent orchestration。

Stage 1–5 不为了统一技术栈强制 Graph 化。

## Rationale

> Complexity must be earned by requirements.

LangGraph 的使用必须对应真实需求，例如：

- state
- branch
- loop
- pause/resume
- HITL
- fan-out/fan-in
- durable workflow

## Alternatives Considered

### Use LangGraph from Stage 1

Rejected.

问题：

- 过早增加抽象；
- 很难解释真实必要性；
- 破坏渐进式架构演进。

### Never Use LangGraph

Rejected.

Liuyao 的 interrupt / resume / modify / cancel，以及 Stage 7 orchestration 都是真实 workflow 需求。

## Consequences

### Positive

- 每项架构都有需求来源；
- 能展示普通 Python → Agent → Workflow 的演进；
- 避免所有逻辑强塞进 Graph。

### Negative / Trade-offs

- 项目不会从第一天拥有统一运行模型；
- Stage 7 需要进行顶层编排整合；
- 部分代码路径会经历自然演进。

## Revisit Triggers

不因框架流行程度改变。

只有真实业务 workflow 发生变化时重新评估。
