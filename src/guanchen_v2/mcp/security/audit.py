import logging
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class MCPAuditEvent:
    timestamp: str
    client_id: str
    tool_name: str
    status: str
    error_message: str | None = None


def log_audit_event(client_id: str, tool_name: str, status: str, error_message: str | None = None) -> None:
    """记录 MCP 调用的安全与审计事件边界"""
    event = MCPAuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(), client_id=client_id, tool_name=tool_name, status=status, error_message=error_message
    )
    logger.info(f"[MCP Audit] {event}")
