"""Space Science Agent — Connected to ks-space-science Knowledge Source."""

import asyncio
import os

from azure.identity.aio import DefaultAzureCredential
from agent_framework import Agent, Message
from agent_framework.azure import AzureOpenAIChatClient, AzureAISearchContextProvider

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AI_SERVICES_ENDPOINT = os.getenv("AZURE_AI_SERVICES_ENDPOINT", "")
MODEL = os.getenv("AGENT_MODEL", "gpt-4o")
KB_NAME = os.getenv("KNOWLEDGE_BASE_NAME", "demo-knowledge-base")

SPACE_SCIENCE_INSTRUCTIONS = """You are a Space & Earth Science Specialist Agent.
Answer questions about NASA publications, earth observation, satellite imagery,
light emissions, environmental monitoring from space, and earth science research
using the knowledge base. Focus exclusively on space and earth science domain content.
Be specific and cite sources when possible."""


async def run_space_science_agent(query: str) -> str:
    """Run the space science agent with a query."""
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
            instructions=SPACE_SCIENCE_INSTRUCTIONS,
        )

        message = Message(role="user", text=query)
        response = await agent.run([message])
        return response.text

    await credential.close()


async def main():
    print("\n🚀 Space Science Agent (ks-space-science)")
    print("=" * 50)

    query = "What causes light pollution and how do satellites measure it?"
    print(f"\n❓ Query: {query}")

    response = await run_space_science_agent(query)
    print(f"\n💬 Response:\n{response}")


if __name__ == "__main__":
    asyncio.run(main())
