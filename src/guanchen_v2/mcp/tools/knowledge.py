from pydantic import BaseModel, ConfigDict, Field

from guanchen_v2.knowledge.models import RetrievalFilter


class KnowledgeSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=1, max_length=4000)
    filters: RetrievalFilter | None = None
    top_k: int = Field(default=5, ge=1, le=5)


def get_knowledge_tool_definition() -> dict:
    return {
        "name": "knowledge_search",
        "description": "Search knowledge with traceable citations.",
        "inputSchema": KnowledgeSearchInput.model_json_schema(),
        "permission": "knowledge.read",
    }
