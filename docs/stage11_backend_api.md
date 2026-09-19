# Stage 11 后端与 Bolt 对接契约

本次范围按用户要求调整为 Stage 1–11 后端。UI 由 Bolt 后续制作；不把后端 HTTP 验收当成网页端验收。后端提供四个 Agent、按需补资料、Safety、持久化匿名会话、HITL、引用及 SSE。

## 启动

```powershell
docker start guanchen_eval_db
uv run python scripts/serve_api.py
```

读取项目 `.env`，要求 PostgreSQL + pgvector、已导入知识库及模型配置。Windows 启动器选择 psycopg 支持的 Selector 事件循环。默认 `http://127.0.0.1:8000`，OpenAPI `/openapi.json`，交互文档 `/docs`。Stage 11 本地服务为单进程；多 worker 的共享限流、幂等和公网部署属于 Stage 12。

`GUANCHEN_API_CORS_ORIGINS` 是 JSON 数组，填写准确的 Bolt 预览或前端地址，例如 `["http://localhost:5173","https://your-preview.example"]`。允许 Authorization/Content-Type；不使用跨站 Cookie。`GUANCHEN_API_TIMEOUT_SECONDS` 默认 180 秒。云端 Bolt 执行环境不能直接访问用户电脑的 localhost；本地浏览器开发时使用可达的后端地址，公网入口待 Stage 12 部署。

## 匿名会话

先 `POST /api/v1/sessions`，获得 `session_id` 与 `session_token`。后续所有会话读写都携带 `Authorization: Bearer <session_token>`。凭证只在创建时发给客户端，数据库只保存其 SHA-256 哈希，重启后仍有效；不能拿另一个会话的凭证读取或修改当前会话。

无 session_id 的 chat/stream 也会自动创建会话，并在响应或 start 中返回凭证。推荐先创建会话，以便首轮网络异常后仍可查询状态。凭证按会话保存到前端 sessionStorage；不要将它写入 URL、日志或分享链接。

| 方法 / 路径 | 用途 |
|---|---|
| POST `/api/v1/chat` | 普通 JSON 对话 |
| POST `/api/v1/chat/stream` | 同一 chat 请求的 SSE 形式 |
| POST `/api/v1/resume` | 确认、修改或取消六爻中断 |
| POST `/api/v1/resume/stream` | resume 的 SSE 形式 |
| GET `/api/v1/sessions/{session_id}` | 历史消息、最后响应和当前确认卡片 |
| GET `/api/v1/sessions/{session_id}/profile` | 已存的完整资料及部分已填字段 |
| PATCH `/api/v1/profile` | 用户明确提供或更正的出生资料，支持增量填写 |
| GET `/api/v1/sessions/{session_id}/citations/{chunk_id}` | 当前回答引用的原文和来源；非当前引用返回 404 |

Chat 请求：

```json
{"session_id":"...","message":"我的八字事业如何","new_task":false,"birth_profile":{"year":1992}}
```

`birth_profile` 可省略，不在首次打开时强制要求。只有 `status=needs_input` 且 `required_input.kind=birth_profile` 才显示出生资料表单；按 `fields` 展示缺失项。知识和解梦不依赖出生资料。`new_task=true` 表示明确开始新任务，会退出旧六爻会话流程。

响应状态：answered、needs_input、interrupted、cancelled、blocked。返回 content、used_intents、citations、facts、required_input、interrupt、safety、trace_id。`facts` 为领域代码产生的确定性事实，不用前端自行排盘。`blocked` 要显示安全响应正文。

六爻 `interrupt` 返回 `thread_id`、`confirmation_id`、`prompt`。确认示例：

```json
{"session_id":"...","thread_id":"...","confirmation_id":"...","action":"confirm"}
```

`action=cancel` 取消；`action=modify` 还需非空 `modification`。修改后可能返回 needs_input 或一张新的确认卡片。必须使用最新 confirmation_id；旧卡片、重复确认返回 409。当前处于确认态时，普通 chat 返回 RESUME_REQUIRED，前端应通过卡片按钮走 resume。安全拦截不会自动起卦，原确认卡片仍可通过 session 接口恢复或取消。

## SSE

使用 `fetch` POST + ReadableStream，不能用只能 GET 且难以携带 Authorization 的原生 EventSource。按空行切分帧；不要假设每次网络 read 恰好是一帧。每帧为 `id`、`event`、JSON `data`；以冒号开头的是心跳注释。

| event | data / 行为 |
|---|---|
| start | session_id、初次创建的 session_token |
| route | intents，更新 Agent 状态 |
| tool_start | tool，标记工具开始 |
| tool_end | tool、status，标记完成或失败 |
| retrieval | chunk_ids、status，表示实际检索进度 |
| need_input | kind、fields，显示按需表单或问题澄清 |
| interrupt | thread_id、confirmation_id、prompt，显示确认卡片 |
| token | text，追加展示文本 |
| done | 完整 ChatResponse；最终状态与引用以它为准 |
| error | code、message、trace_id；本次流终止，不再发送 done |

route/tool/retrieval 在实际执行时发送。token 是**完整回答通过输出检查后的文本分块**，不是未经检查的 provider token；前端等待时展示进度，避免提前泄露不适当断言。SSE 约每 15 秒发送心跳；响应设置 no-cache/no-store 和 X-Accel-Buffering: no。断开连接取消尚在执行的任务；已经提交的数据库/checkpoint 不会回滚。重新连接后先 GET session，不能盲目再次 confirm。SSE id 仅在本次流内递增，不支持 Last-Event-ID 重放。

JSON 错误使用 `{code,message,trace_id}`，422 为契约校验失败，401 为凭证无效，409 为中断过期/需要卡片操作，504 为请求超时，500 为脱敏内部错误。SSE 开始前的校验仍使用 HTTP 错误；开始后的执行错误使用 error 事件。

## Bolt 验收清单

1. 知识与解梦直接输入并得到答案，不弹出生资料框。
2. 八字缺资料时按 fields 收集，补全后继续原问题；编辑资料后结果采用新资料。
3. 展示路由、工具开始/结束、检索进度与最终引用；引用可打开原文。
4. 六爻先显示确认卡片；修改后显示新卡片，取消无起卦，重复提交被拒绝。
5. 刷新后持有凭证可恢复会话；安全拦截、网络错误与 error 事件均有可见状态。
6. 不将模型文本作为 HTML 直接注入；使用安全 Markdown 渲染，并保持原文引用的来源区别。

## 后端验证

```powershell
uv run python scripts/run_evals.py --include-stage11 --output-dir reports/stage11_baseline
```

统一命令重跑 Stage 1–10 回归与真实模型基线，再启动独立 HTTP 进程验证 Stage 11 各路径和重启恢复。详细 HTTP 报告在 `reports/stage11_backend`；亦可单独运行 `uv run python scripts/eval_stage11_backend.py`。测试用合成输入；数据库集成测试使用独立测试库，真实应用验收在已导入知识库的配置数据库中新建合成会话。

实现参照：[FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)、[Starlette StreamingResponse](https://starlette.dev/responses/)、[CORS 配置](https://www.starlette.io/middleware/)。
