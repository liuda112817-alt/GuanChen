# GuanChen Observability Foundation

## 1. Overview
Stage 10 的 Observability 模块为 GuanChen v2 提供了统一的遥测与可观测性底座。
其核心目标是回答：系统运行过程中发生了什么？在哪里发生？耗时多少？为什么失败？

## 2. Architecture
可观测性底座不干扰核心业务流，使用透明的上下文管理进行旁路记录：
```text
TraceContext
    ↓ (Propagation)
  Tracer 
    ↓ (Event Generation inside Span)
ObservabilityEvent
    ↓
 Structured Logger & Metrics Collector
 3. Event Model
所有系统行为（包括 Agent Runtime、MCP Boundary、Tools、Services）都会统一收敛为 ObservabilityEvent。
关键字段：

trace_id: 贯穿同一次请求上下文的唯一追踪 ID。

component: 来源组件（如 agent, router, bazi_service）。

event_type: 标准化动作分类（如 TOOL_CALL, SERVICE_CALL, REQUEST_START）。

status: 结果状态（SUCCESS, FAILED, RUNNING）。

duration_ms: 执行耗时。

4. Extension
当前第一版设计通过 json.dumps 打印至 stdout 实现基础结构化日志。
在 Stage 11 (部署阶段) 中，此基础模型无需修改，仅需将 logger 挂接到 Elasticsearch/FluentBit 或 Datadog 即可。
