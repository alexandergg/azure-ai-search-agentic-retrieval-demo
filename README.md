# Azure AI Foundry IQ Demo

A complete demo showcasing **Azure AI Foundry IQ** capabilities: Agentic Retrieval, Knowledge Bases, Knowledge Sources, and document ingestion with semantic chunking via Azure Content Understanding.

## Overview

This demo implements an end-to-end Retrieval-Augmented Generation (RAG) pipeline using Azure AI Foundry IQ:

1. **Ingest** PDF documents into Azure Blob Storage
2. **Chunk** documents using Azure Content Understanding (layout analysis → Markdown → semantic chunking)
3. **Index** chunks in Azure AI Search with vector embeddings
4. **Create** a Knowledge Source and Knowledge Base for agentic retrieval
5. **Deploy** a Foundry Agent connected to the knowledge base via Model Context Protocol (MCP)
6. **Chat** interactively with the agent, which decomposes complex queries into parallel subqueries for high-quality answers with citations

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────────────┐
│              │     │                  │     │  Azure Content           │
│  PDF Docs    ├────►│  Blob Storage    ├────►│  Understanding           │
│  (data/)     │     │  (documents)     │     │  (Layout → MD → Chunks)  │
└──────────────┘     └──────────────────┘     └────────────┬─────────────┘
                                                           │
                                                           ▼
┌──────────────┐     ┌──────────────────┐     ┌──────────────────────────┐
│              │     │  Knowledge Base  │     │  Azure AI Search         │
│  Foundry     │◄────┤  (Agentic        │◄────┤  (Vector Index +         │
│  Agent       │ MCP │   Retrieval)     │     │   Semantic Reranking)    │
└──────┬───────┘     └──────────────────┘     └──────────────────────────┘
       │
       ▼
┌──────────────┐
│  Interactive │
│  CLI Chat    │
└──────────────┘
```

## Prerequisites

- **Azure subscription** with **Contributor** and **User Access Administrator** roles
- **Azure CLI** (`az`) installed and authenticated (`az login`)
- **Python 3.10+**
- An Azure region that supports agentic retrieval (e.g., `eastus2`, `westeurope`, `swedencentral`, `australiaeast`)

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/alexandergg/azure-ai-search-agentic-retrieval-demo.git
cd azure-ai-search-agentic-retrieval-demo
```

### 2. Add PDF documents

Place your PDF files in the `data/sample-docs/` directory. These will be ingested, chunked, and indexed.

```
data/
└── sample-docs/
    ├── document1.pdf
    ├── document2.pdf
    └── ...
```

### 3. Deploy Azure infrastructure

```powershell
.\scripts\01_deploy_infra.ps1
```

This provisions all required Azure resources (AI Search, Storage, OpenAI, AI Services, Foundry project) and generates a `.env` file with the connection details.

### 4. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 5. Upload documents to Blob Storage

```bash
python scripts/02_upload_documents.py
```

Uploads all PDFs from `data/sample-docs/` to the Azure Blob Storage container.

### 6. Create Knowledge Source and Knowledge Base

```bash
# Default: standard mode (Content Understanding with OCR, layout analysis)
python scripts/03_create_knowledge.py

# For faster testing: minimal mode (built-in text extraction)
python scripts/03_create_knowledge.py --mode minimal

# With verbose SDK logging:
python scripts/03_create_knowledge.py -v
```

Creates an Azure AI Search index with Content Understanding chunking, registers it as a Knowledge Source, and wraps it in a Knowledge Base with agentic retrieval features (LLM query planning, answer synthesis, retrieval instructions).

### 7. Chat with the agent

```bash
python scripts/04_create_agent.py

# With verbose MCP output (raw tool calls):
python scripts/04_create_agent.py -v
```

Creates a RemoteTool project connection for secure MCP authentication, then creates a Foundry Agent that uses `knowledge_base_retrieve` via MCP. Starts an interactive chat session with:

- **Streaming responses** — answers are streamed token-by-token with live Markdown rendering
- **Retrieval journey panel** — after each answer, shows query decomposition, subqueries, timing, token usage, and cited references
- **Retry logic** — automatic exponential backoff for rate limit (429) errors

### 8. Cleanup (optional)

```bash
# Clean up AI Search resources, blobs, and MCP connections
python scripts/05_cleanup.py

# Or delete the entire resource group
az group delete --name rg-demo-foundry-iq --yes --no-wait
```

## How It Works

### Document Ingestion

Azure Content Understanding processes each PDF through a 3-phase pipeline:

