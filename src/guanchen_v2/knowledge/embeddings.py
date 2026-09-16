from typing import Sequence

from sentence_transformers import SentenceTransformer

from guanchen_v2.knowledge.errors import KnowledgeEmbeddingError
from guanchen_v2.knowledge.models import KnowledgeChunk


class BgeEmbeddingAdapter:
    """
    GuanChen BGE Embedding Adapter。

    职责：
    1. 使用固定 Embedding 模型生成 Dense Vector。
    2. 保证输出维度为 512。
    3. 保证向量执行 L2 normalization。
    4. 管理模型生命周期与 device / batch 策略。
    5. 向持久化与检索层暴露稳定的模型身份。
    6. 隔离 sentence-transformers / PyTorch 异常。

    不负责：
    - PostgreSQL / pgvector
    - Retrieval
    - Reranker
    - Citation
    """

    MODEL_NAME = "BAAI/bge-small-zh-v1.5"
    DIMENSION = 512

    def __init__(
        self,
        device: str = "cpu",
        batch_size: int = 32,
    ) -> None:
        self._device = device
        self._batch_size = batch_size

        try:
            self._model = SentenceTransformer(
                self.MODEL_NAME,
                device=self._device,
            )
        except Exception as exc:
            raise KnowledgeEmbeddingError("Embedding 模型加载失败。") from exc

    @property
    def model_name(self) -> str:
        """
        当前 Adapter 生成向量所使用的稳定模型身份。

        Persistence 与 Dense Retrieval 必须使用该值，
        防止不同 Embedding 模型的向量被错误混用。
        """
        return self.MODEL_NAME

    def embed_documents(
        self,
        chunks: Sequence[KnowledgeChunk],
    ) -> list[list[float]]:
        if not chunks:
            return []

        texts_to_embed: list[str] = []

        for chunk in chunks:
            if not chunk.text.strip():
                raise KnowledgeEmbeddingError(f"尝试对空文本进行 Embedding。Chunk ID: {chunk.chunk_id}")

            # stored chunk text != embedding representation
            #
            # 数据库存储的 chunk.text 保持原文可读性；
            # 模型输入额外加入 source_title + section，
            # 但绝不修改 KnowledgeChunk 本身。
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

        expected_shape = (
            len(chunks),
            self.DIMENSION,
        )

        if not hasattr(embeddings, "shape") or embeddings.shape != expected_shape:
            actual_shape = getattr(
                embeddings,
                "shape",
                "Unknown",
            )

            raise KnowledgeEmbeddingError(f"模型输出的形状异常，预期为 {expected_shape}，实际为 {actual_shape}。")

        try:
            return embeddings.tolist()
        except Exception as exc:
            raise KnowledgeEmbeddingError("向量格式转换失败。") from exc

    def embed_query(
        self,
        query: str,
    ) -> list[float]:
        if not query.strip():
            raise KnowledgeEmbeddingError("检索查询 (Query) 不能为空。")

        try:
            embedding = self._model.encode(
                query,
                show_progress_bar=False,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        except Exception as exc:
            raise KnowledgeEmbeddingError("查询 Embedding 推理失败。") from exc

        expected_shape = (self.DIMENSION,)

        if not hasattr(embedding, "shape") or embedding.shape != expected_shape:
            actual_shape = getattr(
                embedding,
                "shape",
                "Unknown",
            )

            raise KnowledgeEmbeddingError(f"模型输出了错误的形状 {actual_shape}，预期应为 {expected_shape}。")

        try:
            return embedding.tolist()
        except Exception as exc:
            raise KnowledgeEmbeddingError("向量格式转换失败。") from exc
