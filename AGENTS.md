# AGENTS.md

This file describes the AI agents used in this project, their capabilities, tools, and how they interact with the Azure AI Search agentic retrieval pipeline.

## Multi-Agent Architecture

The project implements two agent patterns:

1. **Web App (app/backend/agents/)** -- Multi-agent orchestrator using Microsoft Agent Framework SDK with streaming SSE responses, conversation memory, retrieval journey visualization, and a ChatGPT-style React frontend
2. **CLI (scripts/04_create_agent.py)** -- Single agent with MCP-based agentic retrieval

## Web App Agents

### Orchestrator Agent

**Purpose:** Route user queries to the appropriate specialist agent based on intent classification.

- **Model:** gpt-4o (configurable via AGENT_MODEL env var)
- **No Knowledge Base** -- purely classification-based routing
- **Outputs:** One of ai-research, space-science, standards, cloud-sustainability

### Specialist Agents

Each specialist uses AzureAISearchContextProvider with the shared Knowledge Base (demo-knowledge-base) in agentic retrieval mode.

| Agent | File | Knowledge Source | Domain |
|-------|------|-----------------|--------|
| AI Research | ai_research_agent.py | ks-ai-research | Transformer papers, BERT, GPT-4 |
| Space Science | space_science_agent.py | ks-space-science | NASA publications, earth observation |
| Standards | standards_agent.py | ks-standards | NIST cybersecurity & AI frameworks |
| Cloud & Sustainability | cloud_sustainability_agent.py | ks-cloud-sustainability | Azure whitepapers, sustainability |

### SDK Pattern

```python
from agent_framework import Agent, Message
from agent_framework.azure import AzureOpenAIChatClient, AzureAISearchContextProvider
from agent_framework.session import AgentSession, InMemoryHistoryProvider

async with (
    AzureOpenAIChatClient(endpoint=..., model=..., credential=...) as client,
    AzureAISearchContextProvider(
        endpoint=..., knowledge_base_name='demo-knowledge-base',
        credential=..., mode='agentic', knowledge_base_output_mode='answer_synthesis',
    ) as kb_context,
):
    agent = Agent(chat_client=client, context_provider=kb_context, instructions=...)

    # Non-streaming
    response = await agent.run([Message(role="user", text=query)], session=session)

    # Streaming (SSE)
    stream = await agent.run([Message(role="user", text=query)], session=session, stream=True)
    async for update in stream:
        yield update.text  # text deltas
    final = await stream.get_final_response()  # citations, context
```

### Conversation Memory

Sessions use `AgentSession` + `InMemoryHistoryProvider` for automatic multi-turn context:

```python
history_provider = InMemoryHistoryProvider()
session = AgentSession(session_id=session_id, history_provider=history_provider)
# Agent automatically stores/retrieves conversation history per session
```

Sessions are stored in-memory (`_sessions: dict[str, AgentSession]` in orchestrator.py) and reset on server restart.

### FastAPI Integration

The orchestrator exposes two main functions:

- **`run_single_query(message, session_id)`** -- Non-streaming. Returns `(route, response_text, sources, suggested_questions, retrieval_journey)` for the `POST /chat` endpoint.
- **`run_single_query_stream(message, session_id)`** -- Streaming async generator. Yields SSE events (`route`, `delta`, `metadata`, `done`) for the `POST /chat/stream` endpoint.

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /chat | Non-streaming chat (JSON request/response) |
| POST | /chat/stream | Streaming chat via Server-Sent Events |
| DELETE | /chat/{session_id} | Clear conversation session |
| GET | /health | Health check |
| GET | /agents | List available agents |

### Streaming Protocol (SSE)

The `/chat/stream` endpoint emits events in this order:

```
event: route
data: {"route": "ai-research"}

event: delta
data: {"text": "The transformer architecture..."}
...

event: metadata
data: {"sources": [...], "suggested_questions": [...], "retrieval_journey": {...}, "clean_text": "..."}

event: done
data: {}
```

### Retrieval Journey

Each response includes real telemetry from the KB retrieve pipeline (fetched in parallel via `asyncio.create_task`):

```
User Query --> LLM Query Planning (gpt-4o-mini) --> Parallel Hybrid Search per source
    --> Agentic Reasoning --> Answer Synthesis --> Response with citations
```

Activity data includes:
- **modelQueryPlanning**: inputTokens, outputTokens, elapsedMs, generated subqueries
- **searchIndex**: per-source search results, knowledgeSourceName, count, elapsedMs
- **agenticReasoning**: reasoningTokens, retrievalReasoningEffort, elapsedMs
- **modelAnswerSynthesis**: inputTokens, outputTokens, elapsedMs

### Follow-Up Questions

Agent instructions include a suffix requesting `<<FOLLOW_UP>>question<</FOLLOW_UP>>` markers. These are parsed via regex in `_parse_follow_ups()` and sent to the frontend as `suggested_questions`. During streaming, markers are cleaned from the displayed text when the metadata event fires.

## CLI Agent: demofiq-knowledge-agent

**Purpose:** Single agent with direct MCP connection to the Knowledge Base for interactive CLI chat.

### Model

- **Chat model:** gpt-4o (deployed on Azure AI Services, GlobalStandard SKU)
- **Query planning model:** gpt-4o-mini (used internally by the Knowledge Base)
- **Embedding model:** text-embedding-3-large (3072 dimensions)

### MCP Connection

- **Type:** RemoteTool project connection with ProjectManagedIdentity auth
- **Tool:** knowledge_base_retrieve -- invokes the Azure AI Search agentic retrieval pipeline

### Retrieval Pipeline

`
User Query --> LLM Query Planning (gpt-4o-mini) --> Parallel Hybrid Search per source
    --> Agentic Reasoning --> Answer Synthesis --> Response with citations
`

## Knowledge Base Configuration

| Setting | Value |
|---------|-------|
| Knowledge Base | demo-knowledge-base |
| Knowledge Sources | 4 (ks-ai-research, ks-space-science, ks-standards, ks-cloud-sustainability) |
| Output mode | answer_synthesis (web app) / EXTRACTIVE_DATA (CLI) |

## Required RBAC Roles

| Principal | Role | Scope |
|-----------|------|-------|
| Foundry project MI | Search Index Data Reader | AI Search service |
| Foundry project MI | Search Service Contributor | AI Search service |
| User / Service Principal | Azure AI User | AI Services account |
| AI Search MI | Cognitive Services User | AI Services account |

## Frontend Architecture

The web app uses a **ChatGPT-style conversational UI** built with React 18 + TypeScript + Vite.

### Component Hierarchy

```
App.tsx (state management + streaming logic)
  └── ChatLayout.tsx (centered layout wrapper)
        ├── WelcomeScreen.tsx (empty state with domain cards)
        └── ChatMessage.tsx (per-message bubble)
              ├── MarkdownRenderer.tsx (rich text + citation [N] parsing)
              ├── CitationPanel.tsx (expandable source list)
              ├── RetrievalJourney.tsx (KB pipeline timeline)
              └── SuggestedQuestions.tsx (follow-up pill buttons)
```

### Key Design Decisions

- **Light theme only** -- Clean, centered interface inspired by ChatGPT/Gemini
- **Streaming-first** -- Uses SSE (`ReadableStream` parsing) for progressive text rendering
- **Per-message session** -- UUID session ID managed in frontend, passed to backend for conversation continuity
- **Modular components** -- Each concern (citations, journey, markdown) is a separate component
- **Vite proxy** -- `/chat` prefix proxied to `localhost:8000` during development
- **Build output** -- Frontend compiles to `app/backend/static/` served by FastAPI `StaticFiles`
