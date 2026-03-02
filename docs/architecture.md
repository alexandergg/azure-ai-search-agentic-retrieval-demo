# Architecture

This document provides a detailed technical overview of the Azure AI Foundry IQ demo architecture, covering all components, data flows, chunking strategies, and security considerations.

## Component Overview

| Component | Azure Service | Role |
|---|---|---|
| Document Storage | Azure Blob Storage | Stores raw PDF documents in a `documents` container |
| Document Processing | Azure AI Services (Content Understanding) | Layout analysis, Markdown conversion, and semantic chunking of PDFs |
| Search Index | Azure AI Search | Stores chunked document vectors and supports hybrid search with semantic reranking |
| Embeddings | Azure OpenAI (`text-embedding-3-large`) | Generates vector embeddings for document chunks and queries |
| Query Planning | Azure OpenAI (`gpt-4o-mini`) | Decomposes complex user queries into targeted subqueries |
| Knowledge Source | Azure AI Foundry IQ | Wraps the AI Search index with Content Understanding chunking configuration |
| Knowledge Base | Azure AI Foundry IQ | Groups knowledge sources and enables agentic retrieval |
| Agent | Azure AI Foundry Agent | LLM-powered agent connected to the knowledge base via MCP |
| Chat Model | Azure OpenAI (`gpt-4o`) | Powers the Foundry Agent's conversational responses |

## Data Flow

The end-to-end data flow from PDF ingestion to agent response follows these stages:

```
 ┌─────────────────────────────────────────────────────────────────┐
 │                     INGESTION PIPELINE                         │
 │                                                                │
 │  ┌─────────┐    ┌───────────┐    ┌──────────────────────────┐  │
 │  │  PDFs   ├───►│   Blob    ├───►│  Content Understanding   │  │
 │  │ (local) │    │  Storage  │    │  ┌────────┐ ┌─────────┐  │  │
 │  └─────────┘    └───────────┘    │  │ Layout │►│  MD     │  │  │
 │                                  │  │Analysis│ │ Convert │  │  │
 │                                  │  └────────┘ └────┬────┘  │  │
 │                                  │            ┌─────▼─────┐ │  │
 │                                  │            │ Semantic   │ │  │
 │                                  │            │ Chunking   │ │  │
 │                                  │            └─────┬─────┘ │  │
 │                                  └──────────────────┼───────┘  │
 │                                                     │          │
 │                                  ┌──────────────────▼───────┐  │
 │                                  │  Azure AI Search Index   │  │
 │                                  │  (vectors + metadata)    │  │
 │                                  └──────────────────────────┘  │
 └─────────────────────────────────────────────────────────────────┘

 ┌─────────────────────────────────────────────────────────────────┐
 │                     RETRIEVAL PIPELINE                         │
 │                                                                │
 │  ┌──────────┐    ┌───────────┐    ┌─────────────────────────┐  │
 │  │  User    ├───►│  Foundry  ├───►│   Knowledge Base        │  │
 │  │  Query   │    │  Agent    │MCP │   (Agentic Retrieval)   │  │
 │  └──────────┘    └─────┬─────┘    │  ┌───────────────────┐  │  │
 │                        │          │  │ Query Planner     │  │  │
 │                        │          │  │  ┌─► Subquery 1   │  │  │
 │                        │          │  │  ├─► Subquery 2   │  │  │
 │                        │          │  │  └─► Subquery N   │  │  │
 │                        │          │  └────────┬──────────┘  │  │
 │                        │          │  ┌────────▼──────────┐  │  │
 │                        │          │  │ Semantic Reranker  │  │  │
 │                        │          │  └────────┬──────────┘  │  │
 │                        │          └───────────┼─────────────┘  │
 │                  ┌─────▼─────┐                │                │
 │                  │ Response  │◄───────────────┘                │
 │                  │ (w/       │  ranked results + citations     │
 │                  │ citations)│                                  │
 │                  └───────────┘                                  │
 └─────────────────────────────────────────────────────────────────┘
```

### Step-by-Step

