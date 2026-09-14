import os

# 必须在 numpy / torch / sentence-transformers 等依赖加载之前设置。
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import argparse
import asyncio
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, TypeAlias

from sqlalchemy import select

from guanchen_v2.knowledge.embeddings import BgeEmbeddingAdapter
from guanchen_v2.knowledge.eval_metrics import (
    calculate_mrr_at_k,
    calculate_percentile,
    calculate_recall_at_k,
    calculate_relative_mrr_gain,
)
from guanchen_v2.knowledge.eval_models import (
    RetrievalEvalCase,
    RetrievalEvalMetrics,
    RetrievalEvalReport,
)
from guanchen_v2.knowledge.models import (
    KnowledgeDomain,
    RetrievalFilter,
    SourceType,
)
from guanchen_v2.knowledge.persistence.database import (
    async_session,
    init_db,
)
from guanchen_v2.knowledge.persistence.models import (
    KnowledgeChunkRow,
)
from guanchen_v2.knowledge.retrieval.dense import (
    DenseRetriever,
)
from guanchen_v2.knowledge.retrieval.rrf import (
    ReciprocalRankFusion,
)
from guanchen_v2.knowledge.retrieval.sparse import (
    SparseRetriever,
)

# ============================================================
# Frozen Stage 4 Eval Contract
# ============================================================

MIN_EVAL_CASES = 30

RECALL_K = 5
MRR_K = 10
CANDIDATE_LIMIT = 20

EVAL_CASES_FILE = Path("evals/retrieval/stage4_retrieval_eval.json")

FAILURE_REPORT_FILE = Path("evals/retrieval/failure_report.jsonl")

FINAL_REPORT_FILE = Path("evals/retrieval/stage4_retrieval_report.json")


# 正式 Stage 4 relevance unit。
SourceSectionKey: TypeAlias = tuple[str, str]


# ============================================================
# CLI
# ============================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GuanChen Stage 4 Retrieval Evaluation")

    parser.add_argument(
        "--skip-reranker",
        action="store_true",
        help=("只运行 Dense / Sparse / RRF baseline；完全不加载 BGE Reranker。"),
    )

    return parser.parse_args()


# ============================================================
# Eval case loader
# ============================================================


def _parse_filter(
    raw_filter: Any,
) -> RetrievalFilter | None:
    if raw_filter is None:
        return None

    if not isinstance(raw_filter, dict):
        raise ValueError("filters 必须是 object 或 null")

    allowed_fields = {
        "domains",
        "source_types",
        "source_titles",
        "sections",
    }

    unknown_fields = set(raw_filter) - allowed_fields

    if unknown_fields:
        raise ValueError(f"filters 出现未知字段：{sorted(unknown_fields)}")

    kwargs: dict[str, Any] = {}

    domains = raw_filter.get("domains")
    if domains is not None:
        kwargs["domains"] = frozenset(KnowledgeDomain(value) for value in domains)

    source_types = raw_filter.get("source_types")
    if source_types is not None:
        kwargs["source_types"] = frozenset(SourceType(value) for value in source_types)

    source_titles = raw_filter.get("source_titles")
    if source_titles is not None:
        kwargs["source_titles"] = frozenset(source_titles)

    sections = raw_filter.get("sections")
    if sections is not None:
        kwargs["sections"] = frozenset(sections)

    if not kwargs:
        return None

    return RetrievalFilter(**kwargs)


def load_eval_cases(
    file_path: Path,
) -> list[RetrievalEvalCase]:
    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        raw_data = json.load(file)

    if not isinstance(raw_data, list):
        raise ValueError("Eval 文件顶层必须是 JSON array")

    cases: list[RetrievalEvalCase] = []
    seen_case_ids: set[str] = set()

    for raw_item in raw_data:
        if not isinstance(raw_item, dict):
            raise ValueError("每条 Eval case 必须是 JSON object")

        payload = dict(raw_item)

        payload["filters"] = _parse_filter(payload.get("filters"))

        case = RetrievalEvalCase.model_validate(payload)

        if case.case_id in seen_case_ids:
            raise ValueError(f"发现重复 case_id：{case.case_id}")

        seen_case_ids.add(case.case_id)
        cases.append(case)

    return cases


