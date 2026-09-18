import asyncio
import json

from rich.console import Console
from sqlalchemy import func, select

from guanchen_v2.config.settings import Settings
from guanchen_v2.dream.context import DreamContextService
from guanchen_v2.dream.extractor import DreamExtractor
from guanchen_v2.dream.retrieval import DreamRetrievalService
from guanchen_v2.dream.runtime import (
    DreamAgentRuntime,
    DreamAgentStatus,
)
from guanchen_v2.knowledge.embeddings import BgeEmbeddingAdapter
from guanchen_v2.knowledge.persistence.database import (
    async_session,
    dispose_db,
    get_database_runtime,
    init_db,
)
from guanchen_v2.knowledge.persistence.models import KnowledgeChunkRow
from guanchen_v2.knowledge.rerank_adapter import BgeRerankerAdapter
from guanchen_v2.knowledge.retrieval.assembler import RetrievalResultAssembler
from guanchen_v2.knowledge.retrieval.dense import DenseRetriever
from guanchen_v2.knowledge.retrieval.rerank import KnowledgeReranker
from guanchen_v2.knowledge.retrieval.rrf import ReciprocalRankFusion
from guanchen_v2.knowledge.retrieval.service import RetrievalService
from guanchen_v2.knowledge.retrieval.sparse import SparseRetriever
from guanchen_v2.llm.client import LLMClient

console = Console()


async def verify_dream_corpus() -> int:
    """
    验收前确认当前连接的真实数据库中确实存在《周公解梦》 Dream chunks。

    不依赖固定 chunk 数量，只要求至少存在一条真实入库数据，
    避免误连空数据库 / 测试数据库时仍然继续执行验收。
    """
    async with async_session() as session:
        stmt = (
            select(func.count(KnowledgeChunkRow.chunk_id))
            .where(KnowledgeChunkRow.domain == "dream")
            .where(KnowledgeChunkRow.source_title == "《周公解梦》")
        )

        result = await session.execute(stmt)
        count = int(result.scalar_one())

    if count <= 0:
        raise RuntimeError("当前数据库中未找到《周公解梦》Dream chunks。请确认 GUANCHEN_DATABASE_URL 指向已经完成正式语料入库的 GuanChen 数据库。")

    return count


async def build_real_retrieval_service(
    settings: Settings,
) -> RetrievalService:
    """
    构建 Stage 4 真实共享检索链路：

        PostgreSQL / pgvector
        + BGE Dense Retrieval
        + BM25S Sparse Retrieval
        + RRF Fusion
        + RetrievalResultAssembler

    当前生产策略保持 EVAL-02 的正式决定：
        reranker_enabled=False

    因此实际返回链路为：
        Dense + Sparse -> RRF -> Top-K
    """

    # ---------------------------------------------------------
    # 1. 绑定当前应用 Settings 对应的真实 DatabaseRuntime
    # ---------------------------------------------------------
    get_database_runtime(settings=settings)

    # 幂等保证 pgvector extension / ORM schema 存在。
    # create_all 不会删除已经入库的知识数据。
    await init_db()

    # ---------------------------------------------------------
    # 2. 验证 Dream corpus
    # ---------------------------------------------------------
    dream_chunk_count = await verify_dream_corpus()

    console.print(f"[bold green]✓ 已连接真实知识库，《周公解梦》Dream chunks: {dream_chunk_count}[/bold green]")

    # ---------------------------------------------------------
    # 3. Dense Retrieval
    # ---------------------------------------------------------
    console.print("[bold yellow]正在加载 BGE Embedding 与 Dense Retriever...[/bold yellow]")

    embedding_adapter = BgeEmbeddingAdapter()

    dense_retriever = DenseRetriever(
        embedding_adapter=embedding_adapter,
    )

    # ---------------------------------------------------------
    # 4. Sparse Retrieval
    # ---------------------------------------------------------
    console.print("[bold yellow]正在从 PostgreSQL 构建 BM25S Sparse Index...[/bold yellow]")

    sparse_retriever = SparseRetriever()

    indexed_chunk_count = await sparse_retriever.rebuild_index()

    if indexed_chunk_count <= 0:
        raise RuntimeError("SparseRetriever 未从数据库加载到任何 KnowledgeChunk，拒绝继续 Stage 5 真实检索验收。")

    console.print(f"[bold green]✓ Sparse Index 构建完成，共索引 {indexed_chunk_count} chunks[/bold green]")

    # ---------------------------------------------------------
    # 5. RRF / Reranker / Assembler
    # ---------------------------------------------------------
    rrf = ReciprocalRankFusion()

    # RetrievalService 当前构造契约仍然要求提供 reranker。
    # BgeRerankerAdapter 本身采用 lazy model loading；
    # 由于 reranker_enabled=False，本次不会执行 CrossEncoder rerank。
    reranker_adapter = BgeRerankerAdapter()
    reranker = KnowledgeReranker(
        adapter=reranker_adapter,
    )

    assembler = RetrievalResultAssembler()

    # ---------------------------------------------------------
    # 6. Shared Retrieval Service
    # ---------------------------------------------------------
    retrieval_service = RetrievalService(
        dense_retriever=dense_retriever,
        sparse_retriever=sparse_retriever,
        rrf=rrf,
        reranker=reranker,
        assembler=assembler,
        candidate_limit=20,
        result_limit=5,
        reranker_enabled=False,
    )

    console.print("[bold green]✓ Stage 4 RetrievalService 初始化完成：Dense + Sparse + RRF，Reranker=OFF[/bold green]")

    return retrieval_service