1. **Layout Analysis** — OCR and structural detection identify text, tables, headers, figures, and page boundaries
2. **Markdown Conversion** — Detected elements are converted to Markdown preserving tables, headers, and figure references
3. **Semantic Chunking** — Content is split into semantically coherent chunks that respect section boundaries, keep tables intact, and allow cross-page content to stay together. Overlapping context windows ensure no information is lost at chunk boundaries.

### Agentic Retrieval

Unlike simple vector search, agentic retrieval uses an LLM-powered query planner:

1. **Query Decomposition** — The LLM analyzes the user's question and decomposes complex queries into multiple targeted subqueries
2. **Parallel Subquery Execution** — Each subquery runs independently against the search index using hybrid search (keyword + vector + semantic reranking)
3. **Result Aggregation** — Results from all subqueries are merged, deduplicated, and reranked for relevance
4. **Unified Response** — The agent synthesizes a comprehensive answer with inline citations pointing back to source documents

### MCP Integration

The Foundry Agent connects to the Knowledge Base via [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). The integration uses:

1. **RemoteTool Project Connection** — A connection on the AI Foundry project with `ProjectManagedIdentity` auth type. This tells the Agent Service to acquire tokens for `https://search.azure.com/` using the project's managed identity.
2. **MCP Tool** — The agent is configured with an MCP tool pointing to `{search_endpoint}/knowledgebases/{kb_name}/mcp?api-version=2025-11-01-preview`
3. **`knowledge_base_retrieve`** — The allowed tool that the agent calls to perform agentic retrieval, which internally does LLM-powered query planning, parallel subquery execution, and semantic reranking.

This architecture ensures secure, token-based authentication without exposing API keys — the project MI handles all auth transparently.

## Project Structure

```
demo-foundry-iq/
├── .env.example              # Template for environment variables
├── .gitignore
├── requirements.txt           # Python dependencies
├── README.md
├── data/
│   └── sample-docs/           # Place PDF documents here
├── docs/
│   └── architecture.md        # Detailed architecture documentation
├── infra/
│   └── modules/               # Bicep modules for Azure resources
└── scripts/
    ├── 01_deploy_infra.ps1    # Provisions Azure infrastructure
    ├── 02_upload_documents.py # Uploads PDFs to Blob Storage
    ├── 03_create_knowledge.py # Creates knowledge source + base
    ├── 04_create_agent.py     # Creates agent with MCP tool and starts chat
    ├── 05_cleanup.py          # Cleans up all resources
    └── utils/
        ├── __init__.py
        └── config.py          # Shared configuration loader
```

## Configuration

All configuration is managed through a `.env` file. Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search service endpoint |
| `PROJECT_ENDPOINT` | Azure AI Foundry project API endpoint |
| `PROJECT_RESOURCE_ID` | Full ARM resource ID for the Foundry project |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI service endpoint |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Embedding model deployment name (default: `text-embedding-3-large`) |
| `AZURE_OPENAI_EMBEDDING_MODEL` | Embedding model name (default: `text-embedding-3-large`) |
| `AZURE_OPENAI_GPT_DEPLOYMENT` | GPT model deployment name (default: `gpt-4o`) |
| `AZURE_OPENAI_GPT_MINI_DEPLOYMENT` | GPT mini model deployment name (default: `gpt-4o-mini`) |
| `AZURE_STORAGE_CONNECTION_STRING` | Blob Storage connection string |
| `AZURE_STORAGE_CONTAINER_NAME` | Blob container name (default: `documents`) |
| `AZURE_AI_SERVICES_ENDPOINT` | Azure AI Services endpoint for Content Understanding |
| `AGENT_MODEL` | Model used by the Foundry Agent (default: `gpt-4o`) |
| `KNOWLEDGE_SOURCE_NAME` | Name for the knowledge source (default: `demo-blob-ks`) |
| `KNOWLEDGE_BASE_NAME` | Name for the knowledge base (default: `demo-knowledge-base`) |

## Cleanup

To clean up AI Search resources (KBs, KSs, indexers, indexes), blobs, and MCP connections:

```bash
python scripts/05_cleanup.py
```

To delete all Azure resources entirely:

```bash
az group delete --name rg-demo-foundry-iq --yes --no-wait
```

> **Note:** This permanently deletes all resources in the resource group.

## Resources

- [Azure AI Foundry IQ Documentation](https://learn.microsoft.com/azure/ai-services/agents/)
- [Agentic Retrieval Overview](https://learn.microsoft.com/azure/ai-services/agents/concepts/agentic-retrieval)
- [Azure Content Understanding](https://learn.microsoft.com/azure/ai-services/content-understanding/)
- [Azure AI Search Documentation](https://learn.microsoft.com/azure/search/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Azure OpenAI Service](https://learn.microsoft.com/azure/ai-services/openai/)
