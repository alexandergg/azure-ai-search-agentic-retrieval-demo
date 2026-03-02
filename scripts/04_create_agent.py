"""Create an AI Agent with MCP tool for agentic retrieval and run interactive chat."""

# NOTE: This script uses azure-ai-projects >= 2.0.0b1 preview SDK.
# API names may change in future releases.

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import McpTool
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


def create_agent(project_client: AIProjectClient, config: dict) -> object:
    """Create a Foundry agent with MCP tool for agentic retrieval."""
    mcp_endpoint = build_mcp_endpoint(config)
    model = config.get("AGENT_MODEL", "gpt-4o")

    console.print(f"MCP Endpoint: [dim]{mcp_endpoint}[/dim]")
    console.print(f"Agent Model:  [cyan]{model}[/cyan]")

    # Create MCP tool pointing to the knowledge base
    # TODO: Connection setup may vary based on SDK preview version.
    # The MCP server URL is registered as a tool the agent can invoke.
    mcp_tool = McpTool(
        server_label="knowledge_base",
        server_url=mcp_endpoint,
        allowed_tools=["search"],
    )

    agent = project_client.agents.create_agent(
        model=model,
        name="Foundry IQ Demo Agent",
        instructions=SYSTEM_INSTRUCTIONS,
        tools=[mcp_tool],
    )

    console.print(f"[green]Agent created:[/green] {agent.id}")
    return agent


def run_chat_loop(project_client: AIProjectClient, agent: object) -> None:
    """Run an interactive chat loop with the agent."""
    thread = project_client.agents.threads.create()
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
            project_client.agents.messages.create(
                thread_id=thread.id,
                role="user",
                content=user_input,
            )

            # Create a run and poll until complete
            run = project_client.agents.runs.create_and_process(
                thread_id=thread.id,
                agent_id=agent.id,
            )

            if run.status == "failed":
                console.print(
                    f"[red]Run failed:[/red] {getattr(run, 'last_error', 'Unknown error')}"
                )
                continue

            # Retrieve the latest assistant messages
            messages = project_client.agents.messages.list(thread_id=thread.id)

            # Find the most recent assistant message
            for msg in messages.data:
                if msg.role == "assistant":
                    for block in msg.content:
                        if hasattr(block, "text"):
                            text_value = block.text.value
                            console.print()
                            console.print("[bold green]Agent:[/bold green]")
                            console.print(Markdown(text_value))

                            # Display citations if present
                            annotations = getattr(block.text, "annotations", [])
                            if annotations:
                                console.print("\n[dim]Citations:[/dim]")
                                for ann in annotations:
                                    citation = getattr(ann, "file_citation", None)
                                    if citation:
                                        console.print(
                                            f"  [dim]- {getattr(citation, 'filename', 'unknown')}[/dim]"
                                        )
                            console.print()
                    break  # Only show the latest assistant message

    except KeyboardInterrupt:
        console.print("\n[dim]Chat interrupted.[/dim]")

    # Cleanup
    console.print("[dim]Cleaning up...[/dim]")
    try:
        project_client.agents.threads.delete(thread.id)
        console.print(f"[dim]Thread {thread.id} deleted.[/dim]")
    except Exception:
        pass
    try:
        project_client.agents.delete_agent(agent.id)
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
        project_client = AIProjectClient(
            endpoint=project_endpoint,
            credential=credential,
        )
    except Exception as e:
        console.print(f"[red]Error creating AIProjectClient:[/red] {e}")
        sys.exit(1)

    # Create the agent
    agent = create_agent(project_client, config)

    # Run interactive chat
    run_chat_loop(project_client, agent)

    console.print("[bold green]Done![/bold green]")


if __name__ == "__main__":
    main()
