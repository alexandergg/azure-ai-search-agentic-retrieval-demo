"""AI Research Agent — Connected to ks-ai-research Knowledge Source."""

import asyncio
import os

from azure.identity.aio import DefaultAzureCredential
from agent_framework import Agent, Message
from agent_framework.azure import AzureOpenAIChatClient, AzureAISearchContextProvider

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AI_SERVICES_ENDPOINT = os.getenv("AZURE_AI_SERVICES_ENDPOINT", "")
MODEL = os.getenv("AGENT_MODEL", "gpt-4o")
KB_NAME = os.getenv("KNOWLEDGE_BASE_NAME", "demo-knowledge-base")

AI_RESEARCH_INSTRUCTIONS = """You are an AI Research Specialist Agent.
Answer questions about foundational AI and machine learning research papers, including
transformer architectures, language model pre-training (BERT, GPT), attention mechanisms,
and large-scale model capabilities using the knowledge base.
Focus exclusively on AI research domain content.
Be specific and cite sources when possible."""


async def run_ai_research_agent(query: str) -> str:
    """Run the AI research agent with a query."""
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
        agent = Agent(
            client=chat_client,
            context_providers=[kb_context],
            instructions=AI_RESEARCH_INSTRUCTIONS,
        )

        message = Message(role="user", text=query)
        response = await agent.run([message])
        return response.text

    await credential.close()


async def main():
    print("\n🧠 AI Research Agent (ks-ai-research)")
    print("=" * 50)

    query = "What is the Transformer architecture and how does self-attention work?"
    print(f"\n❓ Query: {query}")

    response = await run_ai_research_agent(query)
    print(f"\n💬 Response:\n{response}")


if __name__ == "__main__":
    asyncio.run(main())
