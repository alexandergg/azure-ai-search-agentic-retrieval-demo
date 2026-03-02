"""Create an AI Agent with MCP-based agentic retrieval and run interactive chat.

This script:
1. Creates a Foundry Agent with an MCP tool pointing to the Knowledge Base
   MCP endpoint (authenticated via api-key header)
2. Runs an interactive CLI chat loop using threads/messages/runs
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

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

MCP_API_VERSION = "2025-11-01-preview"


def create_agent(
    agents_client: AgentsClient, config: dict, mcp_endpoint: str
) -> object:
    """Create a Foundry agent with MCP tool for agentic retrieval."""
    model = config.get("AGENT_MODEL", "gpt-4o")
    search_api_key = config.get("AZURE_SEARCH_API_KEY", "")

    console.print(f"\n[bold]Step 2 · Create Agent[/bold]")
    console.print(f"  Model:           [cyan]{model}[/cyan]")
    console.print(f"  Allowed tools:   [dim]knowledge_base_retrieve[/dim]")

    if not search_api_key:
        console.print("[red]Error:[/red] AZURE_SEARCH_API_KEY not set in .env")
        sys.exit(1)

    mcp_tool = McpTool(
        server_label="knowledge_base",
        server_url=mcp_endpoint,
        allowed_tools=["knowledge_base_retrieve"],
    )
    mcp_tool.set_approval_mode("never")
    mcp_tool.update_headers("api-key", search_api_key)

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

    # Step 1: Create agent client
    try:
        agents_client = AgentsClient(
            endpoint=project_endpoint,
            credential=credential,
        )
    except Exception as e:
        console.print(f"[red]Error creating AgentsClient:[/red] {e}")
        sys.exit(1)

    # Step 2: Create agent with MCP tool (auth via api-key header)
    agent = create_agent(agents_client, config, mcp_endpoint)

    # Step 3: Interactive chat
    run_chat_loop(agents_client, agent)

    console.print("[bold green]Done![/bold green]")


if __name__ == "__main__":
    main()
