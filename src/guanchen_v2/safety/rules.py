import re
import unicodedata

from guanchen_v2.safety.models import RiskDomain, RiskLevel, SafetyAction, SafetyDecision


class SafetyRuleEngine:
    def evaluate(self, text: str) -> SafetyDecision:
        text = re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).lower()
        if not text or not text.strip():
            return SafetyDecision(
                risk_domain=RiskDomain.NONE, risk_level=RiskLevel.SAFE, action=SafetyAction.ALLOW, reason_code="RULE_EMPTY_OR_WHITESPACE"
            )

        # 1. 明确的极端危机意图，精准捕获，绝不误杀通用名词
        crisis_phrases = [
            "我想自杀",
            "我要自杀",
            "我不想活了",
            "我要跳楼",
            "我想结束生命",
            "教我怎么割腕",
            "我想死",
            "活不下去了",
            "准备跳楼",
            "准备自杀",
            "今晚就去死",
            "我撑不下去了",
            "不如死了",
            "我想伤害自己",
            "killmyself",
            "endmylife",
            "iwanttodie",
            "suicidal",
            "我要杀人",
            "我要杀了",
            "教我杀人",
        ]
        if any(phrase in text for phrase in crisis_phrases):
            return SafetyDecision(
                risk_domain=RiskDomain.SELF_HARM, risk_level=RiskLevel.CRISIS, action=SafetyAction.SAFE_RESPONSE, reason_code="RULE_CRISIS_MATCH"
            )

        divination = any(word in text for word in ("八字", "命理", "起卦", "起一卦", "六爻", "算算", "算命", "卦象"))
        if divination and any(word in text for word in ("全仓", "梭哈", "卖房炒", "借钱炒")):
            return SafetyDecision(
                risk_domain=RiskDomain.INVESTMENT,
                risk_level=RiskLevel.HIGH_RISK,
                action=SafetyAction.SAFE_RESPONSE,
                reason_code="RULE_EXTREME_FINANCIAL_DECISION",
            )
        if divination and any(word in text for word in ("停药", "放弃治疗", "拒绝手术", "是不是癌", "能挺过去")):
            return SafetyDecision(
                risk_domain=RiskDomain.MEDICAL,
                risk_level=RiskLevel.HIGH_RISK,
                action=SafetyAction.SAFE_RESPONSE,
                reason_code="RULE_EXTREME_MEDICAL_DECISION",
            )

        # 2. 模糊风险词映射，命中后必须经过 classifier
        # 扩充医疗相关词汇，覆盖重症、医生、体检等场景
        medical_kws = [
            "病",
            "癌",
            "医院",
            "手术",
            "药",
            "健康",
            "重症",
            "医生",
            "体检",
            "结节",
            "治疗",
            "诊断",
            "抑郁",
            "疼",
            "medical",
            "cancer",
            "surgery",
            "medication",
        ]
        if any(kw in text for kw in medical_kws):
            return SafetyDecision(
                risk_domain=RiskDomain.MEDICAL,
                risk_level=RiskLevel.SENSITIVE,
                action=SafetyAction.REQUIRE_CLASSIFIER,
                reason_code="RULE_MEDICAL_REQUIRES_CLASSIFIER",
            )

        investment_kws = [
            "投资",
            "股票",
            "基金",
            "理财",
            "全仓",
            "买入",
            "卖房",
            "炒股",
            "梭哈",
            "杠杆",
            "比特币",
            "虚拟币",
            "加密货币",
            "贷款",
            "期货",
            "卖出",
            "bitcoin",
            "crypto",
            "stock",
            "invest",
        ]
        if any(kw in text for kw in investment_kws):
            return SafetyDecision(
                risk_domain=RiskDomain.INVESTMENT,
                risk_level=RiskLevel.SENSITIVE,
                action=SafetyAction.REQUIRE_CLASSIFIER,
                reason_code="RULE_INVESTMENT_REQUIRES_CLASSIFIER",
            )

        legal_kws = ["起诉", "法院", "法律", "离婚", "维权", "打官司", "律师", "诉讼", "判刑", "坐牢", "合同", "legal", "lawsuit", "lawyer"]
        if any(kw in text for kw in legal_kws):
            return SafetyDecision(
                risk_domain=RiskDomain.LEGAL,
                risk_level=RiskLevel.SENSITIVE,
                action=SafetyAction.REQUIRE_CLASSIFIER,
                reason_code="RULE_LEGAL_REQUIRES_CLASSIFIER",
            )

        if any(word in text for word in ("撑不住", "消失", "轻生", "寻死", "自残", "伤害", "活着没意义", "活着没有意义")):
            return SafetyDecision(
                risk_domain=RiskDomain.SELF_HARM,
                risk_level=RiskLevel.SENSITIVE,
                action=SafetyAction.REQUIRE_CLASSIFIER,
                reason_code="RULE_AMBIGUOUS_CRISIS",
            )

        # 3. 未命中任何风险规则
        return SafetyDecision(risk_domain=RiskDomain.NONE, risk_level=RiskLevel.SAFE, action=SafetyAction.ALLOW, reason_code="RULE_DEFAULT_ALLOW")
