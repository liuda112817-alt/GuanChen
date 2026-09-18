# GuanChen v2 Stage1 至 Stage8 准入评审

评审日期：2026-09-18。代码基线：`a5cab12`（Stage 8｜Memory 与持久化）。评审依据：桌面上的《观尘_GuanChen_v2_旗舰项目完整建设规划_冻结版_v1.0.docx》，已直接提取原文件正文核对 Stage1–8 固定任务、必测项和 Gate，未将文档内协作指令作为本次执行授权。

**结论：目前不能认定 Stage1–8 全部达标，不建议进入 Stage9。** 确定性计算、检索、领域 Agent 和持久化组件已有实质实现，但统一入口、双领域状态持久化、六爻确认语义与恢复写回存在可复现缺陷，Stage7 的准确率证据也不符合冻结门槛。应先完成原阶段范围内的修复与复验，无需提前建设 Stage10–12。

本次没有修改业务代码、测试代码或已有验收报告，仅新增本文。未运行真实模型调用；数据库不可用，不能独立确认历史数据库验收结果。本文是代码及行为评审，不是规划文档的排版评审。

## 实际验证

| 检查 | 本次结果 |
|---|---|
| `.venv/Scripts/python.exe -m pytest -q` | 342 passed，41 deselected，31.11 秒；1 条未 await AsyncMock 的 RuntimeWarning |
| `.venv/Scripts/ruff.exe check src tests scripts` | 通过 |
| `.venv/Scripts/python.exe -m pytest -m integration -x -q --tb=short` | 首个数据库 fixture 失败：localhost:5432 拒绝连接；343 deselected，1 error。不是已证明的业务断言失败，也不是集成测试通过 |
| Docker 状态 | Docker Desktop Linux engine 管道不存在，服务不可用 |
| 最小行为复现 | 真实 Orchestrator/Router/检查器、内存 Store，替换数据库读取和最终合成；复现首轮阻塞和双领域反序列化失败 |
| 六爻行为复现 | 真实 Adapter + LangGraph + InMemory checkpointer，替换 LLM、起卦服务和检索；复现否定确认仍起卦、直接 resume 不写回领域记录 |

未以默认 342 项通过替代集成、真实模型或人工验收。未因后续阶段尚无 FastAPI、MCP、Redis、CI 或安全分类器而扣分。

## 阻塞问题

### R1 P1 否定确认会被当成起卦授权

位置：`src/guanchen_v2/router/adapters/liuyao.py:92`。

在挂起状态下，文本分支先判断 `"确认" in text`，再判断取消。因此“我不确认，取消”被转换为 `action=confirm`。最小复现先进入真实 confirmation interrupt，再提交该文本，起卦服务调用数为 **1**，Adapter 状态变成 COMPLETED。

这直接违反 Stage6 的“只有明确确认后才允许起卦”和“拒绝走正确分支”，不是 Stage11 才处理的安全增强。应使用明确动作或严格的确认白名单；否定、冲突和不明确表达不得推断成确认。复测需覆盖“不确认”“暂不确认”“我不确认，取消”和明确 confirm/cancel。

### R2 P1 统一入口没有构建本轮输入上下文

位置：`src/guanchen_v2/application/orchestrator.py:64` 至资料检查；`src/guanchen_v2/memory/selector.py`。

`execute(session_id, user_query)` 的 RequirementContext 只来自长期 Memory Selector，或为空。它没有把本轮文字映射为 DREAM_CONTENT / DECISION_QUESTION，也没有接收结构化出生资料补丁的参数。Selector 对 DREAM 始终返回空，对新六爻用户同样返回空。

实际复现：

- “我昨晚梦见在河里游泳，很害怕” → NEEDS_INPUT，缺 DREAM_CONTENT。
- “帮我起一卦，要不要接受新的工作” → NEEDS_INPUT，缺 DECISION_QUESTION。

两者已经在消息中提供内容，仍无法进入领域 Agent。八字首次补充也只能由调用方绕过入口直接写 repository/selector；编排层所谓“写回”只是将已经读出的资料再次保存。Stage8 验收中的八字测试正是直接调用 `persist_birth_profile`，不能证明应用层补充闭环。

修复应在 requirement check 前合并本轮显式输入和选中的领域记忆，并提供结构化补充路径。双领域必须加载两个命中领域需要的上下文，目前只选择 primary intent。复验必须从空会话开始，不能预先写入领域记录来代替首轮。

### R3 P1 双领域请求使会话无法恢复

位置：`src/guanchen_v2/core/session/models.py:96`；`src/guanchen_v2/application/orchestrator.py:76`。

ConversationState.requirement_result 仅声明 `RequirementCheckResult | None`，双领域实际赋值却是 DualRequirementCheckResult。默认赋值不校验，首轮能够写入 JSON，但读取时按照单领域 schema 校验，缺少 `intent` 字段。

