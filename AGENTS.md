# AGENTS.md

This file describes the AI agents used in this project, their capabilities, tools, and how they interact with the Azure AI Search agentic retrieval pipeline.

## Multi-Agent Architecture

The project implements two agent patterns:

1. **Web App (app/backend/agents/)** -- Multi-agent orchestrator using Microsoft Agent Framework SDK
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

`python
from agent_framework import ChatAgent, ChatMessage, Role
from agent_framework.azure import AzureAIAgentClient, AzureAISearchContextProvider

async with (
    AzureAIAgentClient(project_endpoint=..., model_deployment_name=..., credential=...) as client,
    AzureAISearchContextProvider(
        endpoint=..., knowledge_base_name='demo-knowledge-base',
        credential=..., mode='agentic', knowledge_base_output_mode='answer_synthesis',
    ) as kb_context,
):
    agent = ChatAgent(chat_client=client, context_provider=kb_context, instructions=...)
    response = await agent.run(ChatMessage(role=Role.USER, text=query))
`

### FastAPI Integration

The 
un_single_query() function in orchestrator.py returns (route, response_text, sources) for the /chat endpoint.

## CLI Agent: demofiq-knowledge-agent

**Purpose:** Single agent with direct MCP connection to the Knowledge Base for interactive CLI chat.

### Model

- **Chat model:** gpt-4o (deployed on Azure AI Services, GlobalStandard SKU)
- **Query planning model:** gpt-4o-mini (used internally by the Knowledge Base)
- **Embedding model:** 	ext-embedding-3-large (3072 dimensions)

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
| Output mode | nswer_synthesis (web app) / EXTRACTIVE_DATA (CLI) |

## Required RBAC Roles

| Principal | Role | Scope |
|-----------|------|-------|
| Foundry project MI | Search Index Data Reader | AI Search service |
| Foundry project MI | Search Service Contributor | AI Search service |
| User / Service Principal | Azure AI User | AI Services account |
| AI Search MI | Cognitive Services User | AI Services account |
