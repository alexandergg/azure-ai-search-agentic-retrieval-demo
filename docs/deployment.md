# Deployment Guide

This guide covers deploying the FoundryIQ Multi-Agent Demo to Azure using `azd` (Azure Developer CLI) or manual methods.

## Prerequisites

- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) installed and authenticated
- [Azure Developer CLI (azd)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) installed
- [Python 3.11+](https://www.python.org/downloads/)
- [Node.js 22+](https://nodejs.org/) (for frontend build)
- Azure subscription with **Owner** or **Contributor + User Access Administrator** roles

## Option 1: Deploy with azd (Recommended)

### 1. Authenticate

```bash
az login
azd auth login
```

### 2. Deploy infrastructure and application

```bash
azd up
```

This will:
- Provision all Azure infrastructure (AI Search, Storage, AI Services, Foundry, Container Registry, Container Apps)
- Build the React frontend (prebuild hook)
- Build and push the Docker image
- Deploy the backend to Azure Container Apps

### 3. Set up Knowledge Base

After infrastructure is deployed, run the pipeline scripts:

```bash
# Download documents (use .sh on Linux/Mac or .py cross-platform)
bash scripts/00_download_documents.sh
# or: python scripts/00_download_documents.py

# Upload to Blob Storage
bash scripts/02_upload_documents.sh
# or: python scripts/02_upload_documents.py

# Create Knowledge Sources + Knowledge Base
bash scripts/03_create_knowledge.sh
# or: python scripts/03_create_knowledge.py
```

### 4. Access the application

The deployment outputs the Container Apps URL. Open it in your browser.

## Option 2: Deploy Infrastructure Only (Bicep)

### 1. Deploy via Bicep

```powershell
.\scripts\01_deploy_infra.ps1
```

### 2. Build and run locally

```bash
# Build frontend
cd app/frontend
npm install && npm run build

# Run backend
cd ../backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Option 3: Local Development

### 1. Backend

```bash
cd app/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Frontend (with hot reload)

```bash
cd app/frontend
npm install
npm run dev
```

The Vite dev server proxies `/chat`, `/health`, and `/agents` API calls to `localhost:8000`.

## API Endpoints

The backend serves the following endpoints:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Non-streaming chat (JSON request/response) |
| POST | `/chat/stream` | Streaming chat via Server-Sent Events (SSE) |
| DELETE | `/chat/{session_id}` | Clear conversation session memory |
| GET | `/health` | Health check |
| GET | `/agents` | List available specialist agents |

## Environment Variables

The `.env` file at the project root is used by both CLI scripts and the backend. Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_SEARCH_ENDPOINT` | Yes | Azure AI Search endpoint |
| `PROJECT_ENDPOINT` | Yes | Azure AI Foundry project endpoint |
| `AGENT_MODEL` | No | Chat model (default: `gpt-4o`) |
| `KNOWLEDGE_BASE_NAME` | No | KB name (default: `demo-knowledge-base`) |

See `.env.example` for the full list.

## Container Apps Configuration

The Dockerfile in `app/backend/` builds a production image:

- Base image: `python:3.11-slim`
- Serves FastAPI via uvicorn on port 8000
- Frontend static assets are bundled into `static/`

## Updating the Deployment

```bash
# After code changes
azd deploy

# After infrastructure changes
azd provision
```
