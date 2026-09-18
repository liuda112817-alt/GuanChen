"""Real application assembly shared by CLI and acceptance scripts."""

import asyncio
import uuid
from contextlib import asynccontextmanager

from guanchen_v2.agents.bazi.runtime import BaziAgentRuntime
from guanchen_v2.agents.knowledge.agent import KnowledgeAgent
from guanchen_v2.application.orchestrator import ConversationOrchestrator
from guanchen_v2.dream.context import DreamContextService
from guanchen_v2.dream.extractor import DreamExtractor
from guanchen_v2.dream.retrieval import DreamRetrievalService
from guanchen_v2.dream.runtime import DreamAgentRuntime
from guanchen_v2.knowledge.embeddings import BgeEmbeddingAdapter
from guanchen_v2.knowledge.persistence.database import create_database_runtime
from guanchen_v2.knowledge.rerank_adapter import BgeRerankerAdapter
from guanchen_v2.knowledge.retrieval.assembler import RetrievalResultAssembler
from guanchen_v2.knowledge.retrieval.dense import DenseRetriever
from guanchen_v2.knowledge.retrieval.rerank import KnowledgeReranker
from guanchen_v2.knowledge.retrieval.rrf import ReciprocalRankFusion
from guanchen_v2.knowledge.retrieval.service import RetrievalService
from guanchen_v2.knowledge.retrieval.sparse import SparseRetriever
from guanchen_v2.liuyao.casting import HexagramCastingService, SystemRandomCoinSource
from guanchen_v2.liuyao.iching_adapter import IChingPyAdapter
from guanchen_v2.liuyao.retrieval import LiuyaoRetrievalBuilder
from guanchen_v2.liuyao.workflow import LiuyaoAgentRuntime
from guanchen_v2.llm.client import LLMClient
from guanchen_v2.memory.checkpointer import PostgresCheckpointerFactory
from guanchen_v2.memory.implementations.postgres import PostgresMemoryStore
from guanchen_v2.memory.models import MemoryBase
from guanchen_v2.memory.selector import MemorySelector
from guanchen_v2.memory.stores import PostgresDecisionRecordStore, PostgresDreamRecordStore
from guanchen_v2.router.adapters.bazi import BaziAgentAdapter
from guanchen_v2.router.adapters.dream import DreamAgentAdapter
from guanchen_v2.router.adapters.knowledge import KnowledgeAgentAdapter
from guanchen_v2.router.adapters.liuyao import LiuyaoAgentAdapter
from guanchen_v2.router.contracts import IntentType
from guanchen_v2.router.core import HighPrecisionRuleRouter, TwoLayerIntentRouter
from guanchen_v2.router.dispatch import SingleAgentDispatcher
from guanchen_v2.router.dual_dispatch import DualDomainDispatcher
from guanchen_v2.router.synthesizer import AgentSynthesizer


async def build_retrieval_service(session_factory):
    sparse = SparseRetriever(session_factory=session_factory)
    if await sparse.rebuild_index() == 0:
        raise RuntimeError("知识库为空，请先运行 ingestion")
    return RetrievalService(
        DenseRetriever(BgeEmbeddingAdapter(), session_factory=session_factory),
        sparse,
        ReciprocalRankFusion(),
        KnowledgeReranker(BgeRerankerAdapter()),
        RetrievalResultAssembler(),
        reranker_enabled=False,
    )


class GuanChenApplication:
    def __init__(self, settings, session_factory, checkpointer, retrieval, llm=None):
        self.settings = settings
        self.session_factory = session_factory
        self.checkpointer = checkpointer
        self.retrieval = retrieval
        self.llm = llm or LLMClient.from_settings(settings)
        self._locks = {}

    def for_session(self, session_id):
        # Mutable Dream runtime is scoped to this request and restored from its own store.
        # No singleton contains the current dream of multiple sessions.
        dream = DreamAgentRuntime(
            DreamContextService(DreamExtractor(self.llm)),
            DreamRetrievalService(self.retrieval),
            self.llm,
            record_store=PostgresDreamRecordStore(session_id, self.session_factory),
        )
        liuyao = LiuyaoAgentRuntime(
            HexagramCastingService(IChingPyAdapter(), SystemRandomCoinSource()),
            self.llm,
            LiuyaoRetrievalBuilder(self.retrieval),
            checkpointer=self.checkpointer,
        )
        registry = {
            IntentType.BAZI: BaziAgentAdapter(BaziAgentRuntime(self.settings, self.retrieval)),
            IntentType.DREAM: DreamAgentAdapter(dream),
            IntentType.LIUYAO: LiuyaoAgentAdapter(liuyao, PostgresDecisionRecordStore(session_id, self.session_factory)),
            IntentType.KNOWLEDGE: KnowledgeAgentAdapter(KnowledgeAgent(self.retrieval, self.llm)),
        }
        return ConversationOrchestrator(
            PostgresMemoryStore(self.session_factory),
            TwoLayerIntentRouter(HighPrecisionRuleRouter(), self.llm),
            SingleAgentDispatcher(registry),
            DualDomainDispatcher(registry),
            AgentSynthesizer(self.llm),
            MemorySelector(self.session_factory),
        )

    async def execute(self, session_id, user_query, **kwargs):
        session_id = session_id or str(uuid.uuid4())
        # Prevent lost updates within a process when two turns use the same session.
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            return await self.for_session(session_id).execute(session_id, user_query, **kwargs)


@asynccontextmanager
async def open_application(settings):
    database = create_database_runtime(database_url=settings.database_url)
    pool = None
    try:
        await database.init_schema()
        async with database.engine.begin() as conn:
            await conn.run_sync(MemoryBase.metadata.create_all)
        saver, pool = await PostgresCheckpointerFactory.create(settings.database_url)
        retrieval = await build_retrieval_service(database.session_factory)
        yield GuanChenApplication(settings, database.session_factory, saver, retrieval)
    finally:
        if pool is not None:
            await pool.close()
        await database.dispose()
