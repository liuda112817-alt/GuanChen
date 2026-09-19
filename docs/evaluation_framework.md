# GuanChen Evaluation Framework

## 1. Overview

GuanChen Evaluation Framework
用于建立一个与核心业务能力解耦的统一评估体系。

主要目标：

-   Capability Quality Evaluation：衡量独立 Capability
    的正确性、稳定性和性能。
-   Agent Performance Measurement：衡量 Agent
    多步骤任务中的决策、工具调用和流程完成质量。
-   Regression Detection：防止系统迭代引入已有能力退化。

Evaluation Framework 只负责：

-   Evaluation Case 管理
-   Evaluation Execution
-   Metric Calculation
-   Evaluation Result Aggregation

不包含：

-   Business Logic
-   Domain Calculation
-   Agent Decision Logic

------------------------------------------------------------------------

## 2. Architecture

``` text
Evaluation Case

        ↓

Evaluation Runner

        ↓

Capability Evaluator

        ↓

Capability Execution

        ↓

Metrics Calculation

        ↓

Evaluation Report
```

### Components

## Evaluation Case

定义一次标准评估输入。

包含：

-   case_id
-   capability
-   input
-   expected_output
-   metadata

## Evaluation Runner

负责：

-   加载 Evaluation Case
-   根据 Capability 查找 Evaluator
-   执行 Evaluation Pipeline
-   汇总 Evaluation Result

## Capability Evaluator

负责：

-   调用目标 Capability
-   分析执行结果
-   生成 Evaluation Result

不包含业务计算逻辑。

## Metrics

负责：

-   从 Evaluation Result 提取质量指标
-   生成量化结果

## Report

负责：

-   聚合 Metrics
-   输出评估报告

------------------------------------------------------------------------

## 3. Evaluation Layers

## Layer 1: Capability Evaluation

Target:

``` text
bazi.calculate

liuyao.cast_hexagram
```

Metrics:

-   Correctness
-   Schema Validity
-   Latency

------------------------------------------------------------------------

## Layer 2: Retrieval Evaluation

Target:

``` text
knowledge.search
```

Metrics:

-   Relevance
    -   Recall@K
    -   MRR
-   Citation Accuracy

------------------------------------------------------------------------

## Layer 3: Agent Evaluation

Target:

``` text
BaziAgent

DreamAgent

LiuyaoAgent
```

Metrics:

-   Tool Selection Accuracy
-   Workflow Completion

------------------------------------------------------------------------

## 4. Evaluation Data Model

核心对象：

``` text
EvaluationCase

EvaluationResult
```

EvaluationCase 描述测试输入。

EvaluationResult 描述执行结果：

-   success
-   output
-   error
-   latency

------------------------------------------------------------------------

## 5. Metric System

基础 Metrics：

  Metric            Purpose
  ----------------- ----------------
  Success Rate      执行成功比例
  Correctness       结果正确性
  Schema Validity   输出契约合法性
  Latency           响应性能

扩展：

Retrieval：

-   Recall@K
-   MRR
-   Citation Coverage

Agent：

-   Tool Selection Accuracy
-   Workflow Completion Rate

------------------------------------------------------------------------

## 6. Evaluation Registry

通过 Registry 管理 Capability 对应 Evaluator：

``` text
Capability

        ↓

Evaluator

        ↓

Metrics
```

示例：

``` text
bazi.calculate

        ↓

BaziEvaluator
```

------------------------------------------------------------------------

## 7. Extension Principles

### Separation of Concerns

Evaluation Framework 不负责：

-   Business Rule
-   Domain Logic
-   Agent Workflow

### Capability Driven

新增 Capability 时，只需要新增：

-   Dataset
-   Evaluator
-   Metrics

无需修改 Framework Core。

------------------------------------------------------------------------

## 8. Stage 10 Task 1 Status

``` text
Evaluation Framework Foundation

        ↓

Ready for Capability Evaluation Suite
```
