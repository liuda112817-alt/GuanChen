from dataclasses import dataclass


@dataclass
class MCPContext:
    """
    MCP Runtime Context.

    Reserved for:
    - application settings
    - authentication context
    - client metadata
    """

    client_id: str | None = None
