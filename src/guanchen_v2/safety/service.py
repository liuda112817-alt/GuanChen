from guanchen_v2.observability.decorators import trace
from guanchen_v2.safety.classifier import SafetyClassifier
from guanchen_v2.safety.models import RiskDomain, RiskLevel, SafetyAction, SafetyDecision
from guanchen_v2.safety.rules import SafetyRuleEngine


class SafetyService:
    def __init__(self, rule_engine: SafetyRuleEngine, classifier: SafetyClassifier | None = None):
        self.rule_engine = rule_engine
        self.classifier = classifier

    def _safe_response_message(self, domain: RiskDomain) -> str:
        messages = {
            RiskDomain.SELF_HARM: (
                "听起来你正在承受很大的痛苦，此时我不会进行命理推演。请先远离可能伤害自己或他人的物品、地点，"
                "联系一位信任的人陪着你。如果已受伤或有立即行动的危险，请马上联系当地急救服务或前往急诊。你现在是否安全？"
            ),
            RiskDomain.MEDICAL: "我不能提供医疗诊断或建议。如果存在健康问题，请及时就医咨询专业医生。",
            RiskDomain.INVESTMENT: "我不能提供任何投资建议或财务指导。请谨慎对待财务决策，必要时咨询专业金融机构。",
            RiskDomain.LEGAL: "我不能提供法律建议。如果遇到法律纠纷，请寻求专业律师或法律机构的帮助。",
        }
        return messages.get(domain, "很抱歉，我无法回答该问题或提供此类建议。")

    @trace(component="safety", event_type="PRECHECK")
    async def evaluate(self, text: str) -> SafetyDecision:
        decision = self.rule_engine.evaluate(text)

        if decision.action != SafetyAction.REQUIRE_CLASSIFIER:
            if decision.action in {SafetyAction.SAFE_RESPONSE, SafetyAction.ALLOW_WITH_BOUNDARY} and not decision.user_message:
                decision.user_message = self._safe_response_message(decision.risk_domain)
            return decision

        if self.classifier is None:
            return SafetyDecision(
                risk_domain=decision.risk_domain,
                risk_level=RiskLevel.HIGH_RISK,
                action=SafetyAction.SAFE_RESPONSE,
                reason_code="FALLBACK_CLASSIFIER_UNAVAILABLE",
                classifier_used=False,
                user_message=self._safe_response_message(decision.risk_domain),
            )

        try:
            classification = await self.classifier.classify(text)
        except Exception:
            return SafetyDecision(
                risk_domain=decision.risk_domain,
                risk_level=RiskLevel.HIGH_RISK,
                action=SafetyAction.SAFE_RESPONSE,
                reason_code="FALLBACK_CLASSIFIER_ERROR",
                classifier_used=True,
                user_message=self._safe_response_message(decision.risk_domain),
            )

        final_decision = SafetyDecision(
            risk_domain=classification.risk_domain,
            risk_level=classification.risk_level,
            action=classification.recommended_action,
            reason_code=classification.reason_code,
            classifier_used=True,
        )

        # Risk severity is authoritative even if a classifier proposes a contradictory action.
        if final_decision.risk_level in {RiskLevel.HIGH_RISK, RiskLevel.CRISIS}:
            final_decision.action = SafetyAction.SAFE_RESPONSE

        if final_decision.action in {SafetyAction.SAFE_RESPONSE, SafetyAction.ALLOW_WITH_BOUNDARY}:
            final_decision.user_message = self._safe_response_message(final_decision.risk_domain)

        return final_decision
