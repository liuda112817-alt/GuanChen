# Stage 3 Bazi Agent 核心验收报告

## 1. 系统配置基线 (Configuration Baseline)
- **Agent 模型**: DeepSeek (`ChatDeepSeek`)
- **Thinking Mode**: `disabled` (显式禁用，统一 Tool Calling 行为)
- **Model Call Budget**: `run_limit = 3` (防无限结构化重试)
- **Tool Call Budget**: `calculate_bazi run_limit = 1` (单一任务禁止重复计算)
- **Runtime Invariant**: 必须恰好发生 1 次业务排盘，排盘事实由 `content_and_artifact` 的 artifact 直接组装入最终结果，模型只生成纯净的 Interpretation。

## 2. 验收场景矩阵 (Acceptance Matrix)

| ID | 场景 | 预期行为 | 验收状态 |
| :--- | :--- | :--- | :--- |
| **A01** | 资料完整 | `ReadyForBazi`，进入 Runtime，`calculate_bazi == 1` | ✅ PASS |
| **A02** | 缺时间 | `NeedUserInput(hour, minute)`，Runtime/Tool/Model = 0 | ✅ PASS |
| **A03** | 缺性别 | `NeedUserInput(gender)`，Runtime/Tool/Model = 0 | ✅ PASS |
| **A04** | 重复补充 | 多轮累积，前 N 轮 Runtime=0，仅最后一次 Runtime=1，原问题不变 | ✅ PASS |
| **A05** | 事业问题 (Live) | 真实 Tool Calling，无违规事实编造，基于确切十神/五行输出解释 | ✅ PASS (人工) |
| **A06** | 感情问题 (Live) | 真实 Tool Calling，无违规事实编造，基于确切事实探讨关系 | ✅ PASS (人工) |

## 3. 人工 Live 场景边界审查标准 (Prompt Gate)
在 A05 和 A06 中，LLM **严禁**进行以下二次确定性派生计算（因 Tool 暂未提供）：
- 自行判断身强、身弱、旺衰程度；
- 自行界定八字格局；
- 自行确定用神、喜神、忌神；
- 五行比例、强弱对比或缺失判断；
- 自行发生合、冲、刑、害关系判定与纳音、神煞提取；
- 自行根据大运干支计算或编造其十神映射；
- 自行断定用户当前“正在走某一步大运”（除非明确提到起始年份）；
- 把传统命理释义（如“偏财主灵活资源”）描述为绝对确定性的现实预言。

*(A05与A06经人工运行 CLI `scripts/bazi_cli.py` 检测，模型仅在 Tool 提供的已知天干、地支、十神范围内提供传统语义解释，未发生事实篡改，防线生效。)*

## 4. 已知局限性 (Known Limitations -> Stage 4 需求)
1. 当前传统命理解读**仅依赖大模型自身参数知识**，没有任何外部文献 Grounding。
2. 无法提供真实、可信的典籍引用（Prompt 已强制禁止伪造引用）。
3. 不保证不同大模型版本对“偏财”、“伤官”等传统术语的解释具备绝对一致性。
4. 当前阶段刻意剥夺了旺衰、格局、用神等命理纵深逻辑，原因是底层排盘 Tool 尚未提供算法，模型二次计算极易产生幻觉。
5. **Stage 4 规划**：将通过 RAG（检索增强生成）为传统术语解释提供《渊海子平》或《三命通会》等可检索的高质量知识依据，并继续保持“排盘依旧交由确定性 Tool”的架构。RAG 补充的是知识与依据，**绝不替代**排盘工具。