"""Cloud & Sustainability Agent — Connected to ks-cloud-sustainability Knowledge Source."""

import asyncio
import os

from azure.identity.aio import DefaultAzureCredential
from agent_framework import Agent, Message
from agent_framework.azure import AzureOpenAIChatClient, AzureAISearchContextProvider

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AI_SERVICES_ENDPOINT = os.getenv("AZURE_AI_SERVICES_ENDPOINT", "")
MODEL = os.getenv("AGENT_MODEL", "gpt-4o")
KB_NAME = os.getenv("KNOWLEDGE_BASE_NAME", "demo-knowledge-base")

CLOUD_SUSTAINABILITY_INSTRUCTIONS = """You are a Cloud & Sustainability Specialist Agent.
Answer questions about Microsoft Azure cloud architecture, enterprise cloud solutions,
AI-driven sustainability initiatives, and technology whitepapers using the knowledge base.
Focus exclusively on cloud computing and sustainability domain content.
Be specific and cite sources when possible."""


async def run_cloud_sustainability_agent(query: str) -> str:
    """Run the cloud & sustainability agent with a query."""
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
            instructions=CLOUD_SUSTAINABILITY_INSTRUCTIONS,
        )

        message = Message(role="user", text=query)
        response = await agent.run([message])
        return response.text

    await credential.close()


async def main():
    print("\n☁️ Cloud & Sustainability Agent (ks-cloud-sustainability)")
    print("=" * 50)

    query = "How does Microsoft use AI to accelerate sustainability?"
    print(f"\n❓ Query: {query}")

    response = await run_cloud_sustainability_agent(query)
    print(f"\n💬 Response:\n{response}")


if __name__ == "__main__":
    asyncio.run(main())
