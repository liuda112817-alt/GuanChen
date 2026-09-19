import json
import logging
import sys
from dataclasses import asdict
from guanchen_v2.observability.events import ObservabilityEvent

logger = logging.getLogger("guanchen.observability")
logger.setLevel(logging.INFO)
logger.propagate = False  # 防止向 root logger 传播导致重复或 stdout 污染

if not logger.handlers:
    # 强制使用 stderr，避免污染 MCP JSON-RPC 的 stdout 通道
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)

def log_event(event: ObservabilityEvent) -> str:
    event_dict = asdict(event)
    json_str = json.dumps(event_dict, ensure_ascii=False)
    logger.info(json_str)
    return json_str
