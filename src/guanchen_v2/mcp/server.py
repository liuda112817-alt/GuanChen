import asyncio
import logging
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server

from guanchen_v2.bazi.adapter import LunarPythonBaziAdapter
from guanchen_v2.bazi.service import BaziService
from guanchen_v2.liuyao.casting import HexagramCastingService, SystemRandomCoinSource
from guanchen_v2.liuyao.iching_adapter import IChingPyAdapter
from guanchen_v2.mcp.adapters.bazi_adapter import BaziCapabilityAdapter
from guanchen_v2.mcp.adapters.knowledge_adapter import KnowledgeCapabilityAdapter
from guanchen_v2.mcp.adapters.liuyao_adapter import LiuyaoCapabilityAdapter
from guanchen_v2.mcp.config import MCPContext
from guanchen_v2.mcp.registry import ToolRegistry
from guanchen_v2.mcp.tools.bazi import BaziCalculateInput, get_bazi_tool_definition
from guanchen_v2.mcp.tools.knowledge import KnowledgeSearchInput, get_knowledge_tool_definition
from guanchen_v2.mcp.tools.liuyao import LiuyaoCastInput, get_liuyao_tool_definition

from guanchen_v2.observability.metrics import MetricsCollector

logging.basicConfig(level=logging.ERROR, stream=sys.stderr)
logger = logging.getLogger(__name__)


class GuanChenMCPServer:
    def __init__(self) -> None:
        self.server = Server("guanchen-v2-mcp")
        self.context = MCPContext()
        # 全局启用 MetricsCollector 收集运行指标
        self.metrics = MetricsCollector()

        self._bazi_service = BaziService(adapter=LunarPythonBaziAdapter())
        self._bazi_adapter = BaziCapabilityAdapter(service=self._bazi_service)

        self._liuyao_service = HexagramCastingService(IChingPyAdapter(), SystemRandomCoinSource())
        self._liuyao_adapter = LiuyaoCapabilityAdapter(service=self._liuyao_service)

        self._retrieval_service = None
        self._knowledge_adapter = KnowledgeCapabilityAdapter(service=self._retrieval_service)

        self._registry = ToolRegistry(metrics=self.metrics)
        self._register_tools()
        self._registry.bind_to_server(self.server)

    def _register_tools(self) -> None:
        bazi_def = get_bazi_tool_definition()
        async def bazi_handler(args: dict):
            return await self._bazi_adapter.calculate(BaziCalculateInput(**args))
        self._registry.register(bazi_def["name"], bazi_handler, bazi_def)

        knowledge_def = get_knowledge_tool_definition()
        async def knowledge_handler(args: dict):
            return await self._knowledge_adapter.search(KnowledgeSearchInput(**args))
        self._registry.register(knowledge_def["name"], knowledge_handler, knowledge_def)

        liuyao_def = get_liuyao_tool_definition()
        async def liuyao_handler(args: dict):
            return await self._liuyao_adapter.cast(LiuyaoCastInput(**args))
        self._registry.register(liuyao_def["name"], liuyao_handler, liuyao_def)

    async def initialize(self) -> None:
        from guanchen_v2.application.factory import build_retrieval_service
        from guanchen_v2.config.settings import Settings
        from guanchen_v2.knowledge.persistence.database import create_database_runtime
        
        settings = Settings()
        self._db_runtime = create_database_runtime(settings.database_url)
        await self._db_runtime.init_schema()
        
        self._retrieval_service = await build_retrieval_service(self._db_runtime.session_factory)
        self._knowledge_adapter.service = self._retrieval_service

    async def run(self) -> None:
        await self.initialize()
        logger.info("Starting GuanChen MCP Server Protocol Layer...")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, self.server.create_initialization_options())

async def main() -> None:
    app = GuanChenMCPServer()
    await app.run()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
