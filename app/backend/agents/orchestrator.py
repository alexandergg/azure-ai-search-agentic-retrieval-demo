"""
Multi-Agent Orchestrator with KB Grounding.

Routes queries to specialized agents:
- AI Research Agent → ks-ai-research (transformer papers, BERT, GPT-4)
- Space Science Agent → ks-space-science (NASA publications, earth observation)
- Standards Agent → ks-standards (NIST cybersecurity & AI frameworks)
- Cloud & Sustainability Agent → ks-cloud-sustainability (Azure whitepapers, sustainability)
"""

import asyncio
import os

from azure.identity.aio import DefaultAzureCredential
from agent_framework import Agent, Message
from agent_framework.azure import AzureOpenAIChatClient, AzureAISearchContextProvider

# Configuration
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AI_SERVICES_ENDPOINT = os.getenv("AZURE_AI_SERVICES_ENDPOINT", "")
MODEL = os.getenv("AGENT_MODEL", "gpt-4o")
KB_NAME = os.getenv("KNOWLEDGE_BASE_NAME", "demo-knowledge-base")

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


async def run_single_query(query: str) -> tuple[str, str, list[dict]]:
    """Run a single query and return (route, response, sources).

    Used by the FastAPI backend for individual chat requests.
    """

    credential = DefaultAzureCredential()

    agent_labels = {
        "ai-research": "ks-ai-research",
        "space-science": "ks-space-science",
        "standards": "ks-standards",
        "cloud-sustainability": "ks-cloud-sustainability",
    }

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
                client=chat_client, context_providers=[kb_context], instructions=AI_RESEARCH_INSTRUCTIONS
            ),
            "space-science": Agent(
                client=chat_client, context_providers=[kb_context], instructions=SPACE_SCIENCE_INSTRUCTIONS
            ),
            "standards": Agent(client=chat_client, context_providers=[kb_context], instructions=STANDARDS_INSTRUCTIONS),
            "cloud-sustainability": Agent(
                client=chat_client, context_providers=[kb_context], instructions=CLOUD_SUSTAINABILITY_INSTRUCTIONS
            ),
        }

        route = await route_query(router, query)

        # Short-circuit for greetings / off-topic queries
        if route == "none":
            return route, GREETING_RESPONSE, []

        agent = specialists[route]
        message = Message(role="user", text=query)
        response = await agent.run([message])

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

        return route, response.text, sources

    await credential.close()


if __name__ == "__main__":
    asyncio.run(run_orchestrator())