async def print_turn_result(
    turn_num: int,
    user_text: str,
    result,
) -> None:
    console.print(f"\n[bold magenta]================ TURN {turn_num} ================[/bold magenta]")

    console.print(f"[bold]user_text:[/bold] {user_text}\n")

    # ---------------------------------------------------------
    # Agent Result
    # ---------------------------------------------------------
    console.print("[bold cyan]=== AGENT RESULT ===[/bold cyan]")

    console.print(f"status: {result.status.value}")

    # ---------------------------------------------------------
    # State
    # ---------------------------------------------------------
    console.print("\n[bold cyan]=== STATE ===[/bold cyan]")

    record = result.record

    console.print(f"dream_id: {record.dream_id}")

    console.print(f"revision: {record.revision}")

    console.print(f"interpretation_status: {record.interpretation_state.status.value}")

    console.print(f"last_interpreted_revision: {record.interpretation_state.last_interpreted_revision}")

    console.print(
        "elements:\n"
        + json.dumps(
            record.elements.model_dump(
                exclude_defaults=True,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )

    console.print(
        "reality_background:\n"
        + json.dumps(
            record.reality_background.model_dump(
                exclude_defaults=True,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )

    # ---------------------------------------------------------
    # Clarification
    # ---------------------------------------------------------
    if result.status == DreamAgentStatus.NEEDS_CLARIFICATION:
        console.print(f"\n[bold yellow]>>> NEEDS CLARIFICATION: {result.clarification_question}[/bold yellow]")
        return

    # ---------------------------------------------------------
    # Answer contract
    # ---------------------------------------------------------
    if result.response is None:
        raise RuntimeError("DreamAgentStatus.ANSWERED 但 response 为空，违反 DreamAgentResult contract。")

    # ---------------------------------------------------------
    # Answer
    # ---------------------------------------------------------
    console.print("\n[bold green]=== ANSWER ===[/bold green]")

    console.print(f"[bold]traditional_view:[/bold]\n{result.response.traditional_view}\n")

    console.print(f"[bold]psychological_context_view:[/bold]\n{result.response.psychological_context_view}\n")

    # ---------------------------------------------------------
    # Citations
    # ---------------------------------------------------------
    console.print("[bold green]=== CITATIONS ===[/bold green]")

    if not result.citations:
        console.print("[] (No citations)")
        return

    for index, citation in enumerate(
        result.citations,
        start=1,
    ):
        console.print(f"[{index}] {citation.source_title} - {citation.section} (Chunk: {citation.chunk_id})")


async def run_acceptance() -> None:
    # ---------------------------------------------------------
    # 1. Application Settings / LLM
    # ---------------------------------------------------------
    console.print("[bold yellow]正在初始化真实 DeepSeek LLM...[/bold yellow]")

    settings = Settings()

    llm_client = LLMClient.from_settings(
        settings,
    )

    extractor = DreamExtractor(
        llm_client=llm_client,
    )

    # ---------------------------------------------------------
    # 2. Stage 4 Real Retrieval
    # ---------------------------------------------------------
    console.print("[bold yellow]正在连接向量数据库与 Stage 4 真实检索服务...[/bold yellow]")

    retrieval_service_base = await build_real_retrieval_service(
        settings=settings,
    )

    # ---------------------------------------------------------
    # 3. Dream Services
    # ---------------------------------------------------------
    context_service = DreamContextService(
        extractor=extractor,
    )

    dream_retrieval_service = DreamRetrievalService(
        retrieval_service=retrieval_service_base,
    )

    runtime = DreamAgentRuntime(
        context_service=context_service,
        retrieval_service=dream_retrieval_service,
        llm_client=llm_client,
    )

    console.print("[bold green]✓ Dream Agent 已挂载真实 Stage 4 RetrievalService[/bold green]")

    # ---------------------------------------------------------
    # 4. Acceptance Scenarios
    # ---------------------------------------------------------
    scenarios = [
        (
            "Scenario A (首次完整解释)",
            "我梦到自己回到小学，在一条很长的走廊里一直找不到出口，后来看到一扇红色的门。我在梦里特别害怕，醒来以后还觉得很真实。",
        ),
        (
            "Scenario B1 (补充人物)",
            "后来想起来，我以前的班主任也在走廊尽头。",
        ),
        (
            "Scenario B2 (连续补充)",
            "还有一扇一直打不开的门。梦里我妈妈站在门边。",
        ),
        (
            "Scenario C (明确 Correction)",
            "我刚才记错了，不是妈妈，是以前的班主任。",
        ),
        (
            "Scenario D (现实背景补充)",
            "最近工作项目快到截止日期了，我现在确实压力很大。",
        ),
        (
            "CONTINUE Smoke",
            "然后呢？",
        ),
        (
            "Scenario E (模糊新梦边界)",
            "昨晚我又梦见自己在树林里。",
        ),
        (
            "Scenario F (明确切换新梦)",
            "换一个梦。我梦见自己在海边，看到很大的浪。",
        ),
    ]

    # ---------------------------------------------------------
    # 5. Run multi-turn acceptance
    # ---------------------------------------------------------
    for turn_num, (name, user_text) in enumerate(
        scenarios,
        start=1,
    ):
        console.rule(f"[bold red]{name}[/bold red]")

        result = await runtime.handle_turn(
            user_text,
        )

        await print_turn_result(
            turn_num=turn_num,
            user_text=user_text,
            result=result,
        )

        # 避免连续真实 LLM 请求过快。
        await asyncio.sleep(1)


async def main() -> None:
    try:
        await run_acceptance()
    finally:
        # DatabaseRuntime 使用进程级 lazy engine。
        # CLI / acceptance script 结束时显式释放连接池。
        await dispose_db()


if __name__ == "__main__":
    asyncio.run(main())