1. **Upload** — PDFs are uploaded from `data/sample-docs/` to Azure Blob Storage (`documents` container)
2. **Index Creation** — An Azure AI Search index is created with a Content Understanding–based skillset attached as the chunking strategy
3. **Indexer Execution** — The AI Search indexer processes each blob, invoking Content Understanding to extract and chunk content
4. **Embedding** — Each chunk is embedded using `text-embedding-3-large` (3072 dimensions) and stored in the vector index
5. **Knowledge Source** — A Knowledge Source is registered in Azure AI Foundry, pointing to the AI Search index and Content Understanding chunking configuration
6. **Knowledge Base** — A Knowledge Base wraps the Knowledge Source, enabling agentic retrieval capabilities
7. **Agent Creation** — A Foundry Agent is created with the Knowledge Base connected via MCP as a tool
8. **Query** — The user asks a question via the interactive CLI
9. **Agentic Retrieval** — The agent invokes the knowledge base, which decomposes the query, runs parallel searches, reranks results, and returns cited passages
10. **Response** — The agent synthesizes a final answer with inline citations

## Chunking Strategy

Azure Content Understanding processes documents through a sophisticated 3-phase pipeline that produces high-quality, semantically coherent chunks.

### Phase 1: Layout Analysis

Content Understanding applies OCR and structural detection to each page:

- **Text extraction** — High-accuracy OCR for printed and handwritten text
- **Table detection** — Identifies table boundaries, rows, columns, headers, and merged cells
- **Header/footer detection** — Separates page headers, footers, and page numbers from body content
- **Figure detection** — Identifies charts, diagrams, and images with associated captions
- **Reading order** — Determines the logical reading order across multi-column layouts

### Phase 2: Markdown Conversion

Detected elements are converted into clean Markdown:

- **Tables** → Markdown table syntax with proper alignment
- **Headers** → Markdown heading levels (`#`, `##`, `###`)
- **Lists** → Ordered and unordered Markdown lists
- **Figures** → Figure references with captions
- **Code blocks** → Fenced code blocks when detected

This intermediate Markdown representation preserves the document's logical structure while normalizing formatting differences across source documents.

### Phase 3: Semantic Chunking

The Markdown content is split into chunks using semantic boundaries:

| Feature | Description |
|---|---|
| **Section-aware splitting** | Chunks respect heading boundaries — a new `##` heading starts a new chunk |
| **Table preservation** | Tables are never split mid-row; small tables stay in a single chunk |
| **Cross-page continuity** | Content that spans page boundaries is kept together in one chunk |
| **Configurable chunk size** | Target chunk size is configurable (default: ~1024 tokens) |
| **Overlap windows** | Adjacent chunks share overlapping context (default: ~128 tokens) to prevent information loss at boundaries |
| **Metadata enrichment** | Each chunk carries metadata: source document, page range, section hierarchy, and content type |

This approach produces chunks that are semantically self-contained, making them significantly more effective for retrieval than naive fixed-size splitting.

## Agentic Retrieval Pipeline

Agentic retrieval is the core differentiator of Azure AI Foundry IQ. Unlike simple vector search, it uses an LLM-powered query planner to handle complex, multi-faceted questions.

### How Query Planning Works

```
User Query: "Compare the revenue growth trends in Q1 and Q2,
             and explain how the new product launch affected margins"

                    ┌──────────────────────┐
                    │   Query Planner      │
                    │   (gpt-4o-mini)      │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
    ┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
    │ Subquery 1:     │ │ Subquery 2:  │ │ Subquery 3:      │
    │ "Q1 revenue     │ │ "Q2 revenue  │ │ "new product     │
    │  growth trends" │ │  growth"     │ │  launch margin   │
    └────────┬────────┘ └──────┬───────┘ │  impact"         │
             │                 │         └────────┬─────────┘
             ▼                 ▼                  ▼
    ┌─────────────────────────────────────────────────────┐
    │              Parallel Hybrid Search                 │
    │         (keyword + vector + semantic)               │
    └─────────────────────┬───────────────────────────────┘
                          ▼
    ┌─────────────────────────────────────────────────────┐
    │              Semantic Reranker                      │
    │    (cross-encoder model for precision reranking)    │
    └─────────────────────┬───────────────────────────────┘
                          ▼
    ┌─────────────────────────────────────────────────────┐
    │        Unified Response with Citations              │
    │   "Q1 showed 12% growth [doc1, p3] while Q2..."    │
    └─────────────────────────────────────────────────────┘
```

### Pipeline Stages

1. **Query Analysis** — The query planner LLM (`gpt-4o-mini`) analyzes the user's question to understand its complexity and information needs
2. **Decomposition** — Complex queries are broken into focused subqueries, each targeting a specific aspect of the question
3. **Parallel Execution** — All subqueries execute simultaneously against the AI Search index using hybrid search (BM25 keyword matching + vector similarity + semantic reranking)
4. **Semantic Reranking** — A cross-encoder reranking model scores each result for deep relevance to the original query, not just the subquery
5. **Deduplication & Merging** — Results from all subqueries are merged, duplicates are removed, and the top results are selected
6. **Citation Generation** — Each selected passage is annotated with source document, page number, and section for traceability
7. **Response Synthesis** — The agent's chat model (`gpt-4o`) synthesizes a comprehensive answer using the retrieved passages, embedding citations inline

