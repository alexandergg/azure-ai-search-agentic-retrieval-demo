# Document Catalog — Frontier Research & Innovation

Documents are organized by domain for multi-domain agentic retrieval. Each category maps to a separate Azure Blob Storage container and Knowledge Source. All documents are publicly available PDFs downloaded from stable URLs.

## Theme

**Frontier Research & Innovation** — A curated collection spanning AI research, space science, cybersecurity standards, and cloud technology. All sources are public domain (NASA, NIST) or open-access (arXiv, MIT-licensed Azure Samples).

## Categories

| Category | Folder | Container | Knowledge Source | Identity |
|----------|--------|-----------|------------------|----------|
| AI Research | `data/ai-research/` | `documents-ai-research` | `ks-ai-research` | Foundational ML papers (arXiv) |
| Space & Earth Science | `data/space-science/` | `documents-space-science` | `ks-space-science` | NASA publications & e-books |
| Standards & Governance | `data/standards/` | `documents-standards` | `ks-standards` | NIST cybersecurity & AI frameworks |
| Cloud & Sustainability | `data/cloud-sustainability/` | `documents-cloud-sustainability` | `ks-cloud-sustainability` | Microsoft Azure whitepapers |

## Documents

### AI Research (arXiv)
- **Attention Is All You Need** (Vaswani et al., 2017) — the Transformer architecture paper
- **BERT** (Devlin et al., 2018) — bidirectional transformer pre-training for NLP
- **GPT-4 Technical Report** (OpenAI, 2023) — capabilities and limitations

### Space & Earth Science (NASA)
- **Earth at Night** — satellite imagery and global light emission analysis
- **Earth Book 2019** — comprehensive earth observations and environmental monitoring

### Standards & Governance (NIST)
- **Cybersecurity Framework v1.1** — critical infrastructure cybersecurity
- **AI Risk Management Framework** (AI 100-1) — trustworthy AI guidelines

### Cloud & Sustainability (Microsoft)
- **Cloud Architecture for Contoso** — enterprise cloud architecture reference
- **Accelerating Sustainability with AI** — AI for environmental sustainability

## Demo Questions

Try these queries to see multi-domain agentic retrieval in action:

- *"What is the Transformer architecture and how does self-attention work?"* → AI Research
- *"What causes light pollution and how do satellites measure it?"* → Space Science
- *"What are the core functions of the NIST Cybersecurity Framework?"* → Standards
- *"How does Microsoft use AI to accelerate sustainability?"* → Cloud & Sustainability
- *"How is AI governance addressed across research papers and NIST frameworks?"* → Cross-domain

## Setup

### 1. Download documents

```bash
# Linux/Mac
bash scripts/00_download_documents.sh

# Windows (cross-platform)
python scripts/00_download_documents.py
```

### 2. Upload to Azure

```bash
bash scripts/02_upload_documents.sh
```

## Catalog File

[`catalog.json`](catalog.json) is the machine-readable catalog mapping:
- Categories → blob containers and knowledge source names
- Documents → source URLs for auto-download
- Knowledge Source descriptions → used by the KB query planner for routing
