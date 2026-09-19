# MCP 能力注册表

唯一注册入口是 `mcp/server.py`，注册与 scope 校验在 `mcp/registry.py`。

| MCP 名称 | 权限 | 输入复用 | 业务委托 |
|---|---|---|---|
| calculate_bazi | bazi.read | BirthProfile | BaziService.calculate |
| knowledge_search | knowledge.read | RetrievalFilter + 有界查询参数 | RetrievalService.retrieve |
| cast_hexagram | liuyao.read | ManualCastingInput | HexagramCastingService.cast_manual / cast_random |

官方 MCPServer 从 request 的 Pydantic 类型生成 schema。禁止额外注册同名工具，禁止复制领域算法。
HTTP Bearer scope 来自进程配置，客户端不能在 tool arguments 中扩大权限。stdio 权限继承本地进程信任。
详细参数、边界和验收命令见 [使用说明](mcp_usage.md)。
