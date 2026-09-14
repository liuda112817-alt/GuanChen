from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field, field_validator

from guanchen_v2.knowledge.models import KnowledgeDomain, RetrievalFilter, RetrievalResult
from guanchen_v2.knowledge.retrieval.service import RetrievalService


class BaziKnowledgeQuery(BaseModel):
    """Bazi Agent 调用的检索凭证"""

    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, description="需要检索的八字传统知识问题")

    @field_validator("query")
    @classmethod
    def check_query_not_empty(cls, v: str) -> str:
        normalized = v.strip()
        if not normalized:
            raise ValueError("query 不能为空或纯空格")
        return normalized


class BaziKnowledgeArtifact(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    results: list[RetrievalResult]


def build_retrieve_bazi_knowledge_tool(retrieval_service: RetrievalService):
    """
    构造 Bazi 专用知识检索工具。
    强行锁定领域为 BAZI，切断 LLM 漫游其他知识域（如六爻）的可能性。
    """

    @tool(
        "retrieve_bazi_knowledge",
        args_schema=BaziKnowledgeQuery,
        response_format="content_and_artifact",
    )
    async def retrieve_bazi_knowledge(query: str) -> tuple[str, BaziKnowledgeArtifact]:
        """
        当你需要解释 calculate_bazi 已明确返回的排盘事实，
        例如月令相关传统理论、十神的传统含义、干支符号的文献解释时，
        调用此工具查询八字知识库。
        """
        # 锁定检索边界为 八字
        filters = RetrievalFilter(domains=frozenset({KnowledgeDomain.BAZI}))

        # 将重排是否开启的决策彻底交由外部 Service 自身的默认配置决定，Agent 不干涉
        results = await retrieval_service.retrieve(query=query, filters=filters)

        if not results:
            return "当前知识库未检索到足够依据支持进一步的传统理论解释。", BaziKnowledgeArtifact(
                results=[]
            )

        parts = ["=== BAZI KNOWLEDGE EVIDENCE ==="]
        for res in results:
            parts.append(
                f"chunk_id: {res.chunk_id}\n"
                f"source_type: {res.source_type.value}\n"
                f"source_title: {res.source_title}\n"
                f"section: {res.section}\n"
                f"evidence_text:\n{res.text}\n"
                f"---"
            )

        formatted_evidence = "\n".join(parts)
        return formatted_evidence, BaziKnowledgeArtifact(results=results)

    return retrieve_bazi_knowledge
