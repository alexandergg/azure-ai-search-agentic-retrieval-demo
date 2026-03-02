"""Create an AI Agent with MCP-based agentic retrieval and run interactive chat.

This script:
1. Creates a RemoteTool project connection pointing to the Knowledge Base MCP endpoint
   (with ProjectManagedIdentity auth so the Agent Service can call Search securely)
2. Creates a Foundry Agent with an MCP tool that uses knowledge_base_retrieve
3. Runs an interactive CLI chat loop using threads/messages/runs
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import requests as http_requests

from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import McpTool, MessageRole
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from utils.config import load_config

console = Console()

SYSTEM_INSTRUCTIONS = (
    "You are a helpful assistant that answers questions using the knowledge base. "
    "Always use the available tools to search for relevant information before answering. "
    "When you find information, cite the source document name and section if available. "
    "If the knowledge base does not contain relevant information, say so clearly."
)

MCP_CONNECTION_NAME = "demofiq-kb-mcp-connection"
MCP_API_VERSION = "2025-11-01-preview"


def create_remote_tool_connection(
    config: dict, credential: DefaultAzureCredential, mcp_endpoint: str
) -> str:
    """Create a RemoteTool project connection for MCP authentication.

    This tells the Foundry Agent Service to use the project's managed identity
    when calling the Knowledge Base MCP endpoint on Azure AI Search.
    """
    project_resource_id = config["PROJECT_RESOURCE_ID"]
    connection_name = MCP_CONNECTION_NAME

    console.print(f"\n[bold]Step 1 · Create RemoteTool Connection[/bold]")
    console.print(f"  Connection name: [cyan]{connection_name}[/cyan]")
    console.print(f"  MCP endpoint:    [dim]{mcp_endpoint}[/dim]")

    token = credential.get_token("https://management.azure.com/.default").token
    url = (
        f"https://management.azure.com{project_resource_id}"
        f"/connections/{connection_name}?api-version=2025-10-01-preview"
    )

    body = {
        "properties": {
            "authType": "ProjectManagedIdentity",
            "category": "RemoteTool",
            "target": mcp_endpoint,
            "isSharedToAll": True,
            "audience": "https://search.azure.com/",
            "metadata": {"ApiType": "Azure"},
        }
    }

    resp = http_requests.put(
        url, json=body, headers={"Authorization": f"Bearer {token}"}
    )

    if resp.status_code in (200, 201):
        console.print(f"  [green]✓ RemoteTool connection created[/green]")
    else:
        console.print(f"  [red]✗ Failed ({resp.status_code}):[/red] {resp.text}")
        sys.exit(1)

    return connection_name


def delete_remote_tool_connection(
    config: dict, credential: DefaultAzureCredential
) -> None:
    """Delete the RemoteTool project connection."""
    project_resource_id = config["PROJECT_RESOURCE_ID"]
    connection_name = MCP_CONNECTION_NAME

    try:
        token = credential.get_token("https://management.azure.com/.default").token
        url = (
            f"https://management.azure.com{project_resource_id}"
            f"/connections/{connection_name}?api-version=2025-10-01-preview"
        )
        resp = http_requests.delete(
            url, headers={"Authorization": f"Bearer {token}"}
        )
        if resp.status_code in (200, 204):
            console.print(f"  [dim]RemoteTool connection deleted.[/dim]")
    except Exception:
        pass


def create_agent(
    agents_client: AgentsClient, config: dict, connection_name: str, mcp_endpoint: str
) -> object:
    """Create a Foundry agent with MCP tool for agentic retrieval."""
    model = config.get("AGENT_MODEL", "gpt-4o")

    console.print(f"\n[bold]Step 2 · Create Agent[/bold]")
    console.print(f"  Model:           [cyan]{model}[/cyan]")
    console.print(f"  MCP connection:  [dim]{connection_name}[/dim]")
    console.print(f"  Allowed tools:   [dim]knowledge_base_retrieve[/dim]")

    mcp_tool = McpTool(
        server_label="knowledge_base",
        server_url=mcp_endpoint,
        allowed_tools=["knowledge_base_retrieve"],
    )
    mcp_tool.set_approval_mode("never")

    agent = agents_client.create_agent(
        model=model,
        name="Foundry IQ Demo Agent",
        instructions=SYSTEM_INSTRUCTIONS,
        tools=mcp_tool.definitions,
        tool_resources=mcp_tool.resources,
    )

    console.print(f"  [green]✓ Agent created:[/green] {agent.id}")
    return agent


def run_chat_loop(agents_client: AgentsClient, agent: object) -> None:
    """Run an interactive chat loop with the agent."""
    thread = agents_client.threads.create()
    console.print(f"  [green]✓ Thread created:[/green] {thread.id}\n")

    console.print(
        Panel(
            "Type your question and press Enter.\n"
            "The agent uses [bold]agentic retrieval[/bold] (query decomposition → "
            "parallel subqueries → semantic reranking → unified response).\n"
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

            # Send user message
            agents_client.messages.create(
                thread_id=thread.id,
                role=MessageRole.USER,
                content=user_input,
            )

            # Create a run and poll until complete
            console.print("[dim]  ⏳ Agent is thinking (agentic retrieval)...[/dim]")
            run = agents_client.runs.create_and_process(
                thread_id=thread.id,
                agent_id=agent.id,
            )

            if run.status == "failed":
                console.print(
                    f"[red]Run failed:[/red] {getattr(run, 'last_error', 'Unknown error')}"
                )
                continue

            # Retrieve the latest assistant message
            last_msg = agents_client.messages.get_last_message_text_by_role(
                thread_id=thread.id,
                role=MessageRole.AGENT,
            )

            if last_msg:
                console.print()
                console.print("[bold green]Agent:[/bold green]")
                console.print(Markdown(last_msg.text.value))

                # Display citations if present
                annotations = getattr(last_msg.text, "annotations", [])
                if annotations:
                    console.print("\n[dim]Citations:[/dim]")
                    for ann in annotations:
                        citation = getattr(ann, "url_citation", None) or getattr(
                            ann, "file_citation", None
                        )
                        if citation:
                            title = getattr(citation, "title", None) or getattr(
                                citation, "filename", "unknown"
                            )
                            url = getattr(citation, "url", "")
                            console.print(f"  [dim]• {title}[/dim]")
                            if url:
                                console.print(f"    [dim]{url}[/dim]")
                console.print()
            else:
                console.print("[yellow]No response from agent.[/yellow]\n")

    except KeyboardInterrupt:
        console.print("\n[dim]Chat interrupted.[/dim]")

    # Cleanup
    console.print("\n[dim]Cleaning up...[/dim]")
    try:
        agents_client.threads.delete(thread.id)
        console.print(f"  [dim]Thread deleted.[/dim]")
    except Exception:
        pass
    try:
        agents_client.delete_agent(agent.id)
        console.print(f"  [dim]Agent deleted.[/dim]")
    except Exception:
        pass


def main() -> None:
    """Create agent with MCP agentic retrieval and start interactive chat."""
    console.print("[bold]Azure AI Foundry — Agent with MCP Agentic Retrieval[/bold]\n")

    config = load_config()
    credential = DefaultAzureCredential()

    project_endpoint = config["PROJECT_ENDPOINT"]
    search_endpoint = config["AZURE_SEARCH_ENDPOINT"]
    kb_name = config.get("KNOWLEDGE_BASE_NAME", "demo-knowledge-base")

    # Build the MCP endpoint URL for the Knowledge Base
    mcp_endpoint = (
        f"{search_endpoint}/knowledgebases/{kb_name}/mcp"
        f"?api-version={MCP_API_VERSION}"
    )

    console.print(f"  Project endpoint: [dim]{project_endpoint}[/dim]")
    console.print(f"  Search endpoint:  [dim]{search_endpoint}[/dim]")
    console.print(f"  Knowledge Base:   [cyan]{kb_name}[/cyan]")

    # Step 1: Create RemoteTool project connection for MCP auth
    connection_name = create_remote_tool_connection(config, credential, mcp_endpoint)

    # Step 2: Create agent with MCP tool
    try:
        agents_client = AgentsClient(
            endpoint=project_endpoint,
            credential=credential,
        )
    except Exception as e:
        console.print(f"[red]Error creating AgentsClient:[/red] {e}")
        sys.exit(1)

    agent = create_agent(agents_client, config, connection_name, mcp_endpoint)

    # Step 3: Interactive chat
    run_chat_loop(agents_client, agent)

    # Cleanup connection
    console.print("[dim]Removing MCP connection...[/dim]")
    delete_remote_tool_connection(config, credential)

    console.print("[bold green]Done![/bold green]")


if __name__ == "__main__":
    main()
