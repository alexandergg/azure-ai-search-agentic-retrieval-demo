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
git clone https://github.com/<your-org>/demo-foundry-iq.git
cd demo-foundry-iq
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
python scripts/03_create_knowledge.py
```

Creates an Azure AI Search index with Content Understanding chunking, registers it as a Knowledge Source, and wraps it in a Knowledge Base for agentic retrieval.

### 7. Chat with the agent

```bash
python scripts/04_create_agent.py
```

Creates a Foundry Agent connected to the knowledge base via MCP and starts an interactive chat session. Ask questions about your documents!

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

The Foundry Agent connects to the Knowledge Base via [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). MCP provides a standardized interface that allows the agent to:

- Discover available knowledge bases and their capabilities
- Issue structured retrieval queries
- Receive typed responses with metadata and citations

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
    ├── 04_create_agent.py     # Creates agent and starts chat
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

To delete all Azure resources created by this demo:

```bash
az group delete --name rg-demo-foundry-iq --yes --no-wait
```

> **Note:** This permanently deletes all resources in the resource group including any data stored in Blob Storage and the AI Search index.

## Resources

- [Azure AI Foundry IQ Documentation](https://learn.microsoft.com/azure/ai-services/agents/)
- [Agentic Retrieval Overview](https://learn.microsoft.com/azure/ai-services/agents/concepts/agentic-retrieval)
- [Azure Content Understanding](https://learn.microsoft.com/azure/ai-services/content-understanding/)
- [Azure AI Search Documentation](https://learn.microsoft.com/azure/search/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Azure OpenAI Service](https://learn.microsoft.com/azure/ai-services/openai/)
