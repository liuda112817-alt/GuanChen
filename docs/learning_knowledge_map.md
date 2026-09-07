# AI Agent / LLM 应用工程当前知识地图

- Status: **Frozen Learning Baseline**
- Version: **v1.0**

本文件用于控制 GuanChen v2 的学习顺序。

规则：

- **A：已掌握，可直接使用** —— 不重复教学。
- **B：已学习，项目中深化** —— 只补当前 Stage 新增复杂度。
- **C：尚未系统学习** —— 首次正式使用前执行：概念 → 原理 → 必要最小练习 → 知识确认 → 项目实现。

---

# A. 已掌握，可以直接进入项目使用

## Python / Engineering

- Python 基础
- CLI
- Git
- HTTP
- JSON
- 基础 LLM API 调用

## RAG Fundamentals

- Document Chunking
- Embedding
- Vector Store
- Retriever
- Reranker
- Context Builder
- Grounded Generation
- Retrieval Evaluation
- Similarity Search
- Top-K
- Retrieval Failure
- Chunk Size 影响
- Query / Retrieval / Reranking / Context 基本关系

## Native Agent Runtime

- Python Function → Tool
- Tool Schema
- Function Calling
- Tool Call Parsing
- JSON Arguments
- Tool Execution
- Tool Result
- tool_call_id
- Assistant Tool Call Message
- Tool Observation
- 完整 Tool Calling 闭环
- Multi-Tool
- Agent Loop
- Multi-step Tool Calling
- ReAct
- Tool Registry
- Calculator / Weather / Search / File Read Tool
- Filesystem Permission Boundary
- Tool Failure → Observation
- Agent Replanning
- max_iterations
- Runtime Safety Guard

## LangChain

- ChatModel
- Message
- SystemMessage
- HumanMessage
- AIMessage
- ToolMessage
- @tool
- bind_tools()
- Tool.invoke()
- Tool Registry
- Runnable
- RunnableLambda
- RunnableSequence
- invoke
- batch
- ChatPromptTemplate
- ChatPromptValue
- StrOutputParser
- Prompt | Model | Parser
- LangChain Agent Loop
- create_agent()
- create_agent() → CompiledStateGraph

## LangGraph

- State
- TypedDict State
- Partial State Update
- NotRequired
- Shared State
- Reducer
- Annotated
- add_messages
- Node
- Edge
- START / END
- Deterministic Edge
- Conditional Edge
- Router
- Loop
- while-loop → Graph Cycle
- recursion_limit

## Persistence / HITL / Store

- MemorySaver / InMemorySaver
- Checkpointer
- Checkpoint
- Thread / thread_id
- StateSnapshot
- get_state()
- get_state_history()
- checkpoint_id
- parent_config
- Replay
- Fork / update_state()
- interrupt()
- Command(resume=...)
- Durable Pause / Resume
- Approval Node
- approve / reject
- Reject → ToolMessage Observation → Replanning
- interrupt node resumes from node start
- side-effect caution before interrupt
- InMemoryStore
- namespace / key / value
- cross-thread Store
- Checkpointer = thread-scoped short-term state
- Store = cross-thread shared memory
- Memory Scope != Storage Durability

---

# B. 已学习，但项目中需要进一步深化

| 能力 | 深化方向 | Stage |
|---|---|---|
| RAG | 共享生产检索底座 | 4 |
| Chunking | 原典章节 + metadata contract | 4 |
| Embedding | BGE / batch ingestion / lifecycle | 4 |
| Vector Store | PostgreSQL + pgvector | 4 |
| Retriever | dense + sparse + metadata filter | 4 |
| Reranker | benchmark-driven enable/disable | 4 |
| Retrieval Evaluation | golden set / Recall@5 / MRR@10 | 4,10 |
| Grounded Generation | citation / evidence degradation | 4 |
| Tool Calling | precondition / budget / business contract | 3 |
| Agent Loop | mature runtime instead of rebuilding | 3 |
| Runtime Guard | business safety routing | 11 |
| LangGraph | real workflow design | 6,7 |
| Reducer | fan-out / fan-in | 7 |
| Router | rule + structured LLM + eval | 7 |
| Persistence | PostgreSQL checkpointer | 8 |
| Memory | selector / domain isolation / lifecycle | 5,8 |
| HITL | UI / API interrupt-resume mapping | 6,11 |
| Idempotency awareness | workflow / Redis idempotency | 6,12 |
| Error Handling | provider boundary / degradation | 1,12 |
| Prompt Engineering | protocol separation / fact boundary | 1,3 |
| Multi-Agent | limited two-agent orchestration | 7 |

