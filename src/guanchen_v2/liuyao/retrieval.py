from guanchen_v2.knowledge.models import KnowledgeDomain, RetrievalFilter, RetrievalResult
from guanchen_v2.knowledge.retrieval.service import RetrievalService
from guanchen_v2.models.liuyao import HexagramResult

LIUYAO_RETRIEVAL_FILTER = RetrievalFilter(domains=frozenset({KnowledgeDomain.LIUYAO, KnowledgeDomain.YIJING}))


def build_liuyao_queries(question_text: str, hexagram: HexagramResult) -> list[str]:
    queries = []

    # 1. 本卦查询
    p_hex = hexagram.primary_hexagram
    q1 = f"{p_hex.upper_trigram}上{p_hex.lower_trigram}下"
    if p_hex.name:
        q1 += f" {p_hex.name}卦"
    queries.append(f"卦象含义 {q1}")

    # 2. 动爻查询
    if hexagram.moving_line_positions:
        moves = "、".join([f"第{pos}爻动" for pos in hexagram.moving_line_positions])
        c_hex = hexagram.changed_hexagram
        c_str = f"变卦{c_hex.upper_trigram}上{c_hex.lower_trigram}下" if c_hex else ""
        queries.append(f"爻辞与动爻解析 {moves} {c_str}".strip())

    # 3. 事象映射
    queries.append(f"六爻决策参考 测事 测{question_text}")

    return queries


class LiuyaoRetrievalBuilder:
    def __init__(self, retrieval_service: RetrievalService):
        self._retrieval_service = retrieval_service

    async def retrieve(self, question_text: str, hexagram: HexagramResult) -> list[RetrievalResult]:
        queries = build_liuyao_queries(question_text, hexagram)
        all_results = []
        seen = set()

        for query in queries:
            results = await self._retrieval_service.retrieve(query, filters=LIUYAO_RETRIEVAL_FILTER)
            for res in results:
                if res.chunk_id not in seen:
                    seen.add(res.chunk_id)
                    all_results.append(res)

        return all_results
