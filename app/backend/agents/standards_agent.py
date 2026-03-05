"""Standards Agent — Connected to ks-standards Knowledge Source."""

import asyncio
import os

from azure.identity.aio import DefaultAzureCredential
from agent_framework import ChatAgent, ChatMessage, Role
from agent_framework.azure import AzureAIAgentClient, AzureAISearchContextProvider

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT", "")
MODEL = os.getenv("AGENT_MODEL", "gpt-4o")
KB_NAME = os.getenv("KNOWLEDGE_BASE_NAME", "demo-knowledge-base")

STANDARDS_INSTRUCTIONS = """You are a Standards & Governance Specialist Agent.
Answer questions about NIST frameworks and standards, including the Cybersecurity Framework,
AI Risk Management Framework, risk assessment guidelines, and governance best practices
using the knowledge base. Focus exclusively on standards and governance domain content.
Be specific and cite sources when possible."""


async def run_standards_agent(query: str) -> str:
    """Run the standards agent with a query."""
    credential = DefaultAzureCredential()

    async with (
        AzureAIAgentClient(
            project_endpoint=PROJECT_ENDPOINT,
            model_deployment_name=MODEL,
            credential=credential,
        ) as client,
        AzureAISearchContextProvider(
            endpoint=SEARCH_ENDPOINT,
            knowledge_base_name=KB_NAME,
            credential=credential,
            mode="agentic",
            knowledge_base_output_mode="answer_synthesis",
        ) as kb_context,
    ):
        agent = ChatAgent(
            chat_client=client,
            context_provider=kb_context,
            instructions=STANDARDS_INSTRUCTIONS,
        )

        message = ChatMessage(role=Role.USER, text=query)
        response = await agent.run(message)
        return response.text

    await credential.close()


async def main():
    print("\n📋 Standards Agent (ks-standards)")
    print("=" * 50)

    query = "What are the core functions of the NIST Cybersecurity Framework?"
    print(f"\n❓ Query: {query}")

    response = await run_standards_agent(query)
    print(f"\n💬 Response:\n{response}")


if __name__ == "__main__":
    asyncio.run(main())
