import re

from guanchen_v2.knowledge.ingestion.errors import KnowledgeStructureParseError
from guanchen_v2.knowledge.ingestion.models import NormalizedKnowledgeSource
from guanchen_v2.knowledge.models import KnowledgeDocument


class MarkdownKnowledgeParser:
    """
    Heading-aware Markdown 解析器。
    维持标题树堆栈，智能切分知识块，同时抵御空标题、标题跳级和重复路径等异常。
    """

    def __init__(self):
        # 严格匹配 ATX 标题 (仅限 # 且跟随至少一个空白字符)
        self._heading_pattern = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")

    def parse(self, source: NormalizedKnowledgeSource) -> list[KnowledgeDocument]:
        heading_stack: list[tuple[int, str]] = []
        current_lines: list[str] = []
        seen_sections = set()
        documents: list[KnowledgeDocument] = []
        inside_fence = False
        fence_char = ""

        def flush_section():
            text = "\n".join(current_lines).strip()
            if not text:
                return

            path_components = [title for lvl, title in heading_stack if lvl > 1]

            if not path_components:
                section_name = source.source_title
            else:
                section_name = " / ".join(path_components)

            if section_name in seen_sections:
                raise KnowledgeStructureParseError(f"在文件 {source.source_path} 中发现重复的 section 路径: {section_name}")
            seen_sections.add(section_name)

            doc = KnowledgeDocument.from_parser(
                domain=source.domain,
                source_title=source.source_title,
                source_type=source.source_type,
                section=section_name,
                text=text,
            )
            documents.append(doc)

        for line in source.text.splitlines():
            stripped = line.strip()

            is_fence = stripped.startswith("```") or stripped.startswith("~~~")
            if is_fence:
                current_fence_char = stripped[0]
                if not inside_fence:
                    inside_fence = True
                    fence_char = current_fence_char
                    current_lines.append(line)
                    continue
                elif current_fence_char == fence_char:
                    inside_fence = False
                    fence_char = ""
                    current_lines.append(line)
                    continue

            if not inside_fence:
                match = self._heading_pattern.match(line)
                if match:
                    level = len(match.group(1))
                    title = match.group(2)

                    # 只要遇到新标题，立即把上一个归属块封存打板
                    flush_section()
                    current_lines.clear()

                    current_max_level = heading_stack[-1][0] if heading_stack else 0

                    # 防御跳级 (例如从 H2 直接跳跃到 H4)
                    if current_max_level > 0 and level > current_max_level + 1:
                        raise KnowledgeStructureParseError(
                            f"在文件 {source.source_path} 中发现结构跳级:试图从 H{current_max_level} 直接跳跃到 H{level}"
                        )

                    # 维护上下文堆栈，弹出所有层级 >= 当前级别的同辈和晚辈标题
                    while heading_stack and heading_stack[-1][0] >= level:
                        heading_stack.pop()

                    heading_stack.append((level, title))
                    continue

            # 非标题 / 代码块内内容，统统算作当前小节的正文
            current_lines.append(line)

        # 刷出最后一块
        flush_section()

        return documents
