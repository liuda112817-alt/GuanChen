from pathlib import Path

import pytest

from guanchen_v2.knowledge.ingestion.chunker import KnowledgeDocumentChunker
from guanchen_v2.knowledge.ingestion.loader import KnowledgeSourceLoader
from guanchen_v2.knowledge.ingestion.normalizer import KnowledgeSourceNormalizer
from guanchen_v2.knowledge.ingestion.parser import MarkdownKnowledgeParser


def test_corpus_v1_smoke_pipeline():
    """真实语料 Smoke Test: Loader -> Normalizer -> Parser -> Chunker 全链路连通性测试"""
    raw_root = Path("data/knowledge/raw_verified").resolve()

    if not raw_root.exists():
        pytest.skip("本地未发现真实语料库，跳过 Smoke Test。")

    loader = KnowledgeSourceLoader(raw_root)
    normalizer = KnowledgeSourceNormalizer()
    parser = MarkdownKnowledgeParser()
    chunker = KnowledgeDocumentChunker(max_chars=800, chunk_overlap=80)

    sources = loader.load_all()
    assert len(sources) > 0, "未能从 raw_verified 加载到任何 Markdown 知识源"

    total_documents = []
    seen_doc_ids = set()

    for raw_source in sources:
        norm_source = normalizer.normalize(raw_source)
        docs = parser.parse(norm_source)
        assert docs, f"{norm_source.source_path} 未产生任何 KnowledgeDocument"

        # 【此处断言放开】：实际周易不仅有 64 卦，可能还有系辞等结构
        if norm_source.source_path.endswith("zhouyi.md"):
            assert len(docs) >= 64, "《周易》至少应产生 64 个基础 Document"

        for doc in docs:
            assert doc.document_id not in seen_doc_ids, f"发生 document_id 碰撞: {doc.document_id}"
            seen_doc_ids.add(doc.document_id)
            total_documents.append(doc)

    assert len(total_documents) > 0

    # ==============================
    # 终极一跃：将全量 Document 进行切分
    # ==============================
    all_chunks = chunker.chunk_documents(total_documents)

    # 基本数学逻辑：切出来的碎片数量绝对不可能少于原文篇数
    assert len(all_chunks) >= len(total_documents)

    seen_chunk_ids = set()

    # 验证血缘图谱：每一个碎片的 document_id 都一定有源头对应
    for chunk in all_chunks:
        assert chunk.chunk_id, "chunk_id 不能为空"
        assert chunk.document_id, "document_id 不能为空"
        assert chunk.section, "section 不能为空"
        assert chunk.text, "text 不能为空"

        assert chunk.document_id in seen_doc_ids, f"血缘断裂！找到未知来源的 chunk，关联 document_id: {chunk.document_id}"

        assert chunk.chunk_id not in seen_chunk_ids, f"发生 chunk_id 全局碰撞 (重复数据块): {chunk.chunk_id}"
        seen_chunk_ids.add(chunk.chunk_id)

    # 作为本地观察用途打印统计，但不阻断流程
    print(f"\n[Smoke Test Success] 统计: 产生 {len(total_documents)} 份 Documents, 拆分为 {len(all_chunks)} 份 Chunks.")
