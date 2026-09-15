import math

import torch.nn as nn
from sentence_transformers import CrossEncoder

from guanchen_v2.knowledge.errors import KnowledgeRerankerError


class BgeRerankerAdapter:
    """
    BAAI/bge-reranker-base 交叉编码器 (Cross-Encoder) 适配层。
    职责：
    1. 冻结模型语义契约，仅接受 SentenceTransformers 方案。
    2. 抵挡大模型环境所有的第三方报错，转译为安全的业务异常。
    3. 拦截数量不对齐、NaN、无穷大 (Inf) 等大模型幻觉/异常。
    """

    MODEL_NAME = "BAAI/bge-reranker-base"

    def __init__(self):
        self._model = None

    def _get_model(self):
        if self._model is not None:
            return self._model

        try:
            self._model = CrossEncoder(self.MODEL_NAME, default_activation_function=nn.Identity())
            return self._model
        except Exception as exc:
            raise KnowledgeRerankerError(
                f"无法加载重排模型 {self.MODEL_NAME}。请检查网络或本地缓存。"
            ) from exc

    def score_pairs(self, pairs: list[tuple[str, str]]) -> list[float]:
        """
        向交叉编码器发送成对的 (query, passage)，获取未归一化的原生打分。
        分数越大代表相关性越高。
        """
        if not pairs:
            return []

        model = self._get_model()

        try:
            raw_scores = model.predict(pairs)
        except Exception as exc:
            raise KnowledgeRerankerError("重排模型推理崩溃。") from exc

        try:
            if hasattr(raw_scores, "tolist"):
                scores_list = raw_scores.tolist()
            elif isinstance(raw_scores, list):
                scores_list = raw_scores
            else:
                scores_list = [float(raw_scores)]
        except Exception as exc:
            raise KnowledgeRerankerError("无法将重排模型的输出解析为浮点数列表。") from exc

        if len(scores_list) != len(pairs):
            raise KnowledgeRerankerError("重排模型返回的评分数量与输入对数量不匹配！")

        final_scores = []
        for i, s in enumerate(scores_list):
            try:
                score = float(s)
            except (TypeError, ValueError) as exc:
                raise KnowledgeRerankerError(f"重排模型返回了非标量结构或无法转为浮点数：{s}") from exc

            if not math.isfinite(score):
                raise KnowledgeRerankerError(f"重排模型返回了非法的无穷数值打分 (NaN/Inf)：{score}")

            final_scores.append(score)

        return final_scores