# ============================================================
# Metadata helpers
# ============================================================


def _enum_or_raw_value(
    value: Any,
) -> Any:
    """
    ORM 字段有时是 str，有时可能是 StrEnum。
    Eval 只需要稳定比较其真实值。
    """
    if hasattr(value, "value"):
        return value.value

    return value


def _source_section_key(
    source_title: str,
    section: str,
) -> SourceSectionKey:
    return (
        source_title,
        section,
    )


def _hit_source_section_key(
    hit: Any,
) -> SourceSectionKey:
    return _source_section_key(
        hit.source_title,
        hit.section,
    )


def _row_source_section_key(
    row: KnowledgeChunkRow,
) -> SourceSectionKey:
    return _source_section_key(
        row.source_title,
        row.section,
    )


def _row_matches_filter(
    row: KnowledgeChunkRow,
    filters: RetrievalFilter,
) -> bool:
    """
    Eval Preflight 自己判断 GT 是否满足 filter。

    不依赖 SparseRetriever 私有字段或私有方法。
    """
    if filters.domains:
        allowed_domains = {domain.value for domain in filters.domains}

        if _enum_or_raw_value(row.domain) not in allowed_domains:
            return False

    if filters.source_types:
        allowed_source_types = {source_type.value for source_type in filters.source_types}

        if _enum_or_raw_value(row.source_type) not in allowed_source_types:
            return False

    if filters.source_titles:
        if row.source_title not in filters.source_titles:
            return False

    if filters.sections:
        if row.section not in filters.sections:
            return False

    return True


# ============================================================
# Preflight
# ============================================================


async def check_preflight(
    cases: list[RetrievalEvalCase],
) -> dict[
    str,
    frozenset[SourceSectionKey],
]:
    """
    正式 Benchmark 前检查：

    1. 至少 30 条人工 case；
    2. 所有 anchor GT chunk 必须真实存在；
    3. GT 必须满足该 case 的 metadata filter；
    4. 从 anchor chunk 派生正式 expected source_title + section。

    返回：
        case_id -> expected source/section relevance set
    """
    if len(cases) < MIN_EVAL_CASES:
        raise ValueError(
            "[BLOCKER] Retrieval Eval 至少需要 "
            f"{MIN_EVAL_CASES} 条有效人工考题，"
            f"当前只有 {len(cases)} 条。"
        )

    all_gt_ids = {chunk_id for case in cases for chunk_id in case.relevant_chunk_ids}

    async with async_session() as session:
        statement = select(KnowledgeChunkRow).where(
            KnowledgeChunkRow.chunk_id.in_(sorted(all_gt_ids))
        )

        rows = (await session.execute(statement)).scalars().all()

    row_map = {row.chunk_id: row for row in rows}

    missing_ids = all_gt_ids - set(row_map)

    if missing_ids:
        raise ValueError(
            "Preflight 失败：以下 Ground Truth "
            "anchor chunk 不存在于当前数据库："
            f"{sorted(missing_ids)}"
        )

    expected_source_sections: dict[
        str,
        frozenset[SourceSectionKey],
    ] = {}

    for case in cases:
        case_expected: set[SourceSectionKey] = set()

        for chunk_id in case.relevant_chunk_ids:
            row = row_map[chunk_id]

            if case.filters is not None and not _row_matches_filter(
                row,
                case.filters,
            ):
                raise ValueError(
                    "Preflight 失败："
                    f"case [{case.case_id}] 的 GT "
                    f"[{chunk_id}] 不满足自身 "
                    "RetrievalFilter。"
                )

            case_expected.add(_row_source_section_key(row))

        if not case_expected:
            raise ValueError(f"case [{case.case_id}] 无法派生 expected source/section")

        expected_source_sections[case.case_id] = frozenset(case_expected)

    print(
        "✓ Preflight PASS："
        "30+ cases、GT lineage、metadata filters、"
        "expected source/section 全部有效。"
    )

    return expected_source_sections


# ============================================================
# Metric helpers
# ============================================================


