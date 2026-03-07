"""
Multi-Agent Orchestrator with KB Grounding.

Routes queries to specialized agents:
- AI Research Agent → ks-ai-research (transformer papers, BERT, GPT-4)
- Space Science Agent → ks-space-science (NASA publications, earth observation)
- Standards Agent → ks-standards (NIST cybersecurity & AI frameworks)
- Cloud & Sustainability Agent → ks-cloud-sustainability (Azure whitepapers, sustainability)
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob import BlobSasPermissions, generate_blob_sas
from agent_framework import Agent, Message, AgentSession, InMemoryHistoryProvider
from agent_framework.azure import AzureOpenAIChatClient, AzureAISearchContextProvider

logger = logging.getLogger(__name__)

# Configuration
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AI_SERVICES_ENDPOINT = os.getenv("AZURE_AI_SERVICES_ENDPOINT", "")
MODEL = os.getenv("AGENT_MODEL", "gpt-4o")
KB_NAME = os.getenv("KNOWLEDGE_BASE_NAME", "demo-knowledge-base")

# Parse storage connection string for SAS URL generation
_STORAGE_CONN_STR = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
_STORAGE_ACCOUNT_NAME = ""
_STORAGE_ACCOUNT_KEY = ""
if _STORAGE_CONN_STR:
    _parts = dict(part.split("=", 1) for part in _STORAGE_CONN_STR.split(";") if "=" in part)
    _STORAGE_ACCOUNT_NAME = _parts.get("AccountName", "")
    _STORAGE_ACCOUNT_KEY = _parts.get("AccountKey", "")

# Agent instructions
from .ai_research_agent import AI_RESEARCH_INSTRUCTIONS
from .space_science_agent import SPACE_SCIENCE_INSTRUCTIONS
from .standards_agent import STANDARDS_INSTRUCTIONS
from .cloud_sustainability_agent import CLOUD_SUSTAINABILITY_INSTRUCTIONS

ROUTER_INSTRUCTIONS = """You are a routing agent. Analyze the user query and determine which specialist should handle it.

Respond with ONLY one of these options:
- "ai-research" - for AI/ML research, transformer architecture, attention mechanisms, BERT, GPT, language models, neural networks, deep learning papers
- "space-science" - for NASA publications, earth observation, satellite imagery, space exploration, light pollution, environmental monitoring from space
- "standards" - for NIST frameworks, cybersecurity standards, AI risk management, governance, compliance, risk assessment
- "cloud-sustainability" - for cloud architecture, Azure services, Microsoft whitepapers, sustainability, green technology, enterprise cloud solutions
- "none" - for greetings (hi, hello, how are you), casual conversation, or any topic NOT related to the four domains above

