import asyncio
import time
from pathlib import Path

from guanchen_v2.knowledge.embeddings import BgeEmbeddingAdapter
from guanchen_v2.knowledge.ingestion.chunker import KnowledgeDocumentChunker
from guanchen_v2.knowledge.ingestion.loader import KnowledgeSourceLoader
from guanchen_v2.knowledge.ingestion.normalizer import KnowledgeSourceNormalizer
from guanchen_v2.knowledge.ingestion.parser import MarkdownKnowledgeParser
from guanchen_v2.knowledge.ingestion.service import KnowledgeIngestionService
from guanchen_v2.knowledge.persistence.database import init_db


async def main():
    print("=" * 60)
    print("GuanChen Corpus Ingestion (Dev/Eval)")
    print("=" * 60)

    # 1. 启动并初始化数据库表结构与 Vector 扩展
    print("正在初始化数据库表结构...")
    await init_db()

    # 2. 组装流水线组件
    print("正在加载 BGE Embedding 模型 (可能需要几秒)...")
    embedding_adapter = BgeEmbeddingAdapter(batch_size=4)
    chunker = KnowledgeDocumentChunker(max_chars=800, chunk_overlap=80)
    ingestion_service = KnowledgeIngestionService(chunker, embedding_adapter)

    raw_root = Path("data/knowledge/raw_verified").resolve()
    loader = KnowledgeSourceLoader(raw_root)
    normalizer = KnowledgeSourceNormalizer()
    parser = MarkdownKnowledgeParser()

    # 3. 解析本地语料
    print(f"正在扫描并解析目录: {raw_root} ...")
    sources = loader.load_all()

    total_docs = []
    for raw_source in sources:
        norm_source = normalizer.normalize(raw_source)
        docs = parser.parse(norm_source)
        total_docs.extend(docs)

    print(f"解析完毕。共提取出 {len(total_docs)} 个逻辑文档 (KnowledgeDocument)。")
    print("开始全量入库 (切分 -> 向量化 -> PostgreSQL UPSERT)...")

    # 4. 执行写入
    start_time = time.perf_counter()
    success_count = 0

    for i, doc in enumerate(total_docs, 1):
        try:
            await ingestion_service.ingest_document(doc)
            success_count += 1
            print(f"[{i}/{len(total_docs)}] 成功入库: {doc.source_title} - {doc.section}")
        except Exception as e:
            print(
                f"[{i}/{len(total_docs)}] 入库失败: {doc.source_title} - {doc.section} | 错误: {e}"
            )

    elapsed = time.perf_counter() - start_time
    print("=" * 60)
    print(f"入库作业完成！成功: {success_count}/{len(total_docs)}，耗时: {elapsed:.2f} 秒。")
    print("你现在可以执行 scripts/eval_retrieval.py 开启检索评测了。")


if __name__ == "__main__":
    asyncio.run(main())