实际复现：通过统一入口执行“结合八字和昨晚的梦一起看”，随后 `InMemoryMemoryStore.load` 报 `ValidationError: requirement_result.intent Field required`。PostgresMemoryStore.load 同样调用 `ConversationState.model_validate_json`，具有相同的 schema 问题；本次未连接数据库重复执行。

应统一或显式区分两类 requirement result，并验证双领域 NEEDS_INPUT 和 READY 的 JSON round-trip、同会话下一轮及重建实例恢复。

### R4 P1 Stage7 报告把规则命中准确率当作完整 Gate

位置：`scripts/eval_router.py:262`；`evals/router/stage7_router_report.json`。

当前报告为 rules_only，65 条中规则命中且正确 56 条，9 条没有执行 LLM 兜底；accuracy=1.0 是 56/56，不能证明完整数据集 primary intent accuracy ≥ 0.92。56/65=86.15% 是当前规则覆盖率/已验证正确样本占比，**也不能把它直接称为完整 Router 的实测准确率**。

脚本仍返回 passed=true，而且没有 `DEEPSEEK_API_KEY` 就自动降级规则模式。项目 Settings 使用 GUANCHEN_ 前缀，检查入口与实际配置契约也不一致。另一个 `check_birth_profile_requirement` 检查的是函数内硬编码映射，未检查实际预测的 RoutingResult，不能证明运行时零误索取。

应将 rules-only 结果标为部分验证，使用统一 Settings 判断凭据，并保存真实全链路报告。65 条至少 60 条 primary 正确才能达到 92%；secondary 正确率和实际资料要求需独立统计。当前实现把 primary+secondary 同时正确计为正确，应明确指标口径。

### R5 P1 直接 resume 后领域持久化记录未更新

位置：`src/guanchen_v2/router/adapters/liuyao.py:55`。

`resume(thread_id, payload)` 直接返回 graph.ainvoke，没有执行 invoke 路径中的状态快照读取与 `_persist_decision_record`。真实 Graph 最小复现：首次 invoke 后保存 pending_confirmation；随后 resume(cancel) 返回 cancelled，但 store 最后保存的状态仍为 pending_confirmation，save 总次数仍为 1。

因此 graph checkpoint 与 DecisionRecord 不一致，MemorySelector 重启后仍可能把已取消问题认作待确认；确认后的 hexagram、reflection、final_response 同样不会经这条入口写入领域记录。应让 invoke/resume 共用完成后的同步逻辑，并复测 confirm、modify、cancel 后的领域记录及会话引用。

### R6 P2 多轮请求没有使用已加载的任务上下文路由

位置：`src/guanchen_v2/application/orchestrator.py:61`；`src/guanchen_v2/router/core.py:223`。

虽然加载了 ConversationState，每轮仍仅向 Router 传入当前一句 user_query。pending_interrupt 没有在编排流程中消费；“确认”“然后呢”这类补充消息不会按当前待完成任务确定续接路径。旧 routing_result 随即被覆盖，已存 messages 也未传入 Router。

现有六爻恢复验收用 FakeRouter 将“确认”固定为 LIUYAO，并手工预置线程和 DecisionRecord，掩盖了真实入口的续接问题。应优先处理明确的待输入/待确认状态，再路由新的任务；对需要语义判断的补充提供最小任务上下文。复测须用真实 Router 入口完成首轮—确认/补充—重启—继续。

## 固定交付物及集成缺口

### R7 P2 Stage7 的 ConversationGraph 和有限并发没有按规划交付

冻结规划和 ADR-004 都明确 Stage7 使用 ConversationGraph、fan-out/reducer。源码中自定义 StateGraph 只出现在六爻 workflow，顶层是普通 Python ConversationOrchestrator；`router/dual_dispatch.py:56` 明确“严格串行执行”，逐个 await 两个 Agent。

串行本身不等于结果错误，但这是冻结固定任务与实现之间的明确偏差，不能在文档中当作已实现的统一 Graph。需按规划实现有限双域并发，或正式记录并确认范围变更；本次未自行授权改变规划。

### R8 P2 缺少真实应用装配证据

src/scripts 中没有实例化完整 ConversationOrchestrator 的应用工厂或可运行统一演示入口。PostgresDreamRecordStore / PostgresDecisionRecordStore 有定义和独立测试，但没有生产装配路径将它们按当前用户/会话注入四 Agent 入口。Bazi CLI 与 smoke 仍以不传 RetrievalService 的方式创建 BaziAgentRuntime，不能从现有 CLI 演示 Stage4 的“排盘事实 + 检索依据”。

