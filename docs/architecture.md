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
| Web Backend | FastAPI | Multi-agent orchestrator with REST and SSE streaming endpoints |
| Web Frontend | React 18 + Vite | ChatGPT-style conversational UI with streaming, citations, and retrieval journey |

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

## Web Application Architecture

The web app implements a multi-agent orchestrator with a ChatGPT-style frontend.

### Multi-Agent Flow

```
 ┌──────────────────────────────────────────────────────────────────┐
 │                     WEB APPLICATION                             │
 │                                                                 │
 │  ┌───────────┐   SSE Stream   ┌──────────────────────────────┐  │
 │  │  React    │◄──────────────►│  FastAPI Backend              │  │
 │  │  Frontend │  POST /chat/   │  ┌────────────────────────┐  │  │
 │  │           │    stream      │  │ Orchestrator Agent      │  │  │
 │  │ • Stream  │                │  │ (intent classification) │  │  │
 │  │ • Cite    │                │  └──────────┬─────────────┘  │  │
 │  │ • Journey │                │       routes to specialist    │  │
 │  │ • Follow  │                │  ┌──────────▼─────────────┐  │  │
 │  │   -ups    │                │  │ Specialist Agent        │  │  │
 │  └───────────┘                │  │ (AI Research | Space    │  │  │
 │                               │  │  Science | Standards |  │  │  │
 │                               │  │  Cloud & Sustainability)│  │  │
 │                               │  └──────────┬─────────────┘  │  │
 │                               │             │ KB context      │  │
 │                               │  ┌──────────▼─────────────┐  │  │
 │                               │  │ AzureAISearch           │  │  │
 │                               │  │ ContextProvider         │  │  │
 │                               │  │ (agentic retrieval)     │  │  │
 │                               │  └────────────────────────┘  │  │
 │                               └──────────────────────────────┘  │
 └──────────────────────────────────────────────────────────────────┘
```

### Streaming Protocol (SSE)

The `POST /chat/stream` endpoint uses Server-Sent Events for progressive rendering:

```
event: route       →  Agent classification result (e.g., "ai-research")
event: delta       →  Text chunk from the LLM (streamed progressively)
event: metadata    →  Sources, citations, retrieval journey, follow-up questions
event: done        →  End of stream
event: error       →  Error details (if any)
```

The frontend parses these events via a `ReadableStream` and renders text as it arrives, providing a real-time typing effect.

### Retrieval Journey Telemetry

In parallel with each agent response, the backend makes a direct REST call to the KB retrieve API (`/knowledgebases/{kb_name}/retrieve`) with `includeActivity: True`. This returns real pipeline telemetry:

| Stage | Data Captured |
|-------|---------------|
| **Query Planning** | Generated subqueries, input/output tokens, elapsed time |
| **Search Execution** | Per-source search results, knowledge source name, result count, elapsed time |
| **Agentic Reasoning** | Reasoning tokens, retrieval effort level, elapsed time |
| **Answer Synthesis** | Input/output tokens, elapsed time |

This data is rendered in the frontend as a collapsible timeline per message with a token summary table.

### Conversation Memory

The backend uses the Agent Framework's built-in session management:

- `AgentSession` + `InMemoryHistoryProvider` automatically store and retrieve conversation history
- Sessions are keyed by a UUID generated in the frontend
- Multi-turn context is maintained across messages within a session
- Sessions are in-memory only (reset on server restart, acceptable for demo)

### Follow-Up Questions

Agent instructions include a suffix requesting follow-up suggestions in `<<FOLLOW_UP>>...<</FOLLOW_UP>>` markers. These are:

1. Parsed via regex from the response text
2. Stripped from the displayed text
3. Sent to the frontend as `suggested_questions`
4. Rendered as clickable pill buttons below each message

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

## Infrastructure as Code

All Azure resources are provisioned via [Bicep](https://learn.microsoft.com/azure/azure-resource-manager/bicep/overview) templates in the `infra/` directory, orchestrated by `main.bicep`.

### Bicep Modules

| Module | File | Resources Created |
|--------|------|-------------------|
| **Storage** | `modules/storage.bicep` | Blob Storage account for document containers |
| **Key Vault** | `modules/keyvault.bicep` | Azure Key Vault for secrets management |
| **AI Search** | `modules/ai-search.bicep` | Azure AI Search service with semantic reranking |
| **AI Services** | `modules/ai-services.bicep` | Azure AI Services (Content Understanding, embeddings) |
| **OpenAI** | `modules/openai.bicep` | Model deployments (gpt-4o, gpt-4o-mini, text-embedding-3-large) |
| **AI Foundry** | `modules/ai-foundry.bicep` | AI Foundry project for Knowledge Bases and agents |
| **Container Registry** | `modules/container-registry.bicep` | ACR for Docker image hosting |
| **Container Apps** | `modules/container-apps.bicep` | Container Apps environment and app for backend hosting |

### Deployment Methods

- **`azd up`** — Provisions infrastructure and deploys the application in one command (recommended)
- **`scripts/01_deploy_infra.ps1`** — PowerShell script for infrastructure-only deployment via Bicep
- **`azd provision`** / **`azd deploy`** — Separate infrastructure and application deployment steps

The `azure.yaml` configuration defines the backend as a Python Container App service with a prebuild hook that compiles the React frontend before Docker image creation.

## Development Environment

### Dev Container

The `.devcontainer/devcontainer.json` provides a fully configured development environment:

| Feature | Configuration |
|---------|--------------|
| **Base Image** | `mcr.microsoft.com/devcontainers/python:1-3.13` |
| **Node.js** | v22 (for frontend build) |
| **Azure CLI** | Latest (for resource management) |
| **Azure Developer CLI** | Latest (for `azd` deployments) |
| **Forwarded Ports** | 8000 (backend), 5173 (Vite dev server) |

**VS Code Extensions** installed automatically:
- Python + Pylance (Python development)
- Ruff (linting and formatting)
- Azure Dev + Bicep (infrastructure)
- ESLint (frontend linting)

**Post-create setup** installs all dependencies:
```bash
pip install -r requirements.txt && pip install -r app/backend/requirements.txt && cd app/frontend && npm install
```
