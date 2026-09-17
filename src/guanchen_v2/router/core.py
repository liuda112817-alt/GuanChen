import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from guanchen_v2.llm.client import LLMClient
from guanchen_v2.prompts.router import ROUTER_SYSTEM_PROMPT
from guanchen_v2.router.contracts import (
    INTENT_REQUIRED_DATA,
    IntentType,
    NonBlankRouteText,
    RequiredDataType,
    RoutingResult,
)


class RouterDecision(BaseModel):
    """
    供 Router 内部流转使用的领域决策结果。
    """

    model_config = ConfigDict(extra="forbid")

    primary_intent: IntentType

    secondary_intents: tuple[IntentType, ...] = Field(
        default_factory=tuple,
        max_length=1,
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    reason: NonBlankRouteText

    @model_validator(mode="after")
    def validate_intent_combination(self) -> "RouterDecision":
        """让 LLM 的结构化输出本身就必须满足领域组合契约"""
        if self.primary_intent in self.secondary_intents:
            raise ValueError("primary_intent 不能出现在 secondary_intents 中")

        non_combinable = {
            IntentType.CHITCHAT,
            IntentType.OUT_OF_SCOPE,
        }

        if self.primary_intent in non_combinable and self.secondary_intents:
            raise ValueError("CHITCHAT / OUT_OF_SCOPE 不能形成双领域路由")

        if any(intent in non_combinable for intent in self.secondary_intents):
            raise ValueError("secondary_intents 只能包含专业领域")

        return self


def resolve_required_data(
    primary_intent: IntentType,
    secondary_intents: tuple[IntentType, ...] = (),
) -> tuple[RequiredDataType, ...]:
    """确定性富化：根据明确的意图枚举，严格映射出所需的数据依赖"""
    resolved: list[RequiredDataType] = []

    for intent in (primary_intent, *secondary_intents):
        for item in INTENT_REQUIRED_DATA[intent]:
            if item not in resolved:
                resolved.append(item)

    return tuple(resolved)


def build_routing_result(decision: RouterDecision) -> RoutingResult:
    """内部组装：将决策与确定性需求合并，转化为对外不可变的契约模型"""
    return RoutingResult(
        primary_intent=decision.primary_intent,
        secondary_intents=decision.secondary_intents,
        confidence=decision.confidence,
        required_data=resolve_required_data(
            decision.primary_intent,
            decision.secondary_intents,
        ),
        reason=decision.reason,
    )


class HighPrecisionRuleRouter:
    """高精度代码路由规则：宁缺毋滥，只拦截确凿的意图，节省 LLM 调用"""

    def _is_explicit_dual_domain(self, query: str) -> bool:
        return bool(
            re.match(
                r"^(请)?结合(我的)?八字(和|与)(昨晚的?|这个|我的)?梦.*(一起看|综合看|分析|解读|参考)",
                query,
            )
        )

    def _is_explicit_bazi_request(self, query: str) -> bool:
        return bool(re.match(r"^(帮我)?看看我的八字.*", query) or re.match(r"^(帮我)?(排|分析)(一下)?(我的)?八字.*", query))

    def _is_explicit_dream_request(self, query: str) -> bool:
        return bool(re.match(r"^(我)?(昨晚|昨天|刚刚)?梦(到|见).*", query))

    def _is_explicit_liuyao_request(self, query: str) -> bool:
        return bool(re.match(r"^(帮我)?起一卦.*", query))

    def _has_personal_invocation_signal(self, query: str) -> bool:
        """识别是否有个人专业调用的强烈暗示，防止知识问答被误杀或误伤"""
        return bool(re.search(r"(我|帮我|梦见|梦到|我的|算一卦|起一卦)", query))

    def _is_clear_knowledge_question(self, query: str) -> bool:
        is_concept_format = bool(re.match(r"^(什么是|什么叫|解释).*|.*(是什么意思|有什么区别|的意思)[?？]*$", query))
        return is_concept_format and not self._has_personal_invocation_signal(query)

    def _is_pure_chitchat(self, query: str) -> bool:
        return bool(re.match(r"^(你好|谢谢|在吗|哈喽|嗨)$", query))

    def _is_clear_out_of_scope(self, query: str) -> bool:
        return bool(re.match(r"^(帮我写一段|用).*代码.*", query))

    def match(self, query: str) -> Optional[RouterDecision]:
        normalized = query.strip()

        if self._is_explicit_dual_domain(normalized):
            return RouterDecision(
                primary_intent=IntentType.BAZI,
                secondary_intents=(IntentType.DREAM,),
                confidence=1.0,
                reason="高精度规则：显式要求结合八字与解梦",
            )

        if self._is_clear_knowledge_question(normalized):
            return RouterDecision(
                primary_intent=IntentType.KNOWLEDGE,
                confidence=1.0,
                reason="高精度规则：典型概念释义且无个人专业调用",
            )

        if self._is_explicit_dream_request(normalized):
            return RouterDecision(
                primary_intent=IntentType.DREAM,
                confidence=1.0,
                reason="高精度规则：显式解梦请求",
            )

        if self._is_explicit_bazi_request(normalized):
            return RouterDecision(
                primary_intent=IntentType.BAZI,
                confidence=1.0,
                reason="高精度规则：显式八字排盘请求",
            )

        if self._is_explicit_liuyao_request(normalized):
            return RouterDecision(
                primary_intent=IntentType.LIUYAO,
                confidence=1.0,
                reason="高精度规则：显式起卦请求",
            )

        if self._is_clear_knowledge_question(normalized):
            return RouterDecision(
                primary_intent=IntentType.KNOWLEDGE,
                confidence=1.0,
                reason="高精度规则：典型概念释义且无个人诉求",
            )

        if self._is_pure_chitchat(normalized):
            return RouterDecision(
                primary_intent=IntentType.CHITCHAT,
                confidence=1.0,
                reason="高精度规则：标准轻量会话",
            )

        if self._is_clear_out_of_scope(normalized):
            return RouterDecision(
                primary_intent=IntentType.OUT_OF_SCOPE,
                confidence=1.0,
                reason="高精度规则：明确的非产品任务",
            )

        return None


class TwoLayerIntentRouter:
    """双层意图路由器：规则打头阵，LLM 模型兜底消歧"""

    def __init__(
        self,
        rule_router: HighPrecisionRuleRouter,
        llm_client: LLMClient,
    ):
        self._rule_router = rule_router
        self._llm_client = llm_client

    async def route(self, query: str) -> RoutingResult:
        decision = self._rule_router.match(query)

        if decision is None:
            decision = await self._llm_client.generate_structured(
                system_prompt=ROUTER_SYSTEM_PROMPT,
                user_prompt=query,
                schema=RouterDecision,
            )

        return build_routing_result(decision)
