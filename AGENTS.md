# AGENTS.md

This file describes the AI agents used in this project, their capabilities, tools, and how they interact with the Azure AI Search agentic retrieval pipeline.

## Agent: `demofiq-knowledge-agent`

**Purpose:** Answer user questions by retrieving and synthesizing information from indexed documents using Azure AI Search agentic retrieval.

### Model

- **Chat model:** `gpt-4o` (deployed on Azure AI Services, GlobalStandard SKU)
- **Query planning model:** `gpt-4o-mini` (used internally by the Knowledge Base for query decomposition)
- **Embedding model:** `text-embedding-3-large` (3072 dimensions, used during indexing and retrieval)

### Instructions

```
You are a helpful assistant that must use the knowledge base to answer all
questions from user. You must never answer from your own knowledge under any
circumstances. Every answer must always provide annotations using the MCP
knowledge base tool and render them as: 【message_idx:search_idx†source_name】
If you cannot find the answer in the provided knowledge base you must respond
with "I don't know".
```

### Tools

| Tool | Protocol | Description |
|------|----------|-------------|
| `knowledge_base_retrieve` | MCP (Model Context Protocol) | Invokes the Azure AI Search Knowledge Base agentic retrieval pipeline. The agent sends a natural language query; the KB decomposes it into subqueries, executes parallel hybrid searches, reranks results, and returns cited passages. |

### MCP Connection

- **Type:** `RemoteTool` project connection with `ProjectManagedIdentity` auth
- **Endpoint:** `https://{search-service}.search.windows.net/knowledgebases/{kb-name}/mcp?api-version=2025-11-01-preview`
- **Auth flow:** The Foundry project's managed identity acquires a token for `https://search.azure.com/` and forwards it to the MCP endpoint automatically.

### Retrieval Pipeline (what happens when the agent calls `knowledge_base_retrieve`)

```
User Query
    │
    ▼
┌──────────────────────┐
│  LLM Query Planning  │  gpt-4o-mini decomposes the query
│  (modelQueryPlanning) │  into targeted subqueries
└──────────┬───────────┘
           │
    ┌──────┼──────┐
    ▼      ▼      ▼
┌────────────────────┐
│  Parallel Hybrid   │  Each subquery runs:
│  Search per source │  BM25 + vector + semantic reranking
│  (searchIndex)     │
└────────┬───────────┘
         │
         ▼
┌──────────────────────┐
│  Agentic Reasoning   │  Cross-source dedup, relevance scoring,
│  (agenticReasoning)  │  document selection
└──────────┬───────────┘
         │
         ▼
┌──────────────────────┐
│  Answer Synthesis    │  (optional) LLM generates a synthesized
│  (modelAnswerSynth.) │  answer with inline citations
└──────────────────────┘
```

### Retrieval Journey Insights

The agent script (`04_create_agent.py`) displays a **Retrieval Journey** panel after each response, showing:

- 🧠 **Query Planning** — input/output tokens, elapsed time, decomposed subqueries
- 🔍 **Search Execution** — each subquery text, document count, source name, timing
- ⚡ **Agentic Reasoning** — reasoning tokens, effort level (minimal/low/medium/high)
- 📝 **Answer Synthesis** — input/output tokens, elapsed time
- 📚 **References** — document keys, types, reranker scores
- **Token Usage** — per-phase breakdown table

Run with `--verbose` / `-v` to see raw MCP tool call data.

### Agent Lifecycle

1. **Created** by `04_create_agent.py` using `AIProjectClient.agents.create_version()`
2. **Conversations** are created via the OpenAI Responses API (`conversations.create()`)
3. **Streaming** responses are delivered via `stream=True` with live Markdown rendering
4. **Deleted** automatically on script exit (`agents.delete_version()`)

### Knowledge Base Configuration

| Setting | Value | Purpose |
|---------|-------|---------|
| Output mode | `EXTRACTIVE_DATA` | Agent gets verbatim content chunks for its own reasoning |
| Reasoning effort | `minimal` (default) | Bypasses LLM query planning for faster responses |
| Reasoning effort | `low` (retrieval journey) | Overridden in direct KB calls to get query planning activity |
| Max output size | Default | ~200 chunks max per retrieval |

### Required RBAC Roles

| Principal | Role | Scope |
|-----------|------|-------|
| Foundry project MI | Search Index Data Reader | AI Search service |
| Foundry project MI | Search Service Contributor | AI Search service |
| User / Service Principal | Azure AI User | AI Services account |
| AI Search MI | Cognitive Services User | AI Services account |