Just respond with the option name, nothing else."""

# In-memory session storage
_sessions: dict[str, AgentSession] = {}

FOLLOW_UP_PATTERN = re.compile(r"<<FOLLOW_UP>>(.*?)<</FOLLOW_UP>>", re.DOTALL)


def _parse_follow_ups(text: str) -> tuple[str, list[str]]:
    """Extract follow-up questions from response text and return cleaned text + questions."""
    questions = [m.strip() for m in FOLLOW_UP_PATTERN.findall(text)]
    clean_text = FOLLOW_UP_PATTERN.sub("", text).strip()
    return clean_text, questions


def clear_session_memory(session_id: str) -> None:
    _sessions.pop(session_id, None)


RETRIEVAL_TYPES = frozenset(
    ["searchIndex", "azureBlob", "web", "remoteSharePoint",
     "indexedSharePoint", "indexedOneLake"]
)


def _get_search_query(act: dict) -> str:
    for key in ("searchIndexArguments", "azureBlobArguments", "webArguments"):
        args = act.get(key)
        if args and "search" in args:
            return args["search"]
    return "—"


def _generate_blob_sas_url(kb_label: str, filepath: str) -> str | None:
    """Generate a read-only SAS URL for a blob document (1-hour expiry)."""
    if not _STORAGE_ACCOUNT_NAME or not _STORAGE_ACCOUNT_KEY or not filepath:
        return None
    filename = filepath.rsplit("/", 1)[-1]
    # Skip non-file values (e.g. bare kb labels used as fallback)
    if "." not in filename:
        return None
    container_name = kb_label.replace("ks-", "documents-", 1)
    try:
        sas_token = generate_blob_sas(
            account_name=_STORAGE_ACCOUNT_NAME,
            container_name=container_name,
            blob_name=filename,
            account_key=_STORAGE_ACCOUNT_KEY,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        return f"https://{_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{container_name}/{filename}?{sas_token}"
    except Exception as e:
        logger.warning("Failed to generate SAS URL for %s/%s: %s", kb_label, filepath, e)
        return None


async def _retrieve_journey(credential, query: str, route: str) -> dict | None:
    """Make a direct KB retrieve call to capture retrieval activity data."""
    from azure.identity.aio import DefaultAzureCredential as AsyncCredential
    import aiohttp

    agent_labels = {
        "ai-research": "ks-ai-research",
        "space-science": "ks-space-science",
        "standards": "ks-standards",
        "cloud-sustainability": "ks-cloud-sustainability",
    }
    agent_names = {
        "ai-research": "AI Research Agent",
        "space-science": "Space Science Agent",
        "standards": "Standards Agent",
        "cloud-sustainability": "Cloud & Sustainability Agent",
    }

    kb_source = agent_labels.get(route)
    if not kb_source or not SEARCH_ENDPOINT:
        return None

    try:
        token_cred = AsyncCredential()
        token = await token_cred.get_token("https://search.azure.com/.default")

        url = f"{SEARCH_ENDPOINT}/knowledgebases/{KB_NAME}/retrieve?api-version=2025-11-01-preview"
        body = {
            "messages": [{"role": "user", "content": [{"type": "text", "text": query}]}],
            "retrievalReasoningEffort": {"kind": "low"},
            "includeActivity": True,
            "knowledgeSourceParams": [{
                "knowledgeSourceName": kb_source,
                "kind": "searchIndex",
                "includeReferences": True,
                "includeReferenceSourceData": True,
            }],
        }

        async with aiohttp.ClientSession() as http:
            async with http.post(url, json=body, headers={
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
            }, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status in (200, 206):
                    data = await resp.json()
                    activity = data.get("activity", [])
                    references = data.get("references", [])

                    # Build summary
                    searches = [a for a in activity if a.get("type") in RETRIEVAL_TYPES]
                    planning = [a for a in activity if a.get("type") == "modelQueryPlanning"]
                    reasoning = [a for a in activity if a.get("type") == "agenticReasoning"]
                    synthesis = [a for a in activity if a.get("type") == "modelAnswerSynthesis"]

                    summary = {
                        "total_time_ms": sum(a.get("elapsedMs", 0) for a in activity),
                        "total_docs_retrieved": sum(a.get("count", 0) for a in searches),
                        "num_subqueries": len(searches),
                        "num_references": len(references),
                        "total_input_tokens": sum(a.get("inputTokens", 0) for a in planning + synthesis),
                        "total_output_tokens": sum(a.get("outputTokens", 0) for a in planning + synthesis),
                        "total_reasoning_tokens": sum(a.get("reasoningTokens", 0) for a in reasoning),
                    }

                    return {
                        "route": route,
                        "agent_name": agent_names.get(route, route),
                        "activity": activity,
                        "references": references,
                        "summary": summary,
                    }
        await token_cred.close()
    except Exception as e:
        logger.warning("Retrieval journey call failed: %s", e)

    return None


GREETING_RESPONSE = (
    "Hello! I'm the FoundryIQ multi-agent assistant. I can help you with:\n\n"
    "🧠 **AI Research** — Transformer architecture, attention mechanisms, BERT, GPT\n"
    "🚀 **Space Science** — NASA publications, earth observation, satellite imagery\n"
    "📋 **Standards** — NIST cybersecurity framework, AI risk management\n"
    "☁️ **Cloud & Sustainability** — Azure architecture, Microsoft sustainability\n\n"
    "Ask me anything about these topics!"
)


async def route_query(client: Agent, query: str) -> str:
    """Route a query to the appropriate specialist, or 'none' for off-topic."""
    message = Message(role="user", text=query)
    response = await client.run([message])
    route = response.text.strip().lower()

    if "none" in route or "greeting" in route or "hi" in route:
        return "none"
    elif "ai-research" in route or "transformer" in route or "bert" in route or "gpt" in route:
        return "ai-research"
    elif "space" in route or "nasa" in route or "earth" in route:
        return "space-science"
    elif "standards" in route or "nist" in route or "cybersecurity" in route or "governance" in route:
        return "standards"
    elif "cloud" in route or "sustainability" in route or "azure" in route:
        return "cloud-sustainability"
    else:
        return "none"


async def run_orchestrator():
    """Run the multi-agent orchestrator interactively."""

    credential = DefaultAzureCredential()

    chat_client = AzureOpenAIChatClient(
        endpoint=AI_SERVICES_ENDPOINT,
        deployment_name=MODEL,
        credential=credential,
    )

    async with AzureAISearchContextProvider(
        endpoint=SEARCH_ENDPOINT,
        knowledge_base_name=KB_NAME,
        credential=credential,
        mode="agentic",
        knowledge_base_output_mode="answer_synthesis",
    ) as kb_context:
        # Create router agent (no KB, just for routing decisions)
        router = Agent(
            client=chat_client,
            instructions=ROUTER_INSTRUCTIONS,
        )

        # Create specialist agents with KB grounding
        specialists = {
            "ai-research": Agent(
                client=chat_client,
                context_providers=[kb_context],
                instructions=AI_RESEARCH_INSTRUCTIONS,
            ),
            "space-science": Agent(
                client=chat_client,
                context_providers=[kb_context],
                instructions=SPACE_SCIENCE_INSTRUCTIONS,
            ),
            "standards": Agent(
                client=chat_client,
                context_providers=[kb_context],
                instructions=STANDARDS_INSTRUCTIONS,
            ),
            "cloud-sustainability": Agent(
                client=chat_client,
                context_providers=[kb_context],
                instructions=CLOUD_SUSTAINABILITY_INSTRUCTIONS,
            ),
        }

        print("\n🤖 Multi-Agent Orchestrator with KB Grounding")
        print("=" * 55)
        print("Domains: AI Research | Space Science | Standards | Cloud & Sustainability")
        print("Type 'quit' to exit\n")

        while True:
            try:
                query = input("❓ You: ").strip()
                if not query or query.lower() in ("quit", "exit", "q"):
                    print("\n👋 Goodbye!")
                    break

                # Route the query
                route = await route_query(router, query)

                if route == "none":
                    print(f"\n💬 Response:\n{GREETING_RESPONSE}\n")
                    continue

                agent = specialists[route]
                print(f"\n🔄 Routed to: {route.replace('-', ' ').title()} Agent")

                # Get response from specialist
                message = Message(role="user", text=query)
                response = await agent.run([message])
                print(f"\n💬 Response:\n{response.text}\n")

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")

    await credential.close()


async def run_single_query(query: str, session_id: str | None = None) -> tuple[str, str, list[dict], list[str], dict | None]:
    """Run a single query and return (route, response, sources, suggested_questions, retrieval_journey).

    Used by the FastAPI backend for individual chat requests.
    """

    credential = DefaultAzureCredential()

    agent_labels = {
        "ai-research": "ks-ai-research",
        "space-science": "ks-space-science",
        "standards": "ks-standards",
        "cloud-sustainability": "ks-cloud-sustainability",
    }

    follow_up_suffix = "\n\nAfter your response, suggest 2-3 follow-up questions the user might ask next. Format each as: <<FOLLOW_UP>>question text<</FOLLOW_UP>>"

    chat_client = AzureOpenAIChatClient(
        endpoint=AI_SERVICES_ENDPOINT,
        deployment_name=MODEL,
        credential=credential,
    )

    async with AzureAISearchContextProvider(
        endpoint=SEARCH_ENDPOINT,
        knowledge_base_name=KB_NAME,
        credential=credential,
        mode="agentic",
        knowledge_base_output_mode="answer_synthesis",
    ) as kb_context:
        router = Agent(client=chat_client, instructions=ROUTER_INSTRUCTIONS)

        specialists = {
            "ai-research": Agent(
                client=chat_client,
                context_providers=[kb_context, InMemoryHistoryProvider()],
                instructions=AI_RESEARCH_INSTRUCTIONS + follow_up_suffix,
            ),
            "space-science": Agent(
                client=chat_client,
                context_providers=[kb_context, InMemoryHistoryProvider()],
                instructions=SPACE_SCIENCE_INSTRUCTIONS + follow_up_suffix,
            ),
            "standards": Agent(
                client=chat_client,
                context_providers=[kb_context, InMemoryHistoryProvider()],
                instructions=STANDARDS_INSTRUCTIONS + follow_up_suffix,
            ),
            "cloud-sustainability": Agent(
                client=chat_client,
                context_providers=[kb_context, InMemoryHistoryProvider()],
                instructions=CLOUD_SUSTAINABILITY_INSTRUCTIONS + follow_up_suffix,
            ),
        }

        route = await route_query(router, query)

        # Short-circuit for greetings / off-topic queries
        if route == "none":
            return route, GREETING_RESPONSE, [], [], None

        agent = specialists[route]
        message = Message(role="user", text=query)

        # Get or create session
        agent_session = None
        if session_id:
            if session_id not in _sessions:
                _sessions[session_id] = agent.create_session(session_id=session_id)
            agent_session = _sessions[session_id]

        # Run agent response and retrieval journey in parallel
        async def get_response():
            if agent_session:
                return await agent.run([message], session=agent_session)
            return await agent.run([message])

        response, journey = await asyncio.gather(
            get_response(),
            _retrieve_journey(credential, query, route),
        )

        # Parse follow-up questions
        clean_text, suggested_questions = _parse_follow_ups(response.text)

        # Extract sources from citations if available
        sources = []
        kb_label = agent_labels.get(route, "unknown")

        if hasattr(response, "citations") and response.citations:
            for citation in response.citations:
                source_info = {"kb": kb_label}
                if hasattr(citation, "title") and citation.title:
                    source_info["title"] = citation.title
                if hasattr(citation, "filepath") and citation.filepath:
                    source_info["filepath"] = citation.filepath
                if hasattr(citation, "url") and citation.url:
                    source_info["url"] = citation.url
                if len(source_info) > 1:
                    sources.append(source_info)

        if not sources and hasattr(response, "context") and response.context:
            for ctx in response.context:
                source_info = {"kb": kb_label}
                if hasattr(ctx, "title"):
                    source_info["title"] = ctx.title
                if hasattr(ctx, "source"):
                    source_info["filepath"] = ctx.source
                if len(source_info) > 1:
                    sources.append(source_info)

        if not sources:
            sources = [{"kb": kb_label, "title": "Knowledge Base", "filepath": kb_label}]

        # Generate blob SAS URLs for citations missing a url
        for src in sources:
            if not src.get("url") and src.get("filepath"):
                sas_url = _generate_blob_sas_url(kb_label, src["filepath"])
                if sas_url:
                    src["url"] = sas_url

        return route, clean_text, sources, suggested_questions, journey

    await credential.close()


async def run_single_query_stream(query: str, session_id: str | None = None):
    """Stream a single query response. Yields dicts with type: 'route', 'delta', 'metadata', 'done'."""

    credential = DefaultAzureCredential()

    agent_labels = {
        "ai-research": "ks-ai-research",
        "space-science": "ks-space-science",
        "standards": "ks-standards",
        "cloud-sustainability": "ks-cloud-sustainability",
    }

    follow_up_suffix = "\n\nAfter your response, suggest 2-3 follow-up questions the user might ask next. Format each as: <<FOLLOW_UP>>question text<</FOLLOW_UP>>"

    chat_client = AzureOpenAIChatClient(
        endpoint=AI_SERVICES_ENDPOINT,
        deployment_name=MODEL,
        credential=credential,
    )

    async with AzureAISearchContextProvider(
        endpoint=SEARCH_ENDPOINT,
        knowledge_base_name=KB_NAME,
        credential=credential,
        mode="agentic",
        knowledge_base_output_mode="answer_synthesis",
    ) as kb_context:
        router = Agent(client=chat_client, instructions=ROUTER_INSTRUCTIONS)

        specialists = {
            "ai-research": Agent(
                client=chat_client,
                context_providers=[kb_context, InMemoryHistoryProvider()],
                instructions=AI_RESEARCH_INSTRUCTIONS + follow_up_suffix,
            ),
            "space-science": Agent(
                client=chat_client,
                context_providers=[kb_context, InMemoryHistoryProvider()],
                instructions=SPACE_SCIENCE_INSTRUCTIONS + follow_up_suffix,
            ),
            "standards": Agent(
                client=chat_client,
                context_providers=[kb_context, InMemoryHistoryProvider()],
                instructions=STANDARDS_INSTRUCTIONS + follow_up_suffix,
            ),
            "cloud-sustainability": Agent(
                client=chat_client,
                context_providers=[kb_context, InMemoryHistoryProvider()],
                instructions=CLOUD_SUSTAINABILITY_INSTRUCTIONS + follow_up_suffix,
            ),
        }

        route = await route_query(router, query)

        # Yield routing info
        yield {"type": "route", "agent": f"{route}-agent"}

        if route == "none":
            yield {"type": "delta", "text": GREETING_RESPONSE}
            yield {"type": "metadata", "sources": [], "suggested_questions": [], "retrieval_journey": None}
            yield {"type": "done"}
            return

        agent = specialists[route]
        message = Message(role="user", text=query)

        # Get or create session
        agent_session = None
        if session_id:
            if session_id not in _sessions:
                _sessions[session_id] = agent.create_session(session_id=session_id)
            agent_session = _sessions[session_id]

        # Start retrieval journey in background
        journey_task = asyncio.create_task(_retrieve_journey(credential, query, route))

        # Stream agent response
        full_text = ""
        if agent_session:
            stream = agent.run([message], stream=True, session=agent_session)
        else:
            stream = agent.run([message], stream=True)

        async for update in stream:
            if update.text:
                full_text += update.text
                yield {"type": "delta", "text": update.text}

        # Get final response for citations
        final_response = await stream.get_final_response()

        # Parse follow-ups from accumulated text
        clean_text, suggested_questions = _parse_follow_ups(full_text)

        # Extract sources (same logic as run_single_query)
        sources = []
        kb_label = agent_labels.get(route, "unknown")

        if hasattr(final_response, "citations") and final_response.citations:
            for citation in final_response.citations:
                source_info = {"kb": kb_label}
                if hasattr(citation, "title") and citation.title:
                    source_info["title"] = citation.title
                if hasattr(citation, "filepath") and citation.filepath:
                    source_info["filepath"] = citation.filepath
                if hasattr(citation, "url") and citation.url:
                    source_info["url"] = citation.url
                if len(source_info) > 1:
                    sources.append(source_info)

        if not sources and hasattr(final_response, "context") and final_response.context:
            for ctx in final_response.context:
                source_info = {"kb": kb_label}
                if hasattr(ctx, "title"):
                    source_info["title"] = ctx.title
                if hasattr(ctx, "source"):
                    source_info["filepath"] = ctx.source
                if len(source_info) > 1:
                    sources.append(source_info)

        if not sources:
            sources = [{"kb": kb_label, "title": "Knowledge Base", "filepath": kb_label}]

        # Generate blob SAS URLs for citations missing a url
        for src in sources:
            if not src.get("url") and src.get("filepath"):
                sas_url = _generate_blob_sas_url(kb_label, src["filepath"])
                if sas_url:
                    src["url"] = sas_url

        # Wait for retrieval journey
        journey = await journey_task

        # Yield metadata and done
        yield {
            "type": "metadata",
            "sources": sources,
            "suggested_questions": suggested_questions,
            "retrieval_journey": journey,
            "clean_text": clean_text,
        }
        yield {"type": "done"}

    await credential.close()


if __name__ == "__main__":
    asyncio.run(run_orchestrator())
