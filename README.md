# FoundryIQ Multi-Agent Demo

A multi-agent orchestration demo using **Microsoft Agent Framework SDK** and **Azure AI Foundry** with **FoundryIQ Knowledge Bases** for grounded retrieval across 4 domains.

## Features

- **Multi-Agent Orchestration** -- Intelligent routing of queries to specialist agents (AI Research, Space Science, Standards, Cloud & Sustainability)
- **Microsoft Agent Framework SDK** -- Built on the official gent-framework Python SDK with AzureAISearchContextProvider
- **FoundryIQ Knowledge Bases** -- Agentic retrieval mode with LLM-powered query planning and semantic reranking
- **React + FastAPI Web App** -- Interactive chat UI with workflow visualization and execution trace
- **CLI Pipeline** -- Standalone scripts for document ingestion, KB setup, and single-agent chat
- **RBAC-Only Auth** -- Uses DefaultAzureCredential for all Azure services
- **azd Deployment** -- Infrastructure as Code with Bicep + Container Apps

## Architecture

`
User Query
    |
    v
ORCHESTRATOR AGENT (routes by intent)
    |
    +---> AI RESEARCH AGENT (ks-ai-research) -- transformer papers, BERT, GPT-4, ML research
    +---> SPACE SCIENCE AGENT (ks-space-science) -- NASA pubs, earth observation, satellite imagery
    +---> STANDARDS AGENT (ks-standards) -- NIST frameworks, cybersecurity, AI governance
    +---> CLOUD & SUSTAINABILITY AGENT (ks-cloud-sustainability) -- Azure whitepapers, sustainability
    |
    v
FOUNDRYIQ KNOWLEDGE BASE (demo-knowledge-base)
  1 KB with 4 Knowledge Sources
  LLM query planning routes subqueries to the most relevant source(s)
  Hybrid search + semantic reranking
`

## Prerequisites

- **Azure subscription** with **Owner** or **Contributor + User Access Administrator** roles
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) installed and authenticated
- [Azure Developer CLI (azd)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- **Python 3.11+**
- **Node.js 22+** (for frontend)
- An Azure region that supports agentic retrieval (e.g., astus2, westeurope, swedencentral)

## Quick Start

### 1. Clone and set up

`ash
git clone <repo-url>
cd demo-foundry-iq

python -m venv .venv
source .venv/bin/activate  # or .venv\\Scripts\\Activate on Windows

pip install -r requirements.txt
pip install -r app/backend/requirements.txt
`

### 2. Deploy Azure infrastructure

`powershell
.\\scripts\\01_deploy_infra.ps1
`

Or with azd:

`ash
az login && azd auth login
azd up
`

### 3. Set up Knowledge Base

`ash
# Download documents (Linux/Mac)
bash scripts/00_download_documents.sh

# Download documents (Windows cross-platform)
python scripts/00_download_documents.py

# Upload and create knowledge base
bash scripts/02_upload_documents.sh
bash scripts/03_create_knowledge.sh
`

### 4. Run the web app

`ash
# Build frontend
cd app/frontend && npm install && npm run build && cd ../..

# Start backend
cd app/backend
uvicorn main:app --reload --port 8000
`

Open http://localhost:8000 in your browser.

### 5. Or use the CLI agent

`ash
python scripts/04_create_agent.py
`

### 6. Cleanup

`ash
bash scripts/05_cleanup.sh
# Or: az group delete --name rg-demo-foundry-iq --yes --no-wait
`

## Project Structure

`
demo-foundry-iq/
+-- app/
|   +-- backend/
|   |   +-- main.py                # FastAPI app (/chat, /health, /agents)
|   |   +-- requirements.txt       # Backend dependencies
|   |   +-- Dockerfile             # Production container image
|   |   +-- agents/
|   |   |   +-- orchestrator.py    # Router + run_single_query()
|   |   |   +-- ai_research_agent.py    # AI Research specialist
|   |   |   +-- space_science_agent.py  # Space Science specialist
|   |   |   +-- standards_agent.py      # Standards specialist
|   |   |   +-- cloud_sustainability_agent.py # Cloud & Sustainability specialist
|   |   +-- static/                # Frontend build output
|   +-- frontend/
|       +-- package.json           # React 18 + Vite + TypeScript
|       +-- vite.config.ts         # Builds to ../backend/static
|       +-- src/
|           +-- App.tsx            # Chat UI with workflow visualization
|           +-- main.tsx           # React entry point
|           +-- index.css          # Dark theme styling
+-- scripts/                       # CLI pipeline
|   +-- 00_download_documents.sh
|   +-- 01_deploy_infra.ps1
|   +-- 02_upload_documents.sh
|   +-- 03_create_knowledge.sh
|   +-- 04_create_agent.py
|   +-- 05_cleanup.sh
|   +-- utils/config.py            # Python config (for 04_create_agent.py)
|   +-- utils/config.sh            # Bash config (for .sh scripts)
+-- data/
|   +-- catalog.json               # Document catalog (4 domains)
|   +-- ai-research/ space-science/ standards/ cloud-sustainability/
+-- docs/
|   +-- architecture.md            # Detailed architecture
|   +-- deployment.md              # Deployment guide
|   +-- MANUAL_STEPS.md            # Manual Azure setup steps
+-- infra/                         # Bicep IaC templates
+-- azure.yaml                     # azd configuration
+-- .devcontainer/                 # Dev container setup
+-- pyproject.toml                 # Project config + tool settings
+-- requirements.txt               # CLI script dependencies
+-- requirements-dev.txt           # Development dependencies
+-- AGENTS.md                      # Agent specification (Copilot)
`

## Knowledge Base Mapping

| Agent | Knowledge Source | Content |
|-------|----------------|---------|
| AI Research | ks-ai-research | Transformer papers, BERT, GPT-4, ML research |
| Space Science | ks-space-science | NASA publications, earth observation, satellite imagery |
| Standards | ks-standards | NIST cybersecurity framework, AI risk management |
| Cloud & Sustainability | ks-cloud-sustainability | Azure whitepapers, cloud architecture, sustainability |

All 4 sources are combined into a single Knowledge Base (demo-knowledge-base) with LLM-powered query planning that routes subqueries to the most relevant source(s).

## Configuration

All configuration is managed through a .env file. Copy .env.example to .env:

| Variable | Description |
|---|---|
| AZURE_SEARCH_ENDPOINT | Azure AI Search service endpoint |
| PROJECT_ENDPOINT | Azure AI Foundry project API endpoint |
| PROJECT_RESOURCE_ID | Full ARM resource ID for the Foundry project |
| AGENT_MODEL | Chat model (default: gpt-4o) |
| KNOWLEDGE_BASE_NAME | KB name (default: demo-knowledge-base) |
| AZURE_STORAGE_CONNECTION_STRING | Blob Storage connection string |
| AZURE_AI_SERVICES_ENDPOINT | AI Services endpoint for Content Understanding |

See .env.example for the full variable list.

## Documentation

- [Architecture](docs/architecture.md) -- Detailed system architecture
- [Deployment Guide](docs/deployment.md) -- azd, Docker, and local deployment
- [Manual Steps](docs/MANUAL_STEPS.md) -- Azure Portal setup and RBAC configuration

## Resources

- [Azure AI Foundry IQ](https://learn.microsoft.com/azure/ai-services/agents/)
- [Agentic Retrieval](https://learn.microsoft.com/azure/ai-services/agents/concepts/agentic-retrieval)
- [Microsoft Agent Framework SDK](https://pypi.org/project/agent-framework-core/)
- [Azure Content Understanding](https://learn.microsoft.com/azure/ai-services/content-understanding/)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
