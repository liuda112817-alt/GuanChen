from typing import Sequence

from sentence_transformers import SentenceTransformer

from guanchen_v2.knowledge.errors import KnowledgeEmbeddingError
from guanchen_v2.knowledge.models import KnowledgeChunk


class BgeEmbeddingAdapter:
    """
    GuanChen BGE Embedding 适配器。
    严格边界：
    1. 仅负责 512 维的 Dense Vector 生成与 L2 归一化。
    2. 管理模型生命周期与设备策略。
    3. 隔离第三方 PyTorch / sentence-transformers 异常。
    4. 不涉及任何 PGVector / Retriever / Reranker 逻辑。
    """

    MODEL_NAME = "BAAI/bge-small-zh-v1.5"
    DIMENSION = 512

    def __init__(self, device: str = "cpu", batch_size: int = 32):
        self._device = device
        self._batch_size = batch_size

        try:
            self._model = SentenceTransformer(self.MODEL_NAME, device=self._device)
        except Exception as exc:
            raise KnowledgeEmbeddingError("Embedding 模型加载失败。") from exc

    def embed_documents(self, chunks: Sequence[KnowledgeChunk]) -> list[list[float]]:
        if not chunks:
            return []

        texts_to_embed = []
        for chunk in chunks:
            if not chunk.text.strip():
                raise KnowledgeEmbeddingError(
                    f"尝试对空文本进行 Embedding。Chunk ID: {chunk.chunk_id}"
                )

            # 业务构造规则：source_title + section + chunk.text
            # 绝不能修改传入的 chunk 对象的属性，只构建专用于模型输入的字符串
            embed_input = f"{chunk.source_title}\n{chunk.section}\n{chunk.text}"
            texts_to_embed.append(embed_input)

        try:
            embeddings = self._model.encode(
                texts_to_embed,
                batch_size=self._batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        except Exception as exc:
            raise KnowledgeEmbeddingError("文档批量 Embedding 推理失败。") from exc

        expected_shape = (len(chunks), self.DIMENSION)
        if not hasattr(embeddings, "shape") or embeddings.shape != expected_shape:
            actual_shape = getattr(embeddings, "shape", "Unknown")
            raise KnowledgeEmbeddingError(
                f"模型输出的形状异常，预期为 {expected_shape}，实际为 {actual_shape}。"
            )

        try:
            return embeddings.tolist()
        except Exception as exc:
            raise KnowledgeEmbeddingError("向量格式转换失败。") from exc

    def embed_query(self, query: str) -> list[float]:
        if not query.strip():
            raise KnowledgeEmbeddingError("检索查询 (Query) 不能为空。")

        try:
            embedding = self._model.encode(
                query, show_progress_bar=False, normalize_embeddings=True, convert_to_numpy=True
            )
        except Exception as exc:
            raise KnowledgeEmbeddingError("查询 Embedding 推理失败。") from exc

        expected_shape = (self.DIMENSION,)
        if not hasattr(embedding, "shape") or embedding.shape != expected_shape:
            actual_shape = getattr(embedding, "shape", "Unknown")
            raise KnowledgeEmbeddingError(
                f"模型输出了错误的形状 {actual_shape}，预期应为 {expected_shape}。"
            )

        try:
            return embedding.tolist()
        except Exception as exc:
            raise KnowledgeEmbeddingError("向量格式转换失败。") from exc
