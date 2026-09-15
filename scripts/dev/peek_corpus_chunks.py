import sys
from pathlib import Path

from guanchen_v2.knowledge.ingestion.chunker import KnowledgeDocumentChunker
from guanchen_v2.knowledge.ingestion.loader import KnowledgeSourceLoader
from guanchen_v2.knowledge.ingestion.normalizer import KnowledgeSourceNormalizer
from guanchen_v2.knowledge.ingestion.parser import MarkdownKnowledgeParser


def peek_chunks():
    raw_root = Path("data/knowledge/raw_verified").resolve()
    if not raw_root.exists():
        print(f"找不到语料目录: {raw_root}")
        sys.exit(1)

    loader = KnowledgeSourceLoader(raw_root)
    normalizer = KnowledgeSourceNormalizer()
    parser = MarkdownKnowledgeParser()
    chunker = KnowledgeDocumentChunker(max_chars=800, chunk_overlap=80)

    try:
        sources = loader.load_all()
    except Exception as e:
        print(f"语料加载失败: {e}")
        sys.exit(1)

    output_file = Path("corpus_chunk_dict.txt")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=== GuanChen 语料 Chunk ID 字典 ===\n")
        f.write("使用方法：在本文档中 Ctrl+F 搜索你想作为正确答案的句子，即可找到上方的 chunk_id。\n\n")

        for raw_source in sources:
            norm_source = normalizer.normalize(raw_source)
            docs = parser.parse(norm_source)
            chunks = chunker.chunk_documents(docs)

            f.write(f"\n{'=' * 60}\n")
            f.write(f" 书名: {norm_source.source_title} ({norm_source.domain.value})\n")
            f.write(f"{'=' * 60}\n")

            for c in chunks:
                f.write(f" 章节: {c.section}\n")
                f.write(f" chunk_id: {c.chunk_id}\n")
                # 打印前 100 个字符方便辨认
                preview = c.text.replace("\n", " ")[:100]
                f.write(f" 预览: {preview}...\n")
                f.write("-" * 40 + "\n")

    print(f"透视完成！请打开项目根目录下的 {output_file.name} 挑选你的 Eval Ground Truth。")


if __name__ == "__main__":
    peek_chunks()
