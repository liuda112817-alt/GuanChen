# MCP 使用说明（Stage 9）

官方 `mcp` Python SDK **2.2.0 / MCPServer**，默认演示传输为 Streamable HTTP。
协议由官方 SDK 处理；内部 Agent 直接调用 service，避免本进程多一层协议、延迟和故障点。MCP 仅供外部 Agent Host 调用。

## 启动

先按项目配置 `.env`、PostgreSQL + pgvector 并导入知识库。在 PowerShell 设置演示 token（不要提交真实 token）：

```powershell
$env:GUANCHEN_MCP_TOKEN = '<your-local-demo-token>'
uv run python -m guanchen_v2.mcp.server --transport streamable-http --port 8001
```

端点 `http://127.0.0.1:8001/mcp`，仅绑定回环地址；HTTP 请求必须带 `Authorization: Bearer <token>`。
没有 token 配置时拒绝启动 HTTP，不自动授予匿名访问。可用 `GUANCHEN_MCP_SCOPES` 设置空格分隔的 `bazi.read knowledge.read liuyao.read`，默认三项。
无权限调用返回工具错误；不在此阶段实现 OAuth、多租户或公网服务。

本地 stdio：`uv run python -m guanchen_v2.mcp.server --transport stdio`。
stdio 信任边界是启动进程的本地操作系统用户，授予三项能力；日志写 stderr。

## 三个工具

参数均由 `request` 包裹，工具名冻结为下表，旧的 dotted names 已移除。

| 工具 | request 契约 | 返回 |
|---|---|---|
| `calculate_bazi` | 原 `BirthProfile` | 完整 `BaziChart` |
| `knowledge_search` | query、top_k（1–5）、原 `RetrievalFilter` | 正文与 Citation（chunk/document/source/section） |
| `cast_hexagram` | method=random/manual；manual 使用原 `ManualCastingInput` | 完整 `HexagramResult`，含方法、爻值、随机记录 |

```json
{"request":{"year":1990,"month":1,"day":1,"hour":12,"minute":30,"gender":"male"}}
```

```json
{"request":{"query":"正官是什么意思","top_k":5,"filters":{"domains":["bazi"]}}}
```

```json
{"request":{"method":"manual","manual":{"lines":[7,8,7,8,7,8]}}}
```

六爻工具为无状态计算能力；外部 Host 必须在用户确认后调用一次。内部 Liuyao Agent 的 HITL 仍由 LangGraph 管理，不绕过确认。未知 method、长度/爻值错误和不匹配的 manual 参数拒绝执行。

## 实测

```powershell
uv run python scripts/smoke/smoke_mcp.py
```

该命令自动启动独立 HTTP 服务，官方 ClientSession 列出工具并真实调用全部三个工具（包括 PostgreSQL 检索），验证未鉴权请求和非法参数被拒绝，结束后停止自己启动的服务。
报告：`reports/mcp_smoke.json`。服务日志仅用于本地诊断，`.log` 文件不提交。

迁移依据：[官方 v2 migration guide](https://py.sdk.modelcontextprotocol.io/migration/)。
