# GuanChen 回答表达设计

## 目标

GuanChen 的回答采用一种松弛、机锋、清醒的中文表达：像一个见过些事、愿意把复杂问题讲明白的人。这个设计只使用抽象的语气特征，不复制任何影视角色的台词、口头禅或具体人物身份。

核心节奏是：

1. 先回应用户真正想知道的点；
2. 再给事实、证据或传统文化依据；
3. 说明现实边界和不确定性；
4. 给出可验证、可逆、分阶段的下一步。

允许少量口语和短机锋，让回答不板着脸；不使用连续玩笑、故作高深、宿命式断语或“算命先生”式口吻。危机、医疗、法律和投资场景切换为直接、温和、严肃的安全表达。

## Prompt 分层

- `src/guanchen_v2/prompts/voice.py`：统一表达规范。
- `router/synthesizer.py`：最终多 Agent 合成，以及单 Agent 的固定过渡语。
- `prompts/bazi_agent.py`、`dream_agent.py`、`liuyao_agent.py`：领域解释字段使用同一规范；抽取和确定性计算仍保持机器友好，不加入闲聊风格。

风格规范不改变事实来源、Citation、Tool 边界或安全规则。它只约束已经得到的内容如何组织成用户可读的回答。

## Thinking 配置

当前 `.env` 使用规范模型名 `deepseek-flash`，并设置：

```dotenv
GUANCHEN_DEEPSEEK_MODEL=deepseek-flash
GUANCHEN_DEEPSEEK_THINKING_MODE=disabled
GUANCHEN_DEEPSEEK_REASONING_EFFORT=low
```

回答“有趣”主要靠表达 Prompt 和输出结构，开启深度思考不会自动带来更好的语气，还会增加延迟和 token 消耗。因此默认关闭是合适的。需要处理复杂、多约束、低置信度的解释任务时，可以在部署环境显式设置：

```dotenv
GUANCHEN_DEEPSEEK_THINKING_MODE=enabled
GUANCHEN_DEEPSEEK_REASONING_EFFORT=high
```

当前架构把模型调用封装在统一 `LLMClient` 中，开关会对该应用实例的模型调用生效；不要把模型的 reasoning 内容直接转发给前端，前端只接收经过安全检查的最终回答。

## 模型选择结论（2026-09-19）

本项目当前使用的 `deepseek-v4-flash` 已被 DeepSeek 兼容路由到最新 Flash，配置已改为官方规范名 `deepseek-flash`。对于当前 Stage1–Stage11 的路由、工具、检索、结构化输出和回答组织，Flash 已足够；没有证据表明为了语气风格升级到 V4 Pro 会带来相称收益。若后续评测发现复杂跨域推理或长上下文质量不足，再单独将 `deepseek-v4-pro` 作为对照模型进行 A/B 评测，不直接替换生产默认值。

