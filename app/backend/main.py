"""
FoundryIQ Multi-Agent Demo Backend

FastAPI wrapper around the multi-agent orchestrator with FoundryIQ Knowledge Bases.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    agent: str | None = None


class ChatResponse(BaseModel):
    message: str
    agent: str
    sources: list[dict] = []


class HealthResponse(BaseModel):
    status: str
    version: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    print("Starting FoundryIQ Multi-Agent Demo...")
    yield
    print("Shutting down...")


app = FastAPI(
    title="FoundryIQ Multi-Agent Demo",
    description="Multi-agent orchestration using Microsoft Agent Framework with FoundryIQ Knowledge Bases",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="0.1.0")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with the multi-agent system."""
    try:
        from agents.orchestrator import run_single_query

        route, response_text, sources = await run_single_query(request.message)

        return ChatResponse(
            message=response_text,
            agent=f"{route}-agent",
            sources=sources,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agents")
async def list_agents():
    """List available agents with their metadata."""
    return {
        "agents": [
            {
                "id": "orchestrator",
                "name": "Orchestrator",
                "description": "Routes requests to specialized agents based on query content",
                "color": "#6366F1",
            },
            {
                "id": "ai-research",
                "name": "AI Research Agent",
                "description": "Handles AI/ML research papers — transformers, BERT, GPT-4, attention mechanisms",
                "kb": "ks-ai-research",
                "color": "#10B981",
            },
            {
                "id": "space-science",
                "name": "Space Science Agent",
                "description": "Handles NASA publications, earth observation, and satellite imagery analysis",
                "kb": "ks-space-science",
                "color": "#3B82F6",
            },
            {
                "id": "standards",
                "name": "Standards Agent",
                "description": "Handles NIST frameworks, cybersecurity standards, and AI governance",
                "kb": "ks-standards",
                "color": "#EF4444",
            },
            {
                "id": "cloud-sustainability",
                "name": "Cloud & Sustainability Agent",
                "description": "Handles Azure cloud architecture, Microsoft whitepapers, and sustainability",
                "kb": "ks-cloud-sustainability",
                "color": "#8B5CF6",
            },
        ]
    }


# Mount static files for frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