def _mean(
    values: list[float],
) -> float:
    if not values:
        raise ValueError("没有 metric observation，无法计算均值")

    return sum(values) / len(values)


def _first_relevant_rank(
    relevant_items: set[Any] | frozenset[Any],
    ranked_items: list[Any],
) -> int | None:
    for rank, item in enumerate(
        ranked_items,
        start=1,
    ):
        if item in relevant_items:
            return rank

    return None


def _serialize_filter(
    filters: RetrievalFilter | None,
) -> dict[str, Any] | None:
    if filters is None:
        return None

    return {
        "domains": (
            sorted(domain.value for domain in filters.domains) if filters.domains else None
        ),
        "source_types": (
            sorted(source_type.value for source_type in filters.source_types)
            if filters.source_types
            else None
        ),
        "source_titles": (sorted(filters.source_titles) if filters.source_titles else None),
        "sections": (sorted(filters.sections) if filters.sections else None),
    }


def _serialize_source_sections(
    values: (set[SourceSectionKey] | frozenset[SourceSectionKey]),
) -> list[dict[str, str]]:
    return [
        {
            "source_title": source_title,
            "section": section,
        }
        for source_title, section in sorted(values)
    ]


def _hit_view(
    hit: Any,
) -> dict[str, Any]:
    """
    Failure Report 用的人类可读 hit。

    不把算法 score 放进正式业务输出；
    Eval failure report 属于离线诊断，因此这里主要展示 lineage。
    """
    return {
        "chunk_id": hit.chunk_id,
        "source_title": hit.source_title,
        "section": hit.section,
    }


# ============================================================
# Main evaluation
# ============================================================


