import asyncio
import time
import uuid
import weakref
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone

from guanchen_v2.agents.bazi.runtime import BaziAgentRuntime
from guanchen_v2.agents.knowledge.agent import KnowledgeAgent
from guanchen_v2.application.orchestrator import ConversationOrchestrator
from guanchen_v2.core.session.models import ConversationState
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
from guanchen_v2.observability.context import TraceContext
from guanchen_v2.observability.events import ObservabilityEvent
from guanchen_v2.observability.integration import get_tracer, reset_tracer, set_tracer
from guanchen_v2.observability.logger import log_event
from guanchen_v2.observability.metrics import MetricsCollector
from guanchen_v2.observability.tracer import Tracer
from guanchen_v2.router.adapters.bazi import BaziAgentAdapter
from guanchen_v2.router.adapters.dream import DreamAgentAdapter
from guanchen_v2.router.adapters.knowledge import KnowledgeAgentAdapter
from guanchen_v2.router.adapters.liuyao import LiuyaoAgentAdapter
from guanchen_v2.router.contracts import IntentType
from guanchen_v2.router.core import HighPrecisionRuleRouter, TwoLayerIntentRouter
from guanchen_v2.router.dispatch import SingleAgentDispatcher
from guanchen_v2.router.dual_dispatch import DualDomainDispatcher
from guanchen_v2.router.synthesis import SynthesizedResponse
from guanchen_v2.router.synthesizer import AgentSynthesizer


async def build_retrieval_service(session_factory):
    sparse = SparseRetriever(session_factory=session_factory)

    if await sparse.rebuild_index() == 0:
        raise RuntimeError("知识库为空，请先运行 ingestion")

    return RetrievalService(
        DenseRetriever(
            BgeEmbeddingAdapter(),
            session_factory=session_factory,
        ),
        sparse,
        ReciprocalRankFusion(),
        KnowledgeReranker(BgeRerankerAdapter()),
        RetrievalResultAssembler(),
        reranker_enabled=False,
    )


class GuanChenApplication:
    def __init__(
        self,
        settings,
        session_factory,
        checkpointer,
        retrieval,
        llm=None,
    ):
        self.settings = settings
        self.session_factory = session_factory
        self.checkpointer = checkpointer
        self.retrieval = retrieval
        self.llm = llm or LLMClient.from_settings(settings)
        self._locks = weakref.WeakValueDictionary()
        self.metrics = MetricsCollector()
        self.trace_sink = None

    async def load_session_state(self, session_id: str) -> ConversationState | None:
        """API 层无侵入地读取状态"""
        return await PostgresMemoryStore(self.session_factory).load(session_id)

    def for_session(self, session_id):
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

    async def execute(self, session_id: str | None, user_query: str, **kwargs) -> SynthesizedResponse:
        session_id = session_id or str(uuid.uuid4())
        tracer = get_tracer()

        if tracer is not None:
            with tracer.span(component="application", event_type="REQUEST"):
                return await self._execute_locked(session_id, user_query, **kwargs)

        tracer = Tracer(context=TraceContext.create(prefix="app"), metrics=getattr(self, "metrics", None))
        token = set_tracer(tracer)
        started = time.perf_counter()

        try:
            with tracer.span(component="application", event_type="REQUEST"):
                result = await self._execute_locked(session_id, user_query, **kwargs)
                tracer.run.status = result.status
                return result
        except BaseException:
            tracer.run.status = "FAILED"
            raise
        finally:
            tracer.run.latency_ms = (time.perf_counter() - started) * 1000
            reset_tracer(token)
            log_event(
                ObservabilityEvent(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    trace_id=tracer.run.trace_id,
                    component="application",
                    event_type="RUN",
                    status=tracer.run.status,
                    duration_ms=tracer.run.latency_ms,
                    metadata=asdict(tracer.run),
                )
            )
            if self.trace_sink is not None:
                self.trace_sink(tracer.run)

    async def _execute_locked(self, session_id: str, user_query: str, **kwargs) -> SynthesizedResponse:
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            return await self.for_session(session_id).execute(
                session_id=session_id,
                user_query=user_query,
                **kwargs,
            )


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

        yield GuanChenApplication(
            settings,
            database.session_factory,
            saver,
            retrieval,
        )
    finally:
        if pool is not None:
            await pool.close()
        await database.dispose()
