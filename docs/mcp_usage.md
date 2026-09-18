# GuanChen MCP Server Usage

## 1. Overview

GuanChen MCP Server 是 GuanChen v2 暴露给外部 Agent Host
的标准化能力接口层。

其核心目的在于：

-   向外部 Agent
    生态系统暴露系统内部已成熟的、确定性的传统文化推演与检索能力（Capability）。
-   提供符合标准的 Model Context Protocol（MCP）Tool Interface。

**明确声明：**

MCP 层仅仅是一个契约转换与通信协议层（Protocol Layer）。它不包含任何
Agent Runtime、Business Logic，也不直接操作系统的
Memory/Context。所有复杂的推理与上下文状态流转均由内部服务闭环处理。

------------------------------------------------------------------------

## 2. Architecture

MCP Server 严格遵循以下单向调用链路，利用 Capability Adapter
实现防腐层隔离：

``` text
External Agent Host
        ↓
    MCP Client
        ↓
GuanChen MCP Server
        ↓
 Capability Adapter
        ↓
 Existing Services (Stage 2/4/6)
```

------------------------------------------------------------------------

## 3. Available Tools

### `bazi.calculate`

-   **Description:** Calculate a structured Bazi chart from birth
    information.

-   **Input Schema:**

``` json
{
  "year": 1990,
  "month": 1,
  "day": 1,
  "hour": 12,
  "minute": 30,
  "gender": "male"
}
```

------------------------------------------------------------------------

### `knowledge.search`

-   **Description:** Search the classical knowledge base for Chinese
    texts and interpretations.

-   **Input Schema:**

``` json
{
  "query": "五行生克制化",
  "top_k": 5,
  "filters": {
    "book_name": "滴天髓阐微"
  }
}
```

------------------------------------------------------------------------

### `liuyao.cast_hexagram`

-   **Description:** Cast a Liuyao hexagram based on the given question.

-   **Input Schema:**

``` json
{
  "question": "近期事业发展",
  "method": "random",
  "manual_records": []
}
```

------------------------------------------------------------------------

## 4. Security Boundary

当前 Stage 9 实现了基础的安全检查结构：

-   **Authentication:** Not implemented（延迟至 Stage 11 API Gateway
    层统一处理）。
-   **Authorization:** 基于 Permission Metadata 实现，内置
    `bazi.read`、`knowledge.read`、`liuyao.read` 颗粒度权限定义，在
    Registry 分发前进行拦截。
-   **Audit:** Logger based。所有 MCP 调用的成功、失败及异常均通过
    `MCPAuditEvent` 在边界处生成标准日志。

------------------------------------------------------------------------

## 5. Running MCP Server

MCP Server 默认通过 `stdio` 协议与本地的 Agent Host
交互。可以直接通过子进程方式启动：

``` bash
python -m guanchen_v2.mcp.server
```