async def run_evaluation(
    *,
    skip_reranker: bool,
) -> None:
    print("=" * 60)
    print("GuanChen Stage 4 Retrieval Benchmark")
    print("=" * 60)

    if skip_reranker:
        print("运行模式：Baseline only (Dense + Sparse + RRF)")
        print("Reranker Gate：DEFERRED")
    else:
        print("运行模式：Full Retrieval Eval (Dense + Sparse + RRF + Reranker)")

    if not EVAL_CASES_FILE.exists():
        raise FileNotFoundError(f"[BLOCKER] 评测文件不存在：{EVAL_CASES_FILE}")

    cases = load_eval_cases(EVAL_CASES_FILE)

    print(f"考卷已加载，共计 {len(cases)} 道考题。")

    print("正在初始化 PostgreSQL / pgvector...")

    await init_db()

    expected_source_sections = await check_preflight(cases)

    print("正在加载 Dense / Sparse Retrieval...")

    embedding_adapter = BgeEmbeddingAdapter()

    dense_retriever = DenseRetriever(embedding_adapter)

    sparse_retriever = SparseRetriever()
    await sparse_retriever.rebuild_index()

    rrf = ReciprocalRankFusion()

    # ========================================================
    # Optional Reranker
    #
    # skip 模式下连模块都不 import，
    # 避免当前本地 CUDA / CrossEncoder 问题。
    # ========================================================

    rerank_adapter = None
    reranker = None

    if not skip_reranker:
        from guanchen_v2.knowledge.rerank_adapter import (
            BgeRerankerAdapter,
        )
        from guanchen_v2.knowledge.retrieval.rerank import (
            KnowledgeReranker,
        )

        rerank_adapter = BgeRerankerAdapter()

        reranker = KnowledgeReranker(rerank_adapter)

    # ========================================================
    # Warm-up
    # ========================================================

    print("正在进行 Embedding Warm-up...")

    embedding_adapter.embed_query("八字预热")

    if not skip_reranker:
        assert rerank_adapter is not None

        print("正在进行 Reranker Warm-up...")

        rerank_adapter.score_pairs(
            [
                (
                    "预热",
                    "这是一段预热文字",
                )
            ]
        )

    print("\n开始执行 Retrieval Eval...\n")

    # ========================================================
    # Official source/section metrics
    # ========================================================

    dense_recalls: list[float] = []
    dense_mrrs: list[float] = []

    sparse_recalls: list[float] = []
    sparse_mrrs: list[float] = []

    rrf_recalls: list[float] = []
    rrf_mrrs: list[float] = []

    rerank_recalls: list[float] = []
    rerank_mrrs: list[float] = []

    # ========================================================
    # Exact chunk diagnostic metrics
    # ========================================================

    dense_chunk_recalls: list[float] = []
    dense_chunk_mrrs: list[float] = []

    sparse_chunk_recalls: list[float] = []
    sparse_chunk_mrrs: list[float] = []

    rrf_chunk_recalls: list[float] = []
    rrf_chunk_mrrs: list[float] = []

    rerank_chunk_recalls: list[float] = []
    rerank_chunk_mrrs: list[float] = []

    rerank_latencies: list[float] = []

    # ========================================================
    # Failure report
    # ========================================================

    FAILURE_REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if FAILURE_REPORT_FILE.exists():
        FAILURE_REPORT_FILE.unlink()

    for index, case in enumerate(
        cases,
        start=1,
    ):
        print(f"[{index:02d}/{len(cases)}] {case.case_id}: {case.query}")

        # ----------------------------------------------------
        # Ground Truth
        # ----------------------------------------------------

        expected_sections = expected_source_sections[case.case_id]

        exact_chunk_gt = case.relevant_chunk_ids

        # ====================================================
        # 1. Dense
        # ====================================================

        dense_hits = await dense_retriever.search(
            case.query,
            limit=CANDIDATE_LIMIT,
            filters=case.filters,
        )

        dense_chunk_ids = [hit.chunk_id for hit in dense_hits]

        dense_section_keys = [_hit_source_section_key(hit) for hit in dense_hits]

        # Official
        dense_recalls.append(
            calculate_recall_at_k(
                expected_sections,
                dense_section_keys,
                RECALL_K,
            )
        )

        dense_mrrs.append(
            calculate_mrr_at_k(
                expected_sections,
                dense_section_keys,
                MRR_K,
            )
        )

        # Diagnostic
        dense_chunk_recalls.append(
            calculate_recall_at_k(
                exact_chunk_gt,
                dense_chunk_ids,
                RECALL_K,
            )
        )

        dense_chunk_mrrs.append(
            calculate_mrr_at_k(
                exact_chunk_gt,
                dense_chunk_ids,
                MRR_K,
            )
        )

        # ====================================================
        # 2. Sparse
        # ====================================================

        sparse_hits = sparse_retriever.search(
            case.query,
            limit=CANDIDATE_LIMIT,
            filters=case.filters,
        )

        sparse_chunk_ids = [hit.chunk_id for hit in sparse_hits]

        sparse_section_keys = [_hit_source_section_key(hit) for hit in sparse_hits]

        # Official
        sparse_recalls.append(
            calculate_recall_at_k(
                expected_sections,
                sparse_section_keys,
                RECALL_K,
            )
        )

        sparse_mrrs.append(
            calculate_mrr_at_k(
                expected_sections,
                sparse_section_keys,
                MRR_K,
            )
        )

        # Diagnostic
        sparse_chunk_recalls.append(
            calculate_recall_at_k(
                exact_chunk_gt,
                sparse_chunk_ids,
                RECALL_K,
            )
        )

        sparse_chunk_mrrs.append(
            calculate_mrr_at_k(
                exact_chunk_gt,
                sparse_chunk_ids,
                MRR_K,
            )
        )

        # ====================================================
        # 3. RRF
        # ====================================================

        rrf_hits = rrf.fuse(
            dense_hits,
            sparse_hits,
            limit=CANDIDATE_LIMIT,
        )

        rrf_chunk_ids = [hit.chunk_id for hit in rrf_hits]

        rrf_section_keys = [_hit_source_section_key(hit) for hit in rrf_hits]

        # Official source/section relevance
        current_rrf_recall = calculate_recall_at_k(
            expected_sections,
            rrf_section_keys,
            RECALL_K,
        )

        rrf_recalls.append(current_rrf_recall)

        rrf_mrrs.append(
            calculate_mrr_at_k(
                expected_sections,
                rrf_section_keys,
                MRR_K,
            )
        )

        # Exact chunk diagnostic
        current_rrf_chunk_recall = calculate_recall_at_k(
            exact_chunk_gt,
            rrf_chunk_ids,
            RECALL_K,
        )

        rrf_chunk_recalls.append(current_rrf_chunk_recall)

        rrf_chunk_mrrs.append(
            calculate_mrr_at_k(
                exact_chunk_gt,
                rrf_chunk_ids,
                MRR_K,
            )
        )

        # ====================================================
        # 4. Optional Reranker
        # ====================================================

        reranked_hits = None
        reranked_chunk_ids = None
        reranked_section_keys = None

        if not skip_reranker:
            assert reranker is not None

            start = time.perf_counter()

            reranked_hits = reranker.rerank(
                case.query,
                rrf_hits,
                limit=CANDIDATE_LIMIT,
            )

            elapsed_ms = (time.perf_counter() - start) * 1000.0

            if reranked_hits:
                rerank_latencies.append(elapsed_ms)

            reranked_chunk_ids = [hit.chunk_id for hit in reranked_hits]

            reranked_section_keys = [_hit_source_section_key(hit) for hit in reranked_hits]

            # Official
            rerank_recalls.append(
                calculate_recall_at_k(
                    expected_sections,
                    reranked_section_keys,
                    RECALL_K,
                )
            )

            rerank_mrrs.append(
                calculate_mrr_at_k(
                    expected_sections,
                    reranked_section_keys,
                    MRR_K,
                )
            )

            # Diagnostic
            rerank_chunk_recalls.append(
                calculate_recall_at_k(
                    exact_chunk_gt,
                    reranked_chunk_ids,
                    RECALL_K,
                )
            )

            rerank_chunk_mrrs.append(
                calculate_mrr_at_k(
                    exact_chunk_gt,
                    reranked_chunk_ids,
                    MRR_K,
                )
            )

        # ====================================================
        # Failure Analysis
        #
        # 只按正式 source/section Gate 判断 failure。
        # Exact chunk miss 会作为 diagnostic 一并记录。
        # ====================================================

        if current_rrf_recall < 1.0:
            failure_record = {
                "case_id": case.case_id,
                "query": case.query,
                "note": case.note,
                "filters": _serialize_filter(case.filters),
                # --------------------------------------------
                # Official GT
                # --------------------------------------------
                "expected_source_sections": (_serialize_source_sections(expected_sections)),
                "source_section_rrf_recall_at_5": (current_rrf_recall),
                "dense_first_relevant_source_section_rank": (
                    _first_relevant_rank(
                        expected_sections,
                        dense_section_keys,
                    )
                ),
                "sparse_first_relevant_source_section_rank": (
                    _first_relevant_rank(
                        expected_sections,
                        sparse_section_keys,
                    )
                ),
                "rrf_first_relevant_source_section_rank": (
                    _first_relevant_rank(
                        expected_sections,
                        rrf_section_keys,
                    )
                ),
                # --------------------------------------------
                # Exact chunk diagnostics
                # --------------------------------------------
                "anchor_chunk_ids": sorted(exact_chunk_gt),
                "exact_chunk_rrf_recall_at_5": (current_rrf_chunk_recall),
                "dense_first_exact_chunk_rank": (
                    _first_relevant_rank(
                        exact_chunk_gt,
                        dense_chunk_ids,
                    )
                ),
                "sparse_first_exact_chunk_rank": (
                    _first_relevant_rank(
                        exact_chunk_gt,
                        sparse_chunk_ids,
                    )
                ),
                "rrf_first_exact_chunk_rank": (
                    _first_relevant_rank(
                        exact_chunk_gt,
                        rrf_chunk_ids,
                    )
                ),
                # --------------------------------------------
                # Human-readable result lineage
                # --------------------------------------------
                "dense_top_10": [_hit_view(hit) for hit in dense_hits[:10]],
                "sparse_top_10": [_hit_view(hit) for hit in sparse_hits[:10]],
                "rrf_top_10": [_hit_view(hit) for hit in rrf_hits[:10]],
                "reranked_top_10": (
                    [_hit_view(hit) for hit in reranked_hits[:10]]
                    if reranked_hits is not None
                    else None
                ),
            }

            with FAILURE_REPORT_FILE.open(
                "a",
                encoding="utf-8",
            ) as file:
                file.write(
                    json.dumps(
                        failure_record,
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    # ========================================================
    # Aggregate official metrics
    # ========================================================

    dense_metrics = RetrievalEvalMetrics(
        recall_at_5=_mean(dense_recalls),
        mrr_at_10=_mean(dense_mrrs),
        query_count=len(cases),
    )

    sparse_metrics = RetrievalEvalMetrics(
        recall_at_5=_mean(sparse_recalls),
        mrr_at_10=_mean(sparse_mrrs),
        query_count=len(cases),
    )

    rrf_metrics = RetrievalEvalMetrics(
        recall_at_5=_mean(rrf_recalls),
        mrr_at_10=_mean(rrf_mrrs),
        query_count=len(cases),
    )

    # ========================================================
    # Aggregate exact chunk diagnostics
    # ========================================================

    dense_exact_metrics = RetrievalEvalMetrics(
        recall_at_5=_mean(dense_chunk_recalls),
        mrr_at_10=_mean(dense_chunk_mrrs),
        query_count=len(cases),
    )

    sparse_exact_metrics = RetrievalEvalMetrics(
        recall_at_5=_mean(sparse_chunk_recalls),
        mrr_at_10=_mean(sparse_chunk_mrrs),
        query_count=len(cases),
    )

    rrf_exact_metrics = RetrievalEvalMetrics(
        recall_at_5=_mean(rrf_chunk_recalls),
        mrr_at_10=_mean(rrf_chunk_mrrs),
        query_count=len(cases),
    )

    # ========================================================
    # Report construction
    # ========================================================

    if skip_reranker:
        report = RetrievalEvalReport(
            query_count=len(cases),
            dense=dense_metrics,
            sparse=sparse_metrics,
            rrf=rrf_metrics,
            dense_exact_chunk_diagnostic=(dense_exact_metrics),
            sparse_exact_chunk_diagnostic=(sparse_exact_metrics),
            rrf_exact_chunk_diagnostic=(rrf_exact_metrics),
        )

    else:
        if not rerank_latencies:
            raise ValueError("Reranker 已启用，但没有任何有效 latency observation。")

        reranked_metrics = RetrievalEvalMetrics(
            recall_at_5=_mean(rerank_recalls),
            mrr_at_10=_mean(rerank_mrrs),
            query_count=len(cases),
        )

        reranked_exact_metrics = RetrievalEvalMetrics(
            recall_at_5=_mean(rerank_chunk_recalls),
            mrr_at_10=_mean(rerank_chunk_mrrs),
            query_count=len(cases),
        )

        relative_gain = calculate_relative_mrr_gain(
            rrf_metrics.mrr_at_10,
            reranked_metrics.mrr_at_10,
        )

        report = RetrievalEvalReport(
            query_count=len(cases),
            dense=dense_metrics,
            sparse=sparse_metrics,
            rrf=rrf_metrics,
            dense_exact_chunk_diagnostic=(dense_exact_metrics),
            sparse_exact_chunk_diagnostic=(sparse_exact_metrics),
            rrf_exact_chunk_diagnostic=(rrf_exact_metrics),
            reranked=reranked_metrics,
            reranked_exact_chunk_diagnostic=(reranked_exact_metrics),
            reranker_relative_mrr_gain=(relative_gain),
            reranker_added_p50_ms=(
                calculate_percentile(
                    rerank_latencies,
                    50,
                )
            ),
            reranker_added_p95_ms=(
                calculate_percentile(
                    rerank_latencies,
                    95,
                )
            ),
        )

    # ========================================================
    # Save report
    # ========================================================

    report_payload = asdict(report)

    FINAL_REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with FINAL_REPORT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report_payload,
            file,
            indent=2,
            ensure_ascii=False,
        )

    # ========================================================
    # Console report
    # ========================================================

    print("\n" + "=" * 60)
    print("Retrieval Eval Report")
    print("=" * 60)

    print(
        json.dumps(
            report_payload,
            indent=2,
            ensure_ascii=False,
        )
    )

    imperfect_count = sum(1 for recall in rrf_recalls if recall < 1.0)

    print(
        "\nOfficial source/section failures: "
        f"{imperfect_count}/{len(cases)} "
        "cases have RRF Recall@5 < 1.0"
    )

    print(f"Failure report: {FAILURE_REPORT_FILE}")

    print(f"Final report: {FINAL_REPORT_FILE}")

    # ========================================================
    # Gate 1:
    # Official Stage 4 Core Retrieval Quality
    # ========================================================

    print("\n" + "=" * 60)
    print("Verdict 1: Stage 4 Core Retrieval Quality Gate")
    print("=" * 60)

    recall_pass = report.rrf.recall_at_5 >= 0.85

    print("Official relevance unit: source_title + section")

    print(f"Dense  Recall@5={report.dense.recall_at_5:.4f}  MRR@10={report.dense.mrr_at_10:.4f}")

    print(f"Sparse Recall@5={report.sparse.recall_at_5:.4f}  MRR@10={report.sparse.mrr_at_10:.4f}")

    print(f"RRF    Recall@5={report.rrf.recall_at_5:.4f}  MRR@10={report.rrf.mrr_at_10:.4f}")

    if recall_pass:
        print("\n[PASS] Core Retrieval Gate：RRF source/section Recall@5 >= 0.85")
    else:
        print("\n[FAIL] Core Retrieval Gate：RRF source/section Recall@5 < 0.85")

    # ========================================================
    # Diagnostic exact chunk results
    # ========================================================

    print("\n" + "=" * 60)
    print("Diagnostic: Exact Chunk Metrics")
    print("=" * 60)

    print(
        "Dense  exact Recall@5="
        f"{report.dense_exact_chunk_diagnostic.recall_at_5:.4f}  "
        "MRR@10="
        f"{report.dense_exact_chunk_diagnostic.mrr_at_10:.4f}"
    )

    print(
        "Sparse exact Recall@5="
        f"{report.sparse_exact_chunk_diagnostic.recall_at_5:.4f}  "
        "MRR@10="
        f"{report.sparse_exact_chunk_diagnostic.mrr_at_10:.4f}"
    )

    print(
        "RRF    exact Recall@5="
        f"{report.rrf_exact_chunk_diagnostic.recall_at_5:.4f}  "
        "MRR@10="
        f"{report.rrf_exact_chunk_diagnostic.mrr_at_10:.4f}"
    )

    print("\n注意：Exact Chunk Metrics 仅用于诊断，不参与 Stage 4 PASS/FAIL。")

    # ========================================================
    # Gate 2:
    # Optional Production Reranker
    # ========================================================

    print("\n" + "=" * 60)
    print("Verdict 2: Production Reranker Gate")
    print("=" * 60)

    if skip_reranker:
        print("[DEFERRED] 本次使用 --skip-reranker。")

        print("未执行 Reranker MRR Gain / latency Gate。")

        print("Production policy: reranker_enabled=False")

    else:
        assert report.reranker_relative_mrr_gain is not None

        assert report.reranker_added_p95_ms is not None

        assert report.reranker_added_p50_ms is not None

        mrr_pass = report.reranker_relative_mrr_gain >= 0.05

        latency_pass = report.reranker_added_p95_ms <= 800.0

        reranker_enabled = mrr_pass and latency_pass

        print(f"Relative MRR Gain: {report.reranker_relative_mrr_gain * 100:.2f}%")

        print(f"Reranker p50: {report.reranker_added_p50_ms:.2f} ms")

        print(f"Reranker p95: {report.reranker_added_p95_ms:.2f} ms")

        if reranker_enabled:
            print("\n[ENABLED] Reranker 通过效果与延迟双 Gate。")

            print("Production policy: reranker_enabled=True")
        else:
            print("\n[DISABLED] Reranker 未通过效果/延迟双 Gate。")

            print("Production policy: reranker_enabled=False")


if __name__ == "__main__":
    args = parse_args()

    asyncio.run(
        run_evaluation(
            skip_reranker=args.skip_reranker,
        )
    )
