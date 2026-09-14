# GuanChen Knowledge Corpus Manifest

**核心安全与版权原则**：
所有被标记为 `public_domain_classic` 的古籍，必须采用其未受现代版权保护的原始文言文/刻印整理基础版。**绝不使用或抓取**任何现代作者拥有独创性翻译、现代白话解析和具有版权主张的校注版本，以严格遵守工程版权合规底线。

## Stage 4 冻结首批语料 (Phase 1)

| 书名 (source_title) | 领域 (domain) | 来源类型 (source_type) | 状态 (status) | 文本底本/使用依据 (edition_or_basis) | 获取源头/下载路径 (origin) | 本地路径 (local_path) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **《渊海子平》** | `bazi` | `public_domain_classic` | verified | 明代公版纯古文整理版，无现代人白话翻译版权。 | (待补充互联网维基文库或古籍库确切 URL) | `data/knowledge/raw/yuanhai_ziping/` |
| **《三命通会》** | `bazi` | `public_domain_classic` | verified | 钦定四库全书原文本底本。 | (待补充确切 URL) | `data/knowledge/raw/sanming_tonghui/` |
| **八字工程笔记** | `bazi` | `project_note` | planned | GuanChen 项目团队内部编制的八字概念解释对齐表。 | 项目自有 | `data/knowledge/raw/project_notes_bazi/` |
| **《增删卜易》** | `liuyao` | `public_domain_classic` | verified | 清代公版纯古文版。 | (待补充确切 URL) | `data/knowledge/raw/zengshan_buyi/` |
| **六爻工程笔记** | `liuyao` | `project_note` | planned | 针对六爻体系的内部定义与规范说明。 | 项目自有 | `data/knowledge/raw/project_notes_liuyao/` |
| **通识文化注脚** | `traditional_culture` | `project_note` | planned | 不涉特定具体方术，解释如干支、五行、八卦的基础符号语义。 | 项目自有 | `data/knowledge/raw/project_notes_culture/` |

**RAG 越权风险声明**：
以上所有典籍（如《渊海子平》、《滴天髓》）均仅作为大模型理解、解释八字术语的**知识来源**（Knowledge Grounding）。确定性排盘、大运推导、十神对应关系**仍永远只能由系统 Tool 生成**。RAG 不能授权大模型代替工具进行诸如“判断日主旺衰”、“断性格”、“断格局”的确定性计算！