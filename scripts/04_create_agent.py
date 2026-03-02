"""Create an AI Agent with MCP-based agentic retrieval and run interactive chat.

This script follows the official Azure AI Search agentic retrieval pipeline
(2025-11-01-preview) best practices:

1. Creates a RemoteTool project connection (ProjectManagedIdentity auth)
   from the CognitiveServices-based Foundry project to the KB MCP endpoint
2. Creates an agent with MCPTool + PromptAgentDefinition via AIProjectClient
3. Chats using the OpenAI Responses API (conversations + agent references)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import requests as http_requests

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from utils.config import load_config

console = Console()

AGENT_INSTRUCTIONS = """
You are a helpful assistant that must use the knowledge base to answer all the questions from user. You must never answer from your own knowledge under any circumstances.
Every answer must always provide annotations for using the MCP knowledge base tool and render them as: `【message_idx:search_idx†source_name】`
If you cannot find the answer in the provided knowledge base you must respond with "I don't know".
""".strip()

MCP_API_VERSION = "2025-11-01-preview"
CONNECTION_ARM_API_VERSION = "2025-10-01-preview"


def create_mcp_connection(
    credential: DefaultAzureCredential,
    project_resource_id: str,
    connection_name: str,
    mcp_endpoint: str,
) -> str:
    """Create a RemoteTool project connection with ProjectManagedIdentity auth."""
    console.print(f"\n[bold]Step 1 · Create MCP Project Connection[/bold]")
    console.print(f"  Connection:  [cyan]{connection_name}[/cyan]")
    console.print(f"  MCP endpoint: [dim]{mcp_endpoint}[/dim]")
    console.print(f"  Auth:         [dim]ProjectManagedIdentity[/dim]")

    bearer_token_provider = get_bearer_token_provider(
        credential, "https://management.azure.com/.default"
    )

    response = http_requests.put(
        f"https://management.azure.com{project_resource_id}/connections/{connection_name}"
        f"?api-version={CONNECTION_ARM_API_VERSION}",
        headers={"Authorization": f"Bearer {bearer_token_provider()}"},
        json={
            "name": connection_name,
            "type": "Microsoft.CognitiveServices/accounts/projects/connections",
            "properties": {
                "authType": "ProjectManagedIdentity",
                "category": "RemoteTool",
                "target": mcp_endpoint,
                "isSharedToAll": True,
                "audience": "https://search.azure.com/",
                "metadata": {"ApiType": "Azure"},
            },
        },
        timeout=30,
    )

    if response.status_code not in (200, 201):
        console.print(f"[red]Error creating connection:[/red] {response.status_code}")
        console.print(f"[red]{response.text[:500]}[/red]")
        sys.exit(1)

    console.print(f"  [green]✓ Connection created[/green]")
    return connection_name


def create_agent(
    project_client: AIProjectClient,
    agent_name: str,
    model: str,
    mcp_endpoint: str,
    connection_name: str,
) -> object:
    """Create a Foundry agent with MCPTool for agentic retrieval."""
    console.print(f"\n[bold]Step 2 · Create Agent[/bold]")
    console.print(f"  Agent:        [cyan]{agent_name}[/cyan]")
    console.print(f"  Model:        [cyan]{model}[/cyan]")
    console.print(f"  Tool:         [dim]MCPTool → {connection_name}[/dim]")

    mcp_tool = MCPTool(
        server_label="knowledge_base",
        server_url=mcp_endpoint,
        require_approval="never",
        allowed_tools=["knowledge_base_retrieve"],
        project_connection_id=connection_name,
    )

    agent = project_client.agents.create_version(
        agent_name=agent_name,
        definition=PromptAgentDefinition(
            model=model,
            instructions=AGENT_INSTRUCTIONS,
            tools=[mcp_tool],
        ),
    )

    console.print(f"  [green]✓ Agent created:[/green] {agent.name} v{agent.version}")
    return agent


def run_chat_loop(project_client: AIProjectClient, agent: object) -> None:
    """Run interactive chat via OpenAI Responses API."""
    openai_client = project_client.get_openai_client()

    conversation = openai_client.conversations.create()
    console.print(f"  [green]✓ Conversation created:[/green] {conversation.id}\n")

    console.print(
        Panel(
            "Type your question and press Enter.\n"
            "The agent uses [bold]MCP agentic retrieval[/bold]\n"
            "(query decomposition → parallel subqueries → semantic reranking → response).\n"
            "Type [bold]quit[/bold] or [bold]exit[/bold] to stop.",
            title="Interactive Chat — MCP Agentic Retrieval",
            border_style="cyan",
        )
    )

    try:
        while True:
            try:
                user_input = console.input("[bold cyan]You:[/bold cyan] ")
            except EOFError:
                break

            if not user_input.strip():
                continue
            if user_input.strip().lower() in ("quit", "exit"):
                console.print("[dim]Ending chat session...[/dim]")
                break

            console.print("[dim]  ⏳ Agent is thinking (agentic retrieval)...[/dim]")

            try:
                response = openai_client.responses.create(
                    conversation=conversation.id,
                    tool_choice="required",
                    input=user_input,
                    extra_body={
                        "agent": {"name": agent.name, "type": "agent_reference"}
                    },
                )

                if response.output_text:
                    console.print()
                    console.print("[bold green]Agent:[/bold green]")
                    console.print(Markdown(response.output_text))
                    console.print()
                else:
                    console.print("[yellow]No response from agent.[/yellow]\n")

            except Exception as e:
                console.print(f"[red]Error:[/red] {e}\n")

    except KeyboardInterrupt:
        console.print("\n[dim]Chat interrupted.[/dim]")


def main() -> None:
    """Create agent with MCP agentic retrieval and start interactive chat."""
    console.print("[bold]Azure AI Foundry — Agent with MCP Agentic Retrieval[/bold]\n")

    config = load_config()
    credential = DefaultAzureCredential()

    foundry_endpoint = config.get("FOUNDRY_PROJECT_ENDPOINT", "")
    foundry_resource_id = config.get("FOUNDRY_PROJECT_RESOURCE_ID", "")
    search_endpoint = config["AZURE_SEARCH_ENDPOINT"]
    kb_name = config.get("KNOWLEDGE_BASE_NAME", "demo-knowledge-base")
    model = config.get("AGENT_MODEL", "gpt-4o")

    if not foundry_endpoint or not foundry_resource_id:
        console.print(
            "[red]Error:[/red] FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_PROJECT_RESOURCE_ID "
            "must be set in .env.\n"
            "Re-run 01_deploy_infra.ps1 to provision the CognitiveServices-based project."
        )
        sys.exit(1)

    # Build the MCP endpoint URL
    mcp_endpoint = (
        f"{search_endpoint}/knowledgebases/{kb_name}/mcp"
        f"?api-version={MCP_API_VERSION}"
    )

    connection_name = "demofiq_kb_mcp_connection"
    agent_name = "demofiq-knowledge-agent"

    console.print(f"  Foundry endpoint: [dim]{foundry_endpoint}[/dim]")
    console.print(f"  Search endpoint:  [dim]{search_endpoint}[/dim]")
    console.print(f"  Knowledge Base:   [cyan]{kb_name}[/cyan]")

    # Step 1: Create MCP project connection (ARM REST)
    create_mcp_connection(
        credential, foundry_resource_id, connection_name, mcp_endpoint
    )

    # Step 2: Create AIProjectClient and agent
    project_client = AIProjectClient(
        endpoint=foundry_endpoint,
        credential=credential,
    )

    agent = create_agent(
        project_client, agent_name, model, mcp_endpoint, connection_name
    )

    # Step 3: Interactive chat via Responses API
    run_chat_loop(project_client, agent)

    # Cleanup
    console.print("\n[dim]Cleaning up...[/dim]")
    try:
        project_client.agents.delete_version(agent.name, agent.version)
        console.print(f"  [dim]Agent deleted.[/dim]")
    except Exception:
        pass

    console.print("[bold green]Done![/bold green]")


if __name__ == "__main__":
    main()
