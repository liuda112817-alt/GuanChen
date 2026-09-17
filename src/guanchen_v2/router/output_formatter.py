import json

from pydantic import BaseModel

from guanchen_v2.router.adapters.liuyao import LiuyaoInvocationResult
from guanchen_v2.router.dual_dispatch import AgentExecutionResult


def format_agent_result(result: AgentExecutionResult) -> str:
    output = result.output

    if isinstance(output, LiuyaoInvocationResult):
        return f"[Liuyao Result]\n{output.output}"

    if isinstance(output, BaseModel):
        return output.model_dump_json(indent=2)

    if isinstance(output, dict):
        return json.dumps(output, ensure_ascii=False, indent=2)

    return str(output)
