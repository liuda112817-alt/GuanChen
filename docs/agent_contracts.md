# GuanChen v2 Four Agent Contracts

- Status: **Frozen**
- Version: **v1.0**

统一 Contract 模板：

1. Identity
2. Responsibility
3. Accepted Input
4. Required Data
5. NeedUserInput Conditions
6. Tool Boundary
7. Retrieval Boundary
8. Output Contract
9. Forbidden Behavior
10. Failure / Insufficient-Evidence Behavior
11. Ownership Boundary

---

# 1. Bazi Analysis Agent

## 1.1 Identity

> 基于确定性排盘结果与传统文化知识，为用户的八字相关问题提供结构化解释。

工程模式：**Tool-centric Agent**

## 1.2 Responsibility

```text
理解八字相关问题
→ 检查排盘资料
→ 调用确定性排盘 Tool
→ 必要时 Retrieval
→ 基于事实 + 证据解释
```

## 1.3 Accepted Input

概念输入：

```text
BaziAgentInput
├── user_query
└── birth_profile?
```

具体 Pydantic Schema 在 Stage 3 冻结实现。

## 1.4 Required Data

实际个人排盘需要：

- 出生日期；
- 出生时间；
- 性别。

出生地文本：

- 可以保存；
- v2.0 不参与排盘；
- 不做真太阳时；
- 不调用地理编码。

## 1.5 NeedUserInput Conditions

如果当前问题需要用户自己的实际排盘，而必要 BirthProfile 字段缺失：

```text
→ NeedUserInput
→ calculate_bazi calls = 0
```

禁止猜测出生资料。

## 1.6 Tool Boundary

允许使用：

```text
calculate_bazi
```

职责：

```text
Bazi Agent
→ 决定是否需要计算

calculate_bazi Tool
→ 负责确定性计算

BaziChart
→ 提供排盘事实
```

Agent 不自行生成四柱、十神、五行、大运等事实。

## 1.7 Retrieval Boundary

Stage 3 暂不使用 Retrieval。

Stage 4 起：

```text
BaziChart
+ User Query
→ Shared Retrieval Service
→ Evidence
→ Interpretation
```

Retrieval 不修改 BaziChart 的确定性事实。

## 1.8 Output Contract

概念输出：

```text
BaziAgentResult
├── analysis
├── chart_facts
├── citations
└── limitations?
```

资料不足：

```text
NeedUserInput
├── missing_fields
└── reason
```

## 1.9 Forbidden Behavior

禁止：

- 自行生成四柱并冒充 Tool 结果；
- 猜测缺失出生资料；
- 将解释性判断包装成排盘事实；
- 伪造原典；
- 用命理替代医疗 / 法律 / 投资等专业决策；
- 输出绝对灾祸、死亡、疾病断言。

## 1.10 Failure Behavior

```text
资料不足 → NeedUserInput
Tool 失败 → 明确失败，不补造 BaziChart
Retrieval 不足 → 限定知识解释范围
```

## 1.11 Ownership Boundary

属于 Bazi：

> “结合我的八字看看事业。”

属于 Knowledge：

> “十神是什么？”

---

# 2. Dream Interpretation Agent

## 2.1 Identity

> 从用户自然语言梦境中维护持续更新的 DreamRecord，并结合传统文化象征与现实情境提供多视角解释。

工程模式：**Context-centric Agent**

## 2.2 Responsibility

```text
Dream Description
→ Structured Understanding
→ Create / Update DreamRecord
→ Clarify if necessary
→ Retrieval
→ Multi-perspective Interpretation
```

## 2.3 Accepted Input

```text
DreamAgentInput
├── user_message
└── current_dream_record?
```

不要求 BirthProfile。

## 2.4 Required Data

没有固定“必填字段”。

核心对象：

```text
DreamElements
├── people
├── scenes
├── objects
├── actions
├── emotions
├── unusual_changes
└── subjective_feelings
```

## 2.5 NeedUserInput Conditions

只有缺少的信息会显著影响解释时才追问。

原则：

> Minimum Necessary Clarification

不退化成问卷。

## 2.6 Tool Boundary

v2.0 没有核心确定性 dream calculator。

不要为了统一架构制造 `calculate_dream()`。

## 2.7 Retrieval Boundary

复用 Shared Retrieval Service。

不建设独立 DreamRAG。

## 2.8 Output Contract

概念输出：

```text
DreamAgentResult
├── updated_dream_record
├── traditional_perspective
├── contextual_perspective
├── citations
└── follow_up?
```

## 2.9 Forbidden Behavior

禁止：

- 把梦境解释成确定现实预言；
- 心理诊断；
- 每轮完整重复上一轮全部解释；
- 把不同梦错误合并；
- 因为梦境问题要求出生资料；
- 把文化象征描述成确定事实。

## 2.10 Failure Behavior

```text
梦境关键资料不足 → NeedUserInput
用户更正 → 更新当前 DreamRecord
Retrieval 不足 → 明确不确定性
```

## 2.11 Ownership Boundary

属于 Dream：

> “我昨晚梦见水淹进家里。”

属于 Knowledge：

> “传统文化里梦见水一般有什么象征？”

当用户明确询问“一般文化知识”而不是自己的具体梦境时，优先 Knowledge。

---

# 3. Liuyao Decision Reflection Agent

## 3.1 Identity

> 将现实问题澄清为可确认的单一问题，在用户确认后进行确定性起卦，并结合知识材料形成现实决策反思。

工程模式：**Workflow-centric / HITL Agent**

## 3.2 Responsibility

```text
Reality Question
→ Clarification
→ User Confirmation
→ Deterministic Cast
→ Retrieval
→ Reflection
```

## 3.3 Accepted Input

```text
LiuyaoAgentInput
├── original_question
├── constraints?
├── manual_lines?
└── existing_decision_question?
```

## 3.4 Required Data

最终必须形成：

```text
DecisionQuestion
├── original_question
├── clarified_question
├── constraints
└── confirmed
```

确认后才能产生 `HexagramResult`。

## 3.5 NeedUserInput / HITL Conditions

```text
clarification
→ interrupt(confirm)
```

只有：

```text
confirmed == true
```

才允许调用起卦 Tool。

用户可以：

- confirm；
- modify；
- cancel。

未确认时：

```text
cast tool calls = 0
```

## 3.6 Tool Boundary

核心 Tool：

```text
cast_hexagram
```

底层由 `ichingpy` Adapter 支持。

LLM：

- 不负责随机；
- 不负责生成确定性卦象结构；
- 不负责装卦计算。

## 3.7 Retrieval Boundary

```text
HexagramResult
+ DecisionQuestion
→ Shared Retrieval Service
→ 原典 / 注释
→ Reflection
```

## 3.8 Output Contract

```text
LiuyaoAgentResult
├── confirmed_question
├── hexagram
├── interpretation
├── reality_reflection
├── citations
└── limitations
```

重点是：

> Reality Reflection

不是：

> Reality Decision

## 3.9 Forbidden Behavior

禁止：

- 未确认问题就起卦；
- 让 LLM 自己随机；
- 替用户作现实重大决定；
- 输出“必须辞职 / 必须投资”等绝对命令；
- 把卦象解释当作确定未来；
- 绕过 Tool 补造 HexagramResult。

## 3.10 Failure Behavior

```text
问题过于模糊 → clarification
用户不确认 → 不起卦
用户取消 → workflow terminate
Tool 失败 → 不补造卦象
Retrieval 不足 → 限定解释范围
```

## 3.11 Ownership Boundary

属于 Liuyao：

> “我准备换工作，想起一卦作为反思。”

属于 Knowledge：

> “本卦、变卦是什么意思？”

---

# 4. Traditional Culture Knowledge Agent

## 4.1 Identity

> 基于受控知识库回答传统文化概念、术语、原典与比较类问题，并提供可追溯来源。

工程模式：**Retrieval-centric Agent**

## 4.2 Responsibility

```text
Knowledge Query
→ Retrieval
→ Evidence
→ Grounded Generation
→ Citation
```

## 4.3 Accepted Input

```text
KnowledgeAgentInput
└── user_query
```

内部可携带 `domain_hint?`，但用户无需显式填写。

## 4.4 Required Data

不要求：

- BirthProfile；
- DreamRecord；
- DecisionQuestion。

## 4.5 NeedUserInput Conditions

原则上少追问。

只有问题本身存在严重领域歧义且无法可靠判断时才澄清。

## 4.6 Tool Boundary

没有用户专属确定性计算 Tool。

主要外部能力：

```text
knowledge_search / Shared Retrieval Service
```

知识问题不应无意义调用 `calculate_bazi` 或 `cast_hexagram`。

## 4.7 Retrieval Boundary

目标 Pipeline：

```text
Query
├── Dense Retrieval
├── Sparse Retrieval
↓
RRF
↓
Optional Rerank
↓
Metadata Filter / Result
↓
Citation
```

回答必须可追溯：

- `source_title`
- `section`
- `chunk_id`

## 4.8 Output Contract

```text
KnowledgeAgentResult
├── answer
├── citations[]
└── evidence_status
```

具体 Schema 在 Stage 4 冻结。

## 4.9 Forbidden Behavior

禁止：

- 伪造古籍原文；
- 伪造来源 / 章节；
- 把模型预训练知识冒充 Retrieval 证据；
- 为知识问题调用用户专属排盘 Tool；
- 证据不足时装作确定；
- 运行时自由联网搜索不可控资料。

## 4.10 Failure Behavior

```text
证据足够 → Grounded Answer
证据部分足够 → 限定回答范围
无可靠证据 → 明确知识库不足
```

## 4.11 Ownership Boundary

属于 Knowledge：

> “正官和七杀有什么区别？”

属于 Bazi：

> “结合我的八字看看正官对我意味着什么？”

---

# 5. Cross-Agent Ownership Rules

| 用户真正需要什么 | Owner |
|---|---|
| “我的八字”如何 | Bazi |
| “我的梦”如何理解 | Dream |
| “我的现实问题，需要起卦反思” | Liuyao |
| “某个传统文化知识本身是什么” | Knowledge |

典型边界：

- “什么是日主？” → Knowledge
- “我的日主是什么？” → Bazi
- “七杀是什么意思？” → Knowledge
- “我的八字里七杀很重是什么意思？” → Bazi
- “梦见蛇在传统文化里有什么象征？” → Knowledge（一般知识）
- “我昨晚梦见蛇一直追我。” → Dream
- “世爻是什么意思？” → Knowledge
- “帮我起一卦看看项目。” → Liuyao
- “《周易》怎么看人生选择？” → Knowledge；不能因为出现“周易 + 选择”就自动起卦。

---

# 6. Unified Forbidden Rules

四个 Agent 共同遵守：

1. 不伪造确定性 Tool 数据；
2. 不伪造 Citation；
3. 缺关键用户数据时不猜测；
4. Retrieval 证据不足时明确不足；
5. 不把传统文化解释表述为确定现实事实；
6. 不替代医疗 / 法律 / 投资 / 心理专业判断；
7. 不因为系统拥有某 Tool 就无条件调用；
8. 不访问本 Agent 不需要的用户领域 Context；
9. 不为了完成回答擅自进入另一个业务 Agent；
10. 不突破 v2.0 四 Agent 范围。