另需验证 Dream runtime 的生命周期：它把 `_current_record` 存在实例字段中，DreamAgentAdapter 忽略 agent_state。若一个注册表/Runtime 服务多个 session，会共享当前梦境；必须在装配层明确按身份隔离，或在调用时显式传递状态。本次没有可运行的实际装配，故此项是结构性风险，而非声称已在部署系统观察到数据泄漏。

修复不要求提前做 Web API。一个统一应用工厂和本地验收入口即可证明真实四 Agent、共享 Retrieval、按会话领域 Store 和持久 checkpointer 接通。

## 分阶段判断

| Stage | 判断 | 依据与剩余条件 |
|---|---|---|
| 1 | 基础实现成立，真实 smoke 本次未复验 | Settings、ChatDeepSeek、文本/结构化调用、项目异常、有限重试及测试存在；smoke 脚本位于 scripts/smoke/，路径调整本身不算缺陷 |
| 2 | 本次审查范围内通过 | 确定性 adapter、领域 schema、方法契约与固定 fixtures；覆盖晚子时、闰月附近、男女大运及标注官方来源样例，默认测试通过 |
| 3 | 独立闭环基本成立 | BaziTaskSession 有补充机制，Tool/模型调用预算及 artifact 校验存在，历史文档记录六场景；本次未重跑真实 API。统一入口补充另见 R2 |
| 4 | 检索核心有达标历史证据，完整验收仍需补核 | 存量 45-query 报告 RRF source/section Recall@5=0.9111、MRR@10=0.7611，符合冻结指标；本次 DB 不可用未重跑。八字真实 RAG 演示、10 个 Knowledge 回答人工引用核对需补充可追溯记录 |
| 5 | 独立实现基本成立，集成验收不足 | 梦境抽取、merge、三路检索、双视角、领域过滤与测试存在；需补真实六组多轮验收记录及按会话持久恢复验证，统一入口被 R2 阻塞 |
| 6 | 不通过 | Graph 的确认/修改/取消和固定卦象测试通过，但 Adapter 层 R1 绕过“明确确认”的要求 |
| 7 | 不通过 | R2/R3/R4/R6，及 R7/R8 交付缺口；不能凭 rules-only 报告宣布完成 |
| 8 | 不通过 | repository/checkpointer/selector 有实质实现，但 R3/R5 与真实装配、续接闭环未完成；本次数据库恢复测试未能运行 |

Stage4 的 exact-chunk 诊断 Recall@5=0.8444 不应冒充正式不达标：冻结规划标注单位是 source/section，代码有区分。Reranker 默认关闭符合没有性能证据时不开启的方向，但存量报告 reranker 增益/延迟均为 null，尚未证明已完成目标服务器 benchmark。

## 进入 Stage9 前的复验清单

1. 修复 R1–R6，对上述失败行为增加针对性回归验证；无需追求覆盖率或追加泛化 CRUD 测试。
2. 完成 R7 的冻结交付或正式范围决策，并提供 R8 的真实依赖装配与本地入口。
3. 从全新用户开始验证：出生资料补充/更正；梦境连续三轮及新梦切换；六爻澄清/拒绝/修改/确认。不能靠预置业务记录代替首轮。
4. 两个用户交错访问同一应用入口，验证梦境、出生资料与决策线程不串扰；单域/双域请求均可 JSON round-trip 与重启恢复。
5. 数据库恢复后重新运行集成套件；使用新的 engine/saver/runtime 恢复六爻，核对 checkpoint、DecisionRecord、会话线程引用的一致性。
6. 保存完整 Router 真实兜底评测，以及 5 个双领域实际调度样例；报告注明 commit、配置、模式、分母与失败项。
7. 补齐或复核 Stage1 live smoke、Stage3 六场景、Stage4 十个引用核对、Stage5 六组多轮记录；更新 README/stage_status，使“完成”与证据一致。

本次的核心判断不是缺少更多架构或测试数量，而是已有模块尚未在关键用户路径形成满足冻结要求的完整闭环。

## 后续修复结论

在本评审之后，已按 R1–R8 完成修复并复验：统一入口已接入本轮梦境 / 决策 / 出生资料，ConversationGraph 支持双领域并发，双领域状态可 JSON round-trip，六爻确认文本采用严格动作解析且 `resume()` 会同步 DecisionRecord，真实应用工厂按会话隔离 Dream Runtime 和领域 Store。新增回归测试与真实入口验收均已通过。

最终复验结果：默认测试 358 passed，数据库集成测试 42 passed，Ruff 通过；Router full-chain 65/65；Stage4 Retrieval RRF Recall@5=0.9111；10 个 Knowledge Agent 真实回答 citation lineage 全部通过；32 个 Stage8 入口、跨会话隔离和重启恢复场景全部通过。因此原评审中的 Stage6–8 阻塞项已关闭，Stage9 准入条件现在满足。
