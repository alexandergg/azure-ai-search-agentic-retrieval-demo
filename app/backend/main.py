"""
FoundryIQ Multi-Agent Demo Backend

FastAPI wrapper around the multi-agent orchestrator with FoundryIQ Knowledge Bases.
"""

import json
import logging
import os
import traceback
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    agent: str | None = None


class ChatResponse(BaseModel):
    message: str
    agent: str
    sources: list[dict] = []
    suggested_questions: list[str] = []
    retrieval_journey: dict | None = None


class HealthResponse(BaseModel):
    status: str
    version: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    print("Starting FoundryIQ Multi-Agent Demo...")
    # Validate agent imports at startup
    try:
        from agents.orchestrator import run_single_query  # noqa: F401
        print("  ✓ Agent imports OK")
    except Exception as e:
        print(f"  ✗ Agent import error: {e}")
        logger.error("Agent import failed:\n%s", traceback.format_exc())
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


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat response using Server-Sent Events."""
    async def event_generator():
        try:
            from agents.orchestrator import run_single_query_stream

            async for event in run_single_query_stream(request.message, request.session_id):
                event_type = event.get("type", "")
                data = json.dumps(event, ensure_ascii=False)
                yield f"event: {event_type}\ndata: {data}\n\n"
        except Exception as e:
            logger.error("Error in /chat/stream endpoint:\n%s", traceback.format_exc())
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with the multi-agent system."""
    try:
        from agents.orchestrator import run_single_query

        route, response_text, sources, suggested_questions, retrieval_journey = await run_single_query(
            request.message, request.session_id
        )

        return ChatResponse(
            message=response_text,
            agent=f"{route}-agent",
            sources=sources,
            suggested_questions=suggested_questions,
            retrieval_journey=retrieval_journey,
        )
    except Exception as e:
        logger.error("Error in /chat endpoint:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/chat/{session_id}")
async def clear_session(session_id: str):
    from agents.orchestrator import clear_session_memory

    clear_session_memory(session_id)
    return {"status": "cleared"}


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
