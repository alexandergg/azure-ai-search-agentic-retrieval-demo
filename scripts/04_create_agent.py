"""Create an AI Agent with MCP tool for agentic retrieval and run interactive chat."""

# NOTE: This script uses azure-ai-agents >= 1.2.0b6 preview SDK.
# API names may change in future releases.

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
    "When you find information, cite the source document name and page number if available. "
    "If the knowledge base does not contain relevant information, say so clearly."
)


def build_mcp_endpoint(config: dict) -> str:
    """Build the MCP endpoint URL for the knowledge base."""
    search_endpoint = config["AZURE_SEARCH_ENDPOINT"].rstrip("/")
    kb_name = config["KNOWLEDGE_BASE_NAME"]
    return f"{search_endpoint}/knowledgebases/{kb_name}/mcp"


def create_agent(agents_client: AgentsClient, config: dict) -> object:
    """Create a Foundry agent with MCP tool for agentic retrieval."""
    mcp_endpoint = build_mcp_endpoint(config)
    model = config.get("AGENT_MODEL", "gpt-4o")

    console.print(f"MCP Endpoint: [dim]{mcp_endpoint}[/dim]")
    console.print(f"Agent Model:  [cyan]{model}[/cyan]")

    mcp_tool = McpTool(
        server_label="knowledge_base",
        server_url=mcp_endpoint,
        allowed_tools=["search"],
    )

    agent = agents_client.create_agent(
        model=model,
        name="Foundry IQ Demo Agent",
        instructions=SYSTEM_INSTRUCTIONS,
        tools=mcp_tool.definitions,
        tool_resources=mcp_tool.resources,
    )

    console.print(f"[green]Agent created:[/green] {agent.id}")
    return agent


def run_chat_loop(agents_client: AgentsClient, agent: object) -> None:
    """Run an interactive chat loop with the agent."""
    thread = agents_client.threads.create()
    console.print(f"[green]Thread created:[/green] {thread.id}\n")

    console.print(
        Panel(
            "Type your question and press Enter. Type [bold]quit[/bold] or [bold]exit[/bold] to stop.",
            title="Interactive Chat",
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
            run = agents_client.runs.create_and_process(
                thread_id=thread.id,
                agent_id=agent.id,
            )

            if run.status == "failed":
                console.print(
                    f"[red]Run failed:[/red] {getattr(run, 'last_error', 'Unknown error')}"
                )
                continue

            # Retrieve the latest assistant message text
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
                        citation = getattr(ann, "file_citation", None)
                        if citation:
                            console.print(
                                f"  [dim]- {getattr(citation, 'filename', 'unknown')}[/dim]"
                            )
                console.print()
            else:
                console.print("[yellow]No response from agent.[/yellow]\n")

    except KeyboardInterrupt:
        console.print("\n[dim]Chat interrupted.[/dim]")

    # Cleanup
    console.print("[dim]Cleaning up...[/dim]")
    try:
        agents_client.threads.delete(thread.id)
        console.print(f"[dim]Thread {thread.id} deleted.[/dim]")
    except Exception:
        pass
    try:
        agents_client.delete_agent(agent.id)
        console.print(f"[dim]Agent {agent.id} deleted.[/dim]")
    except Exception:
        pass


def main() -> None:
    """Create agent and start interactive chat."""
    console.print("[bold]Azure AI Foundry — Agent with Agentic Retrieval[/bold]\n")

    config = load_config()
    credential = DefaultAzureCredential()

    project_endpoint = config["PROJECT_ENDPOINT"]
    console.print(f"Project Endpoint: [dim]{project_endpoint}[/dim]")

    try:
        agents_client = AgentsClient(
            endpoint=project_endpoint,
            credential=credential,
        )
    except Exception as e:
        console.print(f"[red]Error creating AgentsClient:[/red] {e}")
        sys.exit(1)

    # Create the agent
    agent = create_agent(agents_client, config)

    # Run interactive chat
    run_chat_loop(agents_client, agent)

    console.print("[bold green]Done![/bold green]")


if __name__ == "__main__":
    main()
