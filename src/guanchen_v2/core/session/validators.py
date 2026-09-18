from typing import Any


def validate_json_serializable(data: Any, path: str = "root") -> None:
    """
    检查数据是否满足纯 JSON 可序列化契约（无 Runtime Object）。
    """
    if data is None:
        return
    # 更严格的类型校验：bool 是 int 的子类，显式分离
    if isinstance(data, bool):
        return
    if isinstance(data, (str, int, float)):
        return
        
    if isinstance(data, list):
        for i, item in enumerate(data):
            validate_json_serializable(item, f"{path}[{i}]")
        return
        
    if isinstance(data, dict):
        for k, v in data.items():
            if not isinstance(k, str):
                raise ValueError(f"State 字典的 key 必须是字符串: {path}.{k}")
            validate_json_serializable(v, f"{path}.{k}")
        return
        
    raise ValueError(f"禁止包含 Runtime Object，在路径 {path} 发现不可序列化类型: {type(data)}")

def validate_namespace_isolation() -> None:
    """
    ADR Candidate: Application Layer should not inspect domain state keys.
    
    目前 Application 仅通过 Pydantic AgentStateContainer (extra="forbid") 
    强类型管控顶层 Namespace 隔离 ('bazi', 'dream', 'liuyao', 'knowledge')。
    
    内部的字典结构不再由 Application 层通过硬编码 key (如 'bazi_chart') 审查，
    而留给未来具体的 Typed Agent State 处理，防止强耦合。
    """
    pass

