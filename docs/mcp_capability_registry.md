MCP Capability Registry v1
Overview
本文档定义 GuanChen v2 对外暴露的 Model Context Protocol (MCP)
能力契约（Capability Registry v1）。
MCP 层不包含任何核心业务逻辑，仅作为标准化接口向外部 Agent Host
暴露项目内部已经成熟、可独立调用的 Capability。
MCP 的职责：
提供标准化 Tool 接口
完成 MCP Schema 与内部业务 Schema 转换
提供参数校验入口
提供权限检查入口
转换内部异常为 MCP 可理解错误
MCP 不负责：
业务计算
Agent 编排
Workflow 决策
Memory 管理
---
Call Chain Architecture
所有 MCP Capability 严格遵循以下单向调用链：
``` text
External Agent

↓

MCP Tool

↓

Capability Adapter

↓

Existing Service (Stage 2 / 4 / 6)

↓

Result
```
Capability Adapter Responsibility
Capability Adapter 负责：
MCP schema 与内部业务 schema 转换
参数校验
异常转换
权限检查入口
Capability Adapter 不负责：
业务计算
Agent 推理
Workflow 编排
数据持久化逻辑
---
Capability List
Capability             Domain      Type                 Exposure
---
bazi.calculate         bazi        deterministic_tool   MCP Tool
knowledge.search       knowledge   retrieval            MCP Tool
liuyao.cast_hexagram   liuyao      deterministic_tool   MCP Tool
---
Capability Details
Capability: bazi.calculate
Purpose
根据用户出生资料生成结构化八字计算结果，包括：
四柱干支
日主
五行信息
十神信息
大运等排盘数据
Internal Mapping
Service:
``` text
src/guanchen_v2/bazi/service.py
```
Adapter:
``` text
src/guanchen_v2/bazi/adapter.py
```
Layer:
``` text
Domain Service
```
Input Schema
``` json
{
  "birth_profile": {
    "year": 1990,
    "month": 1,
    "day": 1,
    "hour": 12,
    "minute": 30,
    "gender": "male"
  }
}
```
Output Schema
``` json
{
  "chart": {
    "pillars": {},
    "day_master": ""
  },
  "metadata": {}
}
```
Side Effect
``` yaml
false
```
Permission
``` yaml
- bazi.read
```
Stability
``` yaml
production_ready
```
---
Capability: knowledge.search
Purpose
在传统文化知识库中进行混合检索，返回可追溯的知识上下文。
支持：
八字
六爻
易经
解梦
Internal Mapping
Service:
``` text
src/guanchen_v2/knowledge/retrieval/service.py
```
Layer:
``` text
Knowledge Layer
```
Input Schema
``` json
{
  "query": "五行生克制化",
  "filters": {
    "source_titles": [
      "滴天髓阐微"
    ]
  },
  "top_k": 5
}
```
Output Schema
``` json
{
  "results": [
    {
      "content": "",
      "citation": {
        "source_title": "",
        "section": "",
        "chunk_id": ""
      }
    }
  ]
}
```
Side Effect
``` yaml
false
```
Permission
``` yaml
- knowledge.read
```
Stability
``` yaml
production_ready
```
---
Capability: liuyao.cast_hexagram
Purpose
执行六爻起卦计算，根据随机起卦方式或用户手工输入爻值生成结构化卦象结果。
MCP 仅暴露：
``` text
cast capability
```
不暴露：
clarify workflow
user confirmation
interrupt/resume
LangGraph workflow
Internal Mapping
Service:
``` text
src/guanchen_v2/liuyao/casting.py
```
Adapter:
``` text
src/guanchen_v2/liuyao/iching_adapter.py
```
Layer:
``` text
Domain Service
```
Input Schema
``` json
{
  "question": "近期事业发展",
  "method": "random",
  "manual_records": []
}
```
Output Schema
``` json
{
  "ben_gua": {},
  "bian_gua": {},
  "dong_yao": []
}
```
Side Effect
``` yaml
false
```
Permission
``` yaml
- liuyao.read
```
Stability
``` yaml
production_ready
```
---
Non-Exposed Internal Capabilities
以下能力保持内部使用，不作为 MCP Tools 暴露。
Agent Runtime
Reason:
Agent Runtime 属于应用编排层。
包含：
多步骤任务执行
Tool 调用决策
上下文处理
不作为 MCP 原子能力暴露。
Router
Reason:
Router 是内部请求分发机制。
负责：
Intent 判断
Agent 选择
Workflow 调度
不是外部 Agent 可调用能力。
Memory
Reason:
Memory 是内部上下文基础设施。
包括：
用户资料管理
Conversation State
Workflow checkpoint
外部 Agent 不应绕过业务逻辑直接访问内部 Memory。
---
Registry Version
``` yaml
version: v1
status: approved_for_stage9_task2
```