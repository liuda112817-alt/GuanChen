from typing import Any

from pydantic import BaseModel, Field

from guanchen_v2.mcp.security.permissions import Permission


class KnowledgeSearchInput(BaseModel):
    query: str = Field(..., description="The query string to search for classical Chinese text.")
    filters: dict[str, Any] | None = Field(default_factory=dict, description="Optional metadata filters (e.g., {'book_name': '周易'}).")
    top_k: int = Field(5, description="Number of top results to return.")


def get_knowledge_tool_definition() -> dict:
    return {
        "name": "knowledge.search",
        "description": "Search the knowledge base for classical Chinese texts and interpretations.",
        "inputSchema": KnowledgeSearchInput.model_json_schema(),
        "permission": Permission.KNOWLEDGE_READ.value
    }