# GuanChen v2 Product Charter

- Status: **Frozen**
- Version: **v1.0**
- Scope: **GuanChen v2.0**

## 1. Product Name

**观尘 GuanChen v2**

产品定位：

> 面向中文用户的传统文化智能推演与知识服务 AI Agent Application。

通过确定性传统文化计算、可信知识检索、上下文理解和 Agent 工作流，为用户提供传统文化知识解释、结构化推演与现实反思服务。

---

## 2. Product Mission

GuanChen 的目标不是让 LLM “扮演算命先生”。

项目要探索的是：

> 如何把传统文化领域中的确定性计算、知识资料、开放语言理解和人机交互工作流，组合成一个边界清晰、来源可追溯、可评测、可部署的 AI Agent 系统。

系统中的不同任务由适合它的组件承担：

```text
确定性计算
→ Code / Library / Tool

知识事实
→ Retrieval / Controlled Corpus

语义理解
→ LLM

任务决策与工具选择
→ Agent

有状态、多步骤、需要暂停恢复的流程
→ Workflow / LangGraph

用户长期明确资料
→ Memory / Persistence
```

---

## 3. Target Users

### 3.1 传统文化兴趣用户

希望了解：

- 八字结构；
- 易经 / 六爻；
- 梦境文化象征；
- 传统文化概念与原典。

核心诉求：

> 不只看到结论，也能理解依据。

### 3.2 希望获得现实反思视角的用户

例如：

- 职业选择；
- 感情困惑；
- 当前生活状态；
- 梦境带来的情绪或疑问；
- 某个现实决策。

GuanChen 提供：

> 传统文化解释 + 现实情境反思

而不是替用户完成现实决策。

### 3.3 项目展示受众

包括：

- AI Agent / LLM Application Engineer 面试官；
- 技术同行；
- 项目代码审阅者。

他们关心的不只是输出，还包括：

- 为什么这里是 Agent？
- 为什么这里是 Tool？
- 为什么这里需要 RAG？
- 为什么 LangGraph 在 Stage 6 才引入？
- Memory 如何隔离？
- 系统如何评测？
- 一次失败运行如何追踪？
- 系统如何部署？

---

## 4. Core User Value

### 4.1 确定性事实与生成式解释分离

八字示例：

```text
BirthProfile
→ calculate_bazi Tool
→ BaziChart
→ LLM Interpretation
```

LLM 不负责计算四柱、十神、大运等确定性事实。

### 4.2 基于可追溯知识进行解释

```text
User Query
→ Retrieval
→ Evidence
→ Grounded Generation
→ Citation
```

知识不足时明确证据不足，不伪造原典。

### 4.3 多轮上下文理解

解梦等开放任务通过持续维护 `DreamRecord` 处理多轮补充。

重点是：

> 维护任务对象，而不是机械保存和注入全部聊天历史。

### 4.4 对关键步骤保留用户控制权

六爻流程：

```text
提出问题
→ 澄清
→ 用户确认
→ 起卦
→ 检索
→ 解释
```

用户确认以前不得执行起卦。

---

## 5. v2.0 Core Product Scope

### 5.1 Bazi Analysis Agent

职责：

> 根据用户提供的出生资料调用确定性排盘能力，并结合检索知识解释八字相关问题。

### 5.2 Dream Interpretation Agent

职责：

> 从自然语言梦境中识别关键元素，在多轮对话中维护 DreamRecord，并结合传统文化与现实情境提供多视角解释。

### 5.3 Liuyao Decision Reflection Agent

职责：

> 将模糊现实问题整理为明确问题，在用户确认后进行确定性起卦，并结合知识材料形成现实决策反思。

定位：

> 决策反思工具，而不是自动决策系统。

### 5.4 Traditional Culture Knowledge Agent

职责：

> 回答传统文化概念、术语、原典与比较类问题，并提供可追溯来源。

---

## 6. Product Experience Principles

### 6.1 先判断需求，再索取资料

知识问题不应先要求出生信息。

### 6.2 确定性问题不用 LLM 猜

历法、四柱、十神、大运、卦象等优先由确定性系统生成。

### 6.3 需要证据的问题尽量提供证据

知识解释以受控知识库为核心，不做运行时自由联网搜索。

### 6.4 Agent 只用于真正需要决策的地方

```text
确定性能力 → Tool / Service
语言理解、选择、解释 → Agent
```

### 6.5 工作流复杂度渐进引入

不在项目开始时同时引入 LangGraph、多 Agent、Redis、MCP 等全部组件。

### 6.6 用户应知道系统正在做什么

最终 Web 产品应能够呈现：

- 当前 Agent；
- Tool 状态；
- Retrieval 状态；
- Citation；
- HITL interrupt；
- 错误状态。

---

## 7. Responsibility Boundary

GuanChen 提供：

- 传统文化知识；
- 传统文化推演；
- 信息整理；
- 解释；
- 反思视角。

GuanChen 不定位为：

- 医疗诊断系统；
- 法律咨询系统；
- 投资决策系统；
- 心理诊断系统；
- 现实命令系统。

禁止把传统文化解释写成绝对现实结论。

---

## 8. Success Criteria

### Product

四个 Agent 能解决各自明确的问题，并最终通过统一网页完成主要用户流程。

### Engineering

项目最终真实具备并可以解释：

- Agent
- Tool
- RAG
- Context
- Memory
- Workflow
- HITL
- Multi-Agent Routing
- MCP
- Evaluation
- Observability
- Safety
- Streaming
- Persistence
- Production Deployment

但每项能力必须由真实业务需求驱动。

### Learning / Job Search

项目完成时，开发者能够：

- 独立解释整体架构；
- 理解并修改核心代码；
- 解释关键技术选型；
- 解释 Agent / Tool / RAG / Workflow 的边界；
- 说明系统如何评测；
- 说明失败运行如何排查；
- 展示真实线上 Demo。

---

## 9. One-Sentence Definition

> **观尘 GuanChen v2 是一个面向中文传统文化场景的垂直 AI Agent 应用，通过确定性计算、可追溯知识检索、多轮上下文与可恢复工作流，为用户提供传统文化解释、推演与现实反思服务。**

简短展示口径：

> **传统文化智能推演与知识服务 AI Agent Application。**
