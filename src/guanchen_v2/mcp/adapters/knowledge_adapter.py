import json
from dataclasses import asdict

import mcp_types as types

from guanchen_v2.knowledge.models import Citation
from guanchen_v2.mcp.tools.knowledge import KnowledgeSearchInput


class KnowledgeCapabilityAdapter:
    def __init__(self, service=None) -> None:
        self.service = service

    async def search(self, request: KnowledgeSearchInput) -> types.CallToolResult:
        if self.service is None:
            raise RuntimeError("Knowledge retrieval service is not initialized")
        results = (await self.service.retrieve(query=request.query, filters=request.filters))[: request.top_k]
        data = {"results": [{"content": r.text, "citation": asdict(Citation.from_retrieval_result(r))} for r in results]}
        return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(data, ensure_ascii=False))], structured_content=data)