### Benefits Over Simple RAG

| Feature | Simple RAG | Agentic Retrieval |
|---|---|---|
| Query handling | Single query, single search | Multi-query decomposition |
| Search strategy | Vector-only or keyword-only | Hybrid (keyword + vector + semantic) |
| Complex questions | Often misses relevant context | Captures multiple facets |
| Citation quality | Document-level at best | Page and section-level |
| Result ranking | Cosine similarity only | Cross-encoder semantic reranking |

## MCP Integration

The Foundry Agent connects to the Knowledge Base via [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), an open standard for connecting AI models to external tools and data sources.

### How It Works

1. **Tool Registration** — When the agent is created, the Knowledge Base is registered as an MCP tool. The agent receives a schema describing the tool's capabilities and input/output format.
2. **Tool Invocation** — During a conversation, when the agent determines it needs to retrieve information, it generates a structured MCP tool call with the query.
3. **Knowledge Base Execution** — The MCP layer routes the tool call to the Knowledge Base, which executes the agentic retrieval pipeline.
4. **Response Handling** — Retrieved passages and citations are returned to the agent through MCP's typed response format, which the agent uses to compose its answer.

### Advantages of MCP

- **Standardized interface** — Any MCP-compatible agent can connect to the knowledge base without custom integration code
- **Tool composition** — The agent can combine knowledge base retrieval with other MCP tools (e.g., code execution, web search)
- **Structured I/O** — Typed schemas ensure consistent data exchange between the agent and knowledge base

## Security

### Authentication & Authorization

| Mechanism | Usage |
|---|---|
| `DefaultAzureCredential` | All Python scripts authenticate using the Azure Identity SDK's credential chain (Azure CLI → Managed Identity → Environment Variables) |
| RBAC: **Contributor** | Required on the resource group to create and manage Azure resources |
| RBAC: **User Access Administrator** | Required to assign roles to the AI services principal |
| RBAC: **Storage Blob Data Contributor** | Assigned to the AI Search service for indexer access to Blob Storage |
| RBAC: **Cognitive Services OpenAI User** | Assigned for embedding and chat model access |
| RBAC: **Search Index Data Contributor** | Assigned for programmatic index management |

### Best Practices

- **No secrets in code** — All credentials are managed via `.env` (excluded from Git via `.gitignore`) or `DefaultAzureCredential`
- **Managed identities** — In production, replace connection strings with system-assigned managed identities for zero-secret deployments
- **Least privilege** — Each service principal is assigned only the RBAC roles it needs
- **Network isolation** — For production workloads, configure private endpoints and VNet integration on all services

## Cost Considerations

This demo provisions several Azure services. Below is a summary of cost drivers:

| Service | Pricing Model | Notes |
|---|---|---|
| **Azure AI Search** | Tier-based (Basic recommended for demo) | Basic tier: ~$75/month. Includes 15 GB storage, 3 replicas. Free tier available but limited. |
| **Azure OpenAI** | Per-token (input + output) | `gpt-4o`: ~$2.50/1M input tokens, ~$10/1M output tokens. `text-embedding-3-large`: ~$0.13/1M tokens. |
| **Content Understanding** | Per-page processing | Layout analysis pricing varies by feature set. Estimate ~$0.01–$0.05 per page. |
| **Agentic Retrieval** | Token-based billing | Query planner and reranker consume tokens. Costs scale with query complexity and frequency. |
| **Blob Storage** | Per-GB stored + operations | Negligible for small document sets (~$0.02/GB/month for hot tier). |
| **AI Services** | Per-transaction | Minimal cost for the Content Understanding API calls during indexing. |

### Cost Optimization Tips

- Use the **Free tier** of Azure AI Search for initial exploration (limited to 50 MB, no semantic reranker)
- Use `gpt-4o-mini` instead of `gpt-4o` for the agent model during development to reduce token costs
- Delete resources when not in use: `az group delete --name rg-demo-foundry-iq --yes`
- Monitor costs via the [Azure Cost Management](https://portal.azure.com/#view/Microsoft_Azure_CostManagement) dashboard
