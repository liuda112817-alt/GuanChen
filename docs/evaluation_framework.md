# GuanChen Evaluation Framework

## 1. Overview
GuanChen Evaluation Framework 用于建立一个与核心业务能力解耦的统一评估体系。
它的主要作用包括：
* Capability Quality Evaluation (衡量独立工具的能力质量)
* Agent Performance Measurement (衡量 Agent 多步推理与调用的表现)
* Regression Detection (防止迭代引入退化)

## 2. Architecture
评估框架遵循以下单向执行流：
```text
Evaluation Case
        ↓
Evaluation Runner
        ↓
Capability Executor (Evaluator)
        ↓
     Metrics
        ↓
     Report
3. Evaluation Layers
评估框架按关注点分为三个层次：

Layer 1: Capability Evaluation
Target: bazi.calculate, liuyao.cast_hexagram 等独立工具。

Metrics:

Correctness (计算准确性)

Schema Validity (输出结构合法性)

Latency (响应延迟)

Layer 2: Retrieval Evaluation
Target: knowledge.search

Metrics:

Relevance (如 Recall@K, MRR)

Citation (溯源准确性)

Layer 3: Agent Evaluation
Target: BaziAgent, DreamAgent, LiuyaoAgent

Metrics:

Tool Selection Accuracy (工具调用准确率)

Workflow Completion (多轮会话状态流转完成度)
