import json
from typing import TYPE_CHECKING

import mcp.types as types

from guanchen_v2.knowledge.models import RetrievalFilter
from guanchen_v2.mcp.tools.knowledge import KnowledgeSearchInput

# 仅在类型检查期间导入，防止运行时链式引发 torch/scipy 等几 GB 的重型 ML 库加载
if TYPE_CHECKING:
    from guanchen_v2.knowledge.retrieval.service import RetrievalService


class KnowledgeCapabilityAdapter:
    def __init__(self, service: "RetrievalService | None" = None) -> None:
        self.service = service

    async def search(self, request: KnowledgeSearchInput) -> types.CallToolResult:
        if not self.service:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text="Knowledge retrieval service is not initialized.")],
                isError=True
            )

        try:
            filters = None
            if request.filters and "book_name" in request.filters:
                filters = RetrievalFilter(source_titles=frozenset([request.filters["book_name"]]))

            results = await self.service.search(query=request.query, limit=request.top_k, filters=filters)

            formatted_results = []
            for r in results:
                formatted_results.append({
                    "content": r.content,
                    "citation": {
                        "source_title": r.source_title,
                        "section": r.section,
                        "chunk_id": r.chunk_id
                    }
                })

            response_data = {"results": formatted_results}

            return types.CallToolResult(
                content=[types.TextContent(type="text", text=json.dumps(response_data, ensure_ascii=False))]
            )

        except Exception as e:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Knowledge search failed: {str(e)}")],
                isError=True,
            )