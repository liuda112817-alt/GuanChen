# GuanChen v2 Unified Request Lifecycle

- Status: **Frozen**
- Version: **v1.0**

本文件描述系统级逻辑生命周期，不等于具体 LangGraph / FastAPI 实现。

---

# 1. Core Lifecycle

```text
1. User Request

2. Request Context Initialization

3. Safety Pre-check

4. Load Minimal Routing Context

5. Route

6. Requirement Check
   ├── NeedUserInput / HITL
   └── Ready

7. Load Selected Domain Context

8. Execute Selected Agent(s)

9. Tool / Retrieval As Needed

10. Response Composition + Citation

11. Explicit / Confirmed Memory Update

12. Complete
```

Cross-Cutting Concerns：

- Trace / Observability
- Persistence / Checkpoint
- Error Handling
- Streaming / SSE

---

# 2. Request Context Initialization

建立最小运行上下文，例如：

- current message；
- session identity；
- request metadata。

注意：

> Request Context ≠ Domain Memory Context

此时不加载用户全部长期 Memory。

---

# 3. Safety Pre-check

目标：

> 在传统文化推演链开始以前，判断请求是否应该进入专业 Agent。

主要出口：

```text
Allowed → continue

Blocked / Redirected
→ Safe Direct Response
→ Complete
```

具体 Safety 规则已在 Stage 11 后端实现，HTTP/SSE 层统一复用同一 SafetyService。

---

# 4. Load Minimal Routing Context

Router 有时需要少量历史上下文理解连续对话。

例如：

```text
Round 1: “昨晚我梦到掉牙。”
Round 2: “而且当时我特别害怕。”
```

第二句需要最小会话上下文才能可靠路由。

原则：

> 只加载确定当前意图所需的最小 Routing Context。

不加载全部 UserProfile / Dream / Bazi / Liuyao 历史。

---

# 5. Route

目标意图：

- BAZI
- DREAM
- LIUYAO
- KNOWLEDGE
- CHITCHAT
- OUT_OF_SCOPE

Stage 7 才实现：

- rule + structured LLM router；
- secondary intent；
- confidence；
- 最多显式双领域。

---

# 6. Requirement Check

## Bazi

需要个人排盘时检查 BirthProfile 必要字段。

缺失：

```text
→ NeedUserInput
→ calculate_bazi calls = 0
```

## Dream

没有固定必填字段。

只检查是否存在会显著影响解释的关键语义缺口。

## Liuyao

检查：

- 问题是否足够明确；
- 是否进入 clarification；
- 是否需要 user confirmation。

## Knowledge

一般直接 Ready。

知识问题不得要求 BirthProfile。

---

# 7. NeedUserInput Semantics

```text
NeedUserInput
≠ Error
```

它是正常产品状态。

正确行为：

```text
NeedUserInput
→ 保存当前任务必要状态
→ 用户补充
→ 恢复当前任务
```

具体持久化实现按 Stage 渐进：

- Stage 3：普通 Python 会话；
- Stage 6：HITL；
- Stage 8：跨进程 persistence。

---

# 8. Load Selected Domain Context

Route / Requirement 确定后，只加载选中领域真正需要的上下文。

```text
Bazi
→ BirthProfile + relevant recent context

Dream
→ current DreamRecord

Liuyao
→ current DecisionQuestion

Knowledge
→ normally no unrelated personal memory
```

原则：

> Route enough to know the domain; then load only the context needed by that domain.

---

# 9. Execute Selected Agent(s)

进入已经冻结的领域 Agent Contract。

单 Agent 默认只处理自身领域任务。

Stage 7 才允许显式双领域最多两个 Agent。

---

# 10. Tool / Retrieval As Needed

不是所有 Agent 都执行所有能力。

```text
Bazi
→ calculate_bazi
→ Retrieval when needed

Dream
→ Retrieval
→ no fake deterministic dream calculator

Liuyao
→ cast after confirmation
→ Retrieval

Knowledge
→ Retrieval
→ no user-specific calculation Tool
```

禁止全局预先 RAG。

---

# 11. Failure Semantics

## Tool Failure

说明确定性事实没有成功产生。

不能假装：

```text
BaziChart / HexagramResult exists
```

## Retrieval Failure

可能出现：

```text
Deterministic fact valid
+ Evidence insufficient
```

此时确定性事实仍有效，但知识型解释必须降级。

因此：

```text
Tool Failure
≠
Retrieval Failure
```

---

# 12. Response Types

系统级响应可能包括：

- Normal Response
- NeedUserInput
- HITL Interrupt
- Safe Response
- Out-of-scope Response
- Error / Degraded Response

使用 Retrieval 的回答应携带 KnowledgeCitation。

Tool 事实与 Retrieval Citation 必须概念分离。

---

# 13. Explicit / Confirmed Memory Update

长期 Memory 只保存：

> 用户明确提供 / 更正 / 确认的结构化信息。

禁止：

```text
LLM 自动总结人格
→ 永久 Memory
```

Thread / Workflow State Persistence 与 Long-term Memory 不同：

```text
当前六爻停在 confirmation
→ checkpoint / workflow persistence

用户确认的 BirthProfile
→ long-term business persistence
```

---

# 14. Cross-Cutting Concerns

## Trace / Observability

Trace 覆盖：

- LLM
- Tool
- Retrieval
- Graph Node
- Response

不是最后才执行一次。

## Streaming / SSE

SSE 是传输 / 展示通道。

未来可发出：

- start
- route
- need_input
- tool_start
- tool_end
- retrieval
- token
- interrupt
- done
- error

它不是单独的最后业务节点。

---

# 15. Example Requests

## Knowledge

```text
“什么是十神？”
→ Safety
→ KNOWLEDGE
→ Ready
→ Retrieval
→ Grounded Response + Citation
```

## Bazi Missing Data

```text
“帮我看看八字。”
→ BAZI
→ Missing BirthProfile
→ NeedUserInput
→ no tool call
```

## Dream Continuation

```text
“刚才那个梦里其实追我的是高中同学。”
→ minimal routing context
→ DREAM
→ load current DreamRecord
→ correction / merge
→ Retrieval if needed
→ updated interpretation
```

## High-Risk Liuyao Request

Safety 必须能够在专业起卦流程前处理明确高风险请求。

具体策略已在 Stage 11 后端实现；明确高风险请求在起卦前被拦截，模糊风险进入结构化分类器。
