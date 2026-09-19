"""Official MCP v2 transport over existing domain services."""

import argparse
import asyncio
import hmac
import os
import sys
from contextlib import asynccontextmanager

from mcp.server.mcpserver import MCPServer
from starlette.responses import JSONResponse

from guanchen_v2.bazi.adapter import LunarPythonBaziAdapter
from guanchen_v2.bazi.service import BaziService
from guanchen_v2.liuyao.casting import HexagramCastingService, SystemRandomCoinSource
from guanchen_v2.liuyao.iching_adapter import IChingPyAdapter
from guanchen_v2.mcp.adapters.bazi_adapter import BaziCapabilityAdapter
from guanchen_v2.mcp.adapters.knowledge_adapter import KnowledgeCapabilityAdapter
from guanchen_v2.mcp.adapters.liuyao_adapter import LiuyaoCapabilityAdapter
from guanchen_v2.mcp.registry import ToolRegistry, access_context
from guanchen_v2.mcp.tools.bazi import BaziCalculateInput, get_bazi_tool_definition
from guanchen_v2.mcp.tools.knowledge import KnowledgeSearchInput, get_knowledge_tool_definition
from guanchen_v2.mcp.tools.liuyao import LiuyaoCastInput, get_liuyao_tool_definition
from guanchen_v2.observability.context import TraceContext
from guanchen_v2.observability.integration import reset_tracer, set_tracer
from guanchen_v2.observability.metrics import MetricsCollector
from guanchen_v2.observability.tracer import Tracer


class BearerAccess:
    def __init__(self, app, token, scopes):
        self.app, self.token, self.scopes = app, token, tuple(scopes)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        if not hmac.compare_digest(headers.get(b"authorization", b""), ("Bearer " + self.token).encode()):
            return await JSONResponse({"error": "unauthorized"}, status_code=401)(scope, receive, send)
        marker = access_context.set(("bearer_client", self.scopes))
        try:
            return await self.app(scope, receive, send)
        finally:
            access_context.reset(marker)


class GuanChenMCPServer:
    def __init__(self):
        self.metrics = MetricsCollector()
        self._db_runtime = None
        self._bazi_adapter = BaziCapabilityAdapter(BaziService(LunarPythonBaziAdapter()))
        self._liuyao_adapter = LiuyaoCapabilityAdapter(HexagramCastingService(IChingPyAdapter(), SystemRandomCoinSource()))
        self._knowledge_adapter = KnowledgeCapabilityAdapter()
        self._registry = ToolRegistry(metrics=self.metrics)

        @asynccontextmanager
        async def lifespan(server):
            try:
                await self.initialize()
                yield {}
            finally:
                await self.close()

        async def observe_request(ctx, call_next):
            tracer = Tracer(TraceContext.create(prefix="mcp"), metrics=self.metrics)
            marker = set_tracer(tracer)
            try:
                with tracer.span("mcp", "REQUEST", {"method": ctx.method}) as span:
                    result = await call_next(ctx)
                    if getattr(result, "is_error", False) or (isinstance(result, dict) and result.get("isError")):
                        span.status = "FAILED"
                    return result
            finally:
                reset_tracer(marker)

        self.server = MCPServer("guanchen-v2-mcp", version="0.1.0", lifespan=lifespan, middleware=[observe_request])
        specs = [
            (get_bazi_tool_definition(), BaziCalculateInput, self._bazi_adapter.calculate),
            (get_knowledge_tool_definition(), KnowledgeSearchInput, self._knowledge_adapter.search),
            (get_liuyao_tool_definition(), LiuyaoCastInput, self._liuyao_adapter.cast),
        ]
        for definition, schema, adapter in specs:
            self._register(definition, schema, adapter)

    def _register(self, definition, schema, adapter):
        async def handler(args):
            return await adapter(schema.model_validate(args))

        self._registry.register(definition["name"], handler, definition)

        # One named Pydantic request object preserves the authoritative domain schema.
        async def tool(request):
            return await self._registry.call(definition["name"], request.model_dump())

        tool.__annotations__ = {"request": schema}
        self.server.add_tool(tool, name=definition["name"], description=definition["description"], structured_output=False)

    async def initialize(self):
        if self._knowledge_adapter.service is not None:
            return
        from guanchen_v2.application.factory import build_retrieval_service
        from guanchen_v2.config.settings import Settings
        from guanchen_v2.knowledge.persistence.database import create_database_runtime

        self._db_runtime = create_database_runtime(database_url=Settings().database_url)
        await self._db_runtime.init_schema()
        self._knowledge_adapter.service = await build_retrieval_service(self._db_runtime.session_factory)

    async def close(self):
        if self._db_runtime is not None:
            await self._db_runtime.dispose()
            self._db_runtime = None
            self._knowledge_adapter.service = None

    def http_app(self, token, scopes=("bazi.read", "knowledge.read", "liuyao.read")):
        if not token:
            raise ValueError("GUANCHEN_MCP_TOKEN is required for HTTP")
        app = self.server.streamable_http_app(host="127.0.0.1", stateless_http=True)
        app.add_middleware(BearerAccess, token=token, scopes=scopes)
        return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="streamable-http")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    app = GuanChenMCPServer()
    if args.transport == "stdio":
        app.server.run(transport="stdio")
    else:
        import uvicorn

        scopes = os.environ.get("GUANCHEN_MCP_SCOPES", "bazi.read knowledge.read liuyao.read").split()
        uvicorn.run(app.http_app(os.environ.get("GUANCHEN_MCP_TOKEN"), scopes), host="127.0.0.1", port=args.port, loop="asyncio")


if __name__ == "__main__":
    main()
