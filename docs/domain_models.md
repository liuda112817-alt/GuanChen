# GuanChen v2 Core Domain Models

- Status: **Conceptual Freeze**
- Version: **v1.0**

本文件只定义领域语义、数据所有权和不变量。

当前不定义：

- Pydantic 代码；
- SQLAlchemy Model；
- 数据库主键；
- ORM relationship；
- API DTO；
- LangGraph State；
- Redis Key；
- 序列化格式。

---

# 1. Model Categories

| 类型 | 模型 | 本质 |
|---|---|---|
| User Fact | UserProfile | 用户明确确认的长期资料 |
| User Fact | BirthProfile | 八字确定性计算输入 |
| Deterministic Result | BaziChart | 八字计算事实 |
| Task State | DreamRecord | 梦境多轮任务状态 |
| Workflow State | DecisionQuestion | 六爻问题确认状态 |
| Deterministic Result | HexagramResult | 六爻计算事实 |
| Evidence Reference | KnowledgeCitation | Retrieval 证据引用 |

---

# 2. UserProfile

## Meaning

> 用户经过明确提供或确认、可以跨任务复用的长期基础资料集合。

不是“AI 自动推断出的完整人格画像”。

## Conceptual Content

- `user_id`
- `display_name?`
- 与 `BirthProfile` 的关联
- `preferences?`（仅限明确表达且确有产品价值的偏好）
- `updated_at`

## Invariant

长期 UserProfile 只保存：

> 用户明确提供 / 明确确认的信息。

禁止自动从普通聊天推断长期人格、价值观等隐式事实。

---

# 3. BirthProfile

## Meaning

> 用户明确提供、用于八字确定性计算的出生资料。

## Conceptual Content

- `birth_date`
- `birth_time`
- `gender`
- `birth_place_text?`
- `calculation_method`

## v2.0 Boundary

`birth_place_text`：

- 可以保存；
- 不参与 v2.0 排盘；
- 不做真太阳时；
- 不调用地理编码。

## Invariant

```text
BirthProfile
+ same calculation_method
+ same dependency version
→ stable BaziChart
```

---

# 4. BaziChart

## Meaning

> 根据 BirthProfile 和冻结排盘口径，由确定性系统产生的标准化八字事实。

## Conceptual Structure

```text
BaziChart
├── pillars
│   ├── year
│   ├── month
│   ├── day
│   └── hour
├── day_master
├── five_elements
├── hidden_stems
├── ten_gods
│   ├── heavenly_stems
│   └── earthly_branches
├── luck_cycles
└── calculation_method
```

Stage 2 再冻结具体嵌套结构与字段类型。

## Boundary

不属于 BaziChart：

- “事业运较好”
- “适合管理工作”
- “今年感情可能变化”

这些属于 Bazi Agent interpretation。

## Third-Party Isolation

```text
lunar_python
→ Adapter
→ BaziChart
→ GuanChen Business Layer
```

业务层不直接依赖 `lunar_python` 对象。

---

# 5. DreamRecord

## Meaning

> 对“当前这个梦”的结构化、可持续更新的任务记录。

## DreamElements

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

## Conceptual Structure

```text
DreamRecord
├── original_description
├── elements: DreamElements
├── reality_context
├── interpretation_state
└── status
```

`status` 表示当前梦境任务的生命周期语义；最终 enum / 字段形式推迟到 Stage 5。

## Core Invariant

用户明确更正：

> Correction > Previous Fact

后写的明确更正覆盖当前有效事实。

## Boundary

```text
Complete Chat History
≠
DreamRecord
```

DreamRecord 只维护当前任务真正重要的信息。

---

# 6. DecisionQuestion

## Meaning

> 用户希望通过六爻进行反思的现实问题，以及用户是否已经确认这个问题。

## Conceptual Structure

```text
DecisionQuestion
├── original_question
├── clarified_question
├── constraints
└── confirmed
```

## Why Keep Both Questions

`original_question` 保留原始语境。

`clarified_question` 是用户确认并用于起卦的明确任务。

## Invariant

```text
confirmed == false
→ cast_hexagram forbidden
```

用户修改：

```text
clarified_question = new question
confirmed = false
```

然后必须重新确认。

---

# 7. HexagramResult

## Meaning

> 六爻确定性计算系统输出的标准化卦象事实。

## Conceptual Content

Stage 0 只冻结语义类别，不冻结完整 schema：

- 输入的六爻 / 起卦结果；
- 本卦确定性结构；
- 变卦相关结构（如适用）；
- 动爻信息；
- `ichingpy` 提供且业务真正使用的六爻结构；
- `cast_method` / `calculation_method`。

具体是否保留：

- 纳甲；
- 六亲；
- 世应；
- 六神；
- 宫位；

在 Stage 6 实际评估 `ichingpy` API 后决定。

## Legal Sources

- 系统随机三枚硬币；
- 用户手工输入六爻结果。

必须保留 `cast_method` 以支持透明说明。

## Boundary

```text
HexagramResult
= deterministic structure

LiuyaoAgentResult
= structure + evidence + reflection
```

---

# 8. KnowledgeCitation

## Meaning

> 最终回答中的知识依据与底层知识库证据之间的可追溯引用。

## Core Fields

- `source_title`
- `section`
- `chunk_id`

`source_type` 是否直接暴露给最终 Citation，在 Stage 4 根据 UI / API 需要决定。

## Invariant

Citation 必须来自真实 RetrievalResult / KnowledgeChunk。

禁止：

```text
LLM 生成“古籍原文”
→ 自己挂 Citation
```

---

# 9. Data Ownership

| 数据 | 谁创建 / 更新 | 谁主要读取 |
|---|---|---|
| UserProfile | 用户明确提供 + 业务层更新 | 按领域选择 |
| BirthProfile | 用户提供 / 更正 | Bazi |
| BaziChart | calculate_bazi Tool | Bazi |
| DreamRecord | Dream flow | Dream |
| DecisionQuestion | Liuyao workflow + 用户确认 | Liuyao |
| HexagramResult | cast_hexagram Tool | Liuyao |
| KnowledgeCitation | Retrieval / response pipeline | 所有需要 RAG 的 Agent |

---

# 10. No Universal UserContext

v2.0 不设计一个包含所有领域数据的“大万能上下文”并注入所有 Agent。

原则：

> 需要什么领域对象，就加载什么领域对象。

目标是避免：

- 领域污染；
- 无关 Token 成本；
- Memory 泄漏；
- Agent 强耦合；
- 上下文噪声。