---

# C. 尚未系统学习，需要首次使用前教学

## Stage 0

- Product Charter / Product Modeling
- formal Agent Contract
- Domain Model design
- ADR
- scope management
- current vs target architecture
- interview-level architecture narrative

Stage 0 已完成本项目所需第一轮学习与冻结。

## Stage 1

- Pydantic v2 systematic use
- Pydantic generic
- pydantic-settings
- Structured Output systematic understanding
- with_structured_output()
- LLMClient abstraction
- provider abstraction
- retry design
- uv / pyproject / lockfile workflow
- Ruff
- fake model testing

## Stage 2

- Adapter Pattern systematic understanding
- third-party library evaluation
- deterministic vs probabilistic boundary deepening
- lunar_python mapping
- fixture-based deterministic testing

## Stage 3

- Agent Contract implementation
- Tool preconditions
- model/tool call budget
- structured NeedUserInput contract

## Stage 4

- PostgreSQL basics for Agent systems
- pgvector
- BM25 / Sparse Retrieval
- Chinese tokenization in sparse retrieval
- Hybrid Retrieval
- Reciprocal Rank Fusion
- Metadata Filtering
- Citation Data Contract
- benchmark design
- Recall@K / MRR systematic understanding
- latency-quality trade-off

## Stage 5

- Context Engineering systematic method
- Structured Information Extraction
- State Merge
- Task Object vs Chat History
- Context Selection
- multi-turn task state

## Stage 6

- ichingpy evaluation
- Liuyao deterministic Tool adapter
- randomness / reproducibility boundary
- workflow idempotency
- Graph integration testing

## Stage 7

- Intent Classification engineering
- rule + LLM two-layer routing
- router confidence / fallback
- Router Dataset / Accuracy Eval
- fan-out / fan-in
- concurrent Agent orchestration
- Synthesizer Pattern
- Multi-Agent cost control

## Stage 8

- PostgreSQL domain modeling
- SQLAlchemy 2.x async
- Repository Pattern boundary
- transaction / session basics
- PostgreSQL LangGraph Checkpointer
- cross-process durable execution
- Memory Selector
- Memory domain isolation
- long-term memory lifecycle

## Stage 9

- MCP principles
- MCP Server
- MCP Client
- schema interoperability
- Streamable HTTP
- MCP vs internal Tool
- MCP vs REST
- MCP access boundary

## Stage 10

- Agent Evaluation
- end-to-end eval
- evaluation dataset design
- failure taxonomy
- Observability
- Trace Model
- AgentRun / RunStep
- token / cost / latency instrumentation
- p50 / p95
- baseline / regression
- LangSmith boundary

## Stage 11

- FastAPI
- API Contract Design
- SSE
- Streaming
- Agent event protocol
- frontend / backend state synchronization
- HITL UI mapping
- Safety Classification
- Safety Routing
- rule + LLM classifier
- API integration testing

## Stage 12

- Docker
- Docker Compose
- PostgreSQL / pgvector containerization
- Redis
- Redis asyncio
- Rate Limiting
- Idempotency Key
- TTL Cache
- Health / Readiness
- Nginx / HTTPS deployment relation
- GitHub Actions
- CI/CD
- Production Smoke Test
- External Dependency Degradation
- Secret Management
- Production Reliability
