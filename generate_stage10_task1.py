import os
from pathlib import Path

FILES = {
    "src/guanchen_v2/evaluation/__init__.py": "",
    
    "src/guanchen_v2/evaluation/models.py": """from dataclasses import dataclass, field
from typing import Any

@dataclass
class EvaluationCase:
    id: str
    capability: str
    input: dict[str, Any]
    expected: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class EvaluationResult:
    case_id: str
    capability: str
    success: bool
    output: dict[str, Any] | None
    error: str | None
    latency_ms: float
""",

    "src/guanchen_v2/evaluation/metrics.py": """from abc import ABC, abstractmethod
from typing import Any
from guanchen_v2.evaluation.models import EvaluationResult

class Metric(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def calculate(self, result: EvaluationResult) -> Any:
        pass
""",

    "src/guanchen_v2/evaluation/evaluator.py": """from abc import ABC, abstractmethod
from guanchen_v2.evaluation.models import EvaluationCase, EvaluationResult
from guanchen_v2.evaluation.metrics import Metric

class CapabilityEvaluator(ABC):
    def __init__(self, capability: str, metrics: list[Metric] | None = None):
        self.capability = capability
        self.metrics = metrics or []

    @abstractmethod
    async def evaluate_case(self, case: EvaluationCase) -> EvaluationResult:
        pass

    async def evaluate(self, cases: list[EvaluationCase]) -> list[EvaluationResult]:
        results = []
        for case in cases:
            if case.capability == self.capability:
                result = await self.evaluate_case(case)
                results.append(result)
        return results
""",

    "src/guanchen_v2/evaluation/registry.py": """from guanchen_v2.evaluation.evaluator import CapabilityEvaluator

class EvaluationRegistry:
    def __init__(self) -> None:
        self._evaluators: dict[str, CapabilityEvaluator] = {}

    def register(self, capability: str, evaluator: CapabilityEvaluator) -> None:
        self._evaluators[capability] = evaluator

    def get(self, capability: str) -> CapabilityEvaluator | None:
        return self._evaluators.get(capability)
""",

    "src/guanchen_v2/evaluation/runner.py": """import logging
from guanchen_v2.evaluation.models import EvaluationCase, EvaluationResult
from guanchen_v2.evaluation.registry import EvaluationRegistry

logger = logging.getLogger(__name__)

class EvaluationRunner:
    def __init__(self, registry: EvaluationRegistry):
        self.registry = registry

    async def run(self, cases: list[EvaluationCase]) -> list[EvaluationResult]:
        cases_by_cap: dict[str, list[EvaluationCase]] = {}
        for case in cases:
            cases_by_cap.setdefault(case.capability, []).append(case)
        
        all_results = []
        
        for capability, cap_cases in cases_by_cap.items():
            evaluator = self.registry.get(capability)
            if not evaluator:
                logger.warning(f"No evaluator registered for {capability}. Skipping.")
                continue
            
            results = await evaluator.evaluate(cap_cases)
            all_results.extend(results)
            
        return all_results
""",

    "docs/evaluation_framework.md": """# GuanChen Evaluation Framework

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
""",

"tests/evaluation/test_framework.py": """import pytest
from guanchen_v2.evaluation.models import EvaluationCase, EvaluationResult
from guanchen_v2.evaluation.metrics import Metric
from guanchen_v2.evaluation.evaluator import CapabilityEvaluator
from guanchen_v2.evaluation.registry import EvaluationRegistry
from guanchen_v2.evaluation.runner import EvaluationRunner

class DummyMetric(Metric):
@property
def name(self) -> str:
return "dummy_metric"

def calculate(self, result: EvaluationResult) -> int:
    return 1 if result.success else 0
class DummyEvaluator(CapabilityEvaluator):
async def evaluate_case(self, case: EvaluationCase) -> EvaluationResult:
return EvaluationResult(
case_id=case.id,
capability=case.capability,
success=True,
output={"tested": True},
error=None,
latency_ms=15.0
)

@pytest.mark.asyncio
async def test_evaluation_framework_core():
# 1. 验证 Data Model
case = EvaluationCase(id="case_001", capability="dummy.cap", input={"query": "test"})
assert case.id == "case_001"

# 2. 验证 Registry 与 Evaluator
registry = EvaluationRegistry()
evaluator = DummyEvaluator(capability="dummy.cap", metrics=[DummyMetric()])
registry.register("dummy.cap", evaluator)
assert registry.get("dummy.cap") is not None

# 3. 验证 Runner 执行链路
runner = EvaluationRunner(registry)
results = await runner.run([case])

assert len(results) == 1
res = results[0]
assert res.case_id == "case_001"
assert res.success is True
assert res.latency_ms == 15.0

# 4. 验证 Metric 调用
metric = evaluator.metrics[0]
assert metric.calculate(res) == 1
"""
}

for file_path_str, content in FILES.items():
    file_path = Path(file_path_str)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    print(f"✓ Created: {file_path}")

    print("\nTask 1 全部文件生成完毕。请运行 'uv run pytest tests/evaluation/test_framework.py' 验证框架架构。")