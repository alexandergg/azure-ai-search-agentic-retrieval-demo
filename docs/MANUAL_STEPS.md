# Manual Setup Steps

Some resources and configurations must be set up manually in the Azure Portal after infrastructure deployment.

## 1. Azure AI Search RBAC Configuration

The search service must allow RBAC-based access for the managed identity:

1. Go to **Azure Portal** → your **AI Search** resource
2. Navigate to **Settings** → **Keys**
3. Set API access control to **"Both"** (API keys + RBAC)

This enables the Foundry project's managed identity to access search indexes and knowledge bases.

## 2. Required RBAC Role Assignments

| Principal | Role | Scope |
|-----------|------|-------|
| Foundry project MI | Search Index Data Reader | AI Search service |
| Foundry project MI | Search Service Contributor | AI Search service |
| User / Service Principal | Azure AI User | AI Services account |
| AI Search MI | Cognitive Services User | AI Services account |

### Assign via CLI

```bash
# Get principal IDs
SEARCH_MI=$(az search service show -n <search-name> -g <rg> --query identity.principalId -o tsv)
PROJECT_MI=$(az cognitiveservices account show -n <project-name> -g <rg> --query identity.principalId -o tsv)

# Assign roles
az role assignment create --assignee $PROJECT_MI --role "Search Index Data Reader" --scope <search-resource-id>
az role assignment create --assignee $PROJECT_MI --role "Search Service Contributor" --scope <search-resource-id>
az role assignment create --assignee $SEARCH_MI --role "Cognitive Services User" --scope <ai-services-resource-id>
```

## 3. Model Deployments

Ensure the following models are deployed in your Azure AI Services account:

| Model | Deployment Name | SKU | Purpose |
|-------|----------------|-----|---------|
| `gpt-4o` | `gpt-4o` | GlobalStandard | Agent chat model |
| `gpt-4o-mini` | `gpt-4o-mini` | GlobalStandard | KB query planning |
| `text-embedding-3-large` | `text-embedding-3-large` | Standard | Document embeddings (3072 dim) |

## 4. Knowledge Base Setup

After infrastructure and RBAC are configured:

```bash
# Download sample documents
bash scripts/00_download_documents.sh

# Upload to Blob Storage
bash scripts/02_upload_documents.sh

# Create Knowledge Sources + Knowledge Base
bash scripts/03_create_knowledge.sh
```

## 5. Verify Setup

Test the agent CLI:

```bash
python scripts/04_create_agent.py
```

Test the web app:

```bash
cd app/backend && uvicorn main:app --port 8000
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| 403 Forbidden on search | Set search Keys to "Both" in Azure Portal |
| Agent returns generic answers | Verify KB was created with `03_create_knowledge.sh` |
| Missing model deployment | Deploy required models in AI Services |
| Managed identity errors | Run RBAC role assignments above |
| Container Apps not starting | Check `.env` is properly configured |
