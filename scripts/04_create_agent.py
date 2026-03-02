"""Create an AI Agent with agentic retrieval via Knowledge Base and run interactive chat.

This script:
1. Creates a Foundry Agent with a function tool for knowledge base retrieval
2. Calls the Knowledge Base retrieval API locally (with AAD auth) when the
   agent invokes the tool
3. Runs an interactive CLI chat loop
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import requests as http_requests

from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import (
    FunctionDefinition,
    MessageRole,
    RequiredFunctionToolCall,
    RunStatus,
    SubmitToolOutputsAction,
    ToolDefinition,
    ToolOutput,
)
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from utils.config import load_config

console = Console()

SYSTEM_INSTRUCTIONS = (
    "You are a helpful assistant that answers questions using the knowledge base. "
    "Always call the knowledge_base_retrieve function to search for relevant information "
    "before answering. When you find information, cite the source document name and section. "
    "If the knowledge base does not contain relevant information, say so clearly."
)

KB_API_VERSION = "2025-11-01-preview"


def call_kb_retrieve(
    search_endpoint: str, kb_name: str, query: str, credential: DefaultAzureCredential,
    conversation_history: list[dict],
) -> str:
    """Call the Knowledge Base retrieval API with agentic retrieval."""
    token = credential.get_token("https://search.azure.com/.default").token

    # Build messages from conversation history + current query
    messages = []
    for msg in conversation_history[-6:]:  # Last 6 messages for context
        messages.append({
            "role": msg["role"],
            "content": [{"type": "text", "text": msg["content"]}],
        })
    # Add the current query as the latest user message if not already there
    if not messages or messages[-1]["content"][0]["text"] != query:
        messages.append({
            "role": "user",
            "content": [{"type": "text", "text": query}],
        })

    url = f"{search_endpoint}/knowledgebases/{kb_name}/retrieve?api-version={KB_API_VERSION}"

    resp = http_requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"messages": messages},
        timeout=60,
    )

    if resp.status_code != 200:
        return f"Error retrieving from knowledge base: {resp.status_code} - {resp.text[:200]}"

    data = resp.json()
    response_items = data.get("response", [])

    # Extract text content from response
    results = []
    for item in response_items:
        content_parts = item.get("content", [])
        for part in content_parts:
            if part.get("type") == "text":
                results.append(part["text"])

    if not results:
        return "No relevant information found in the knowledge base."

    return "\n\n".join(results)


def create_agent(agents_client: AgentsClient, config: dict) -> object:
    """Create a Foundry agent with a function tool for KB retrieval."""
    model = config.get("AGENT_MODEL", "gpt-4o")

    console.print(f"\n[bold]Step 1 · Create Agent[/bold]")
    console.print(f"  Model:           [cyan]{model}[/cyan]")
    console.print(f"  Tool:            [dim]knowledge_base_retrieve (function)[/dim]")

    tool_def = ToolDefinition(
        type="function",
        function=FunctionDefinition(
            name="knowledge_base_retrieve",
            description=(
                "Search the knowledge base for information from indexed documents. "
                "Use this for any question about the documents. The knowledge base "
                "performs agentic retrieval with query decomposition and semantic reranking."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find relevant information.",
                    }
                },
                "required": ["query"],
            },
        ),
    )

    agent = agents_client.create_agent(
        model=model,
        name="Foundry IQ Demo Agent",
        instructions=SYSTEM_INSTRUCTIONS,
        tools=[tool_def],
    )

    console.print(f"  [green]✓ Agent created:[/green] {agent.id}")
    return agent


def run_chat_loop(
    agents_client: AgentsClient,
    agent: object,
    search_endpoint: str,
    kb_name: str,
    credential: DefaultAzureCredential,
) -> None:
    """Run an interactive chat loop with the agent, handling KB retrieval locally."""
    thread = agents_client.threads.create()
    console.print(f"  [green]✓ Thread created:[/green] {thread.id}\n")

    console.print(
        Panel(
            "Type your question and press Enter.\n"
            "The agent uses [bold]agentic retrieval[/bold] via Knowledge Base API\n"
            "(query decomposition → parallel subqueries → semantic reranking → response).\n"
            "Type [bold]quit[/bold] or [bold]exit[/bold] to stop.",
            title="Interactive Chat — Agentic Retrieval",
            border_style="cyan",
        )
    )

    conversation_history: list[dict] = []

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

            conversation_history.append({"role": "user", "content": user_input})

            # Send user message
            agents_client.messages.create(
                thread_id=thread.id,
                role=MessageRole.USER,
                content=user_input,
            )

            # Create a run
            console.print("[dim]  ⏳ Agent is thinking...[/dim]")
            run = agents_client.runs.create(
                thread_id=thread.id,
                agent_id=agent.id,
            )

            # Poll and handle tool calls
            while True:
                run = agents_client.runs.get(thread_id=thread.id, run_id=run.id)

                if run.status == RunStatus.REQUIRES_ACTION:
                    action = run.required_action
                    if isinstance(action, SubmitToolOutputsAction):
                        tool_outputs = []
                        for tool_call in action.submit_tool_outputs.tool_calls:
                            if isinstance(tool_call, RequiredFunctionToolCall):
                                if tool_call.function.name == "knowledge_base_retrieve":
                                    args = json.loads(tool_call.function.arguments)
                                    query = args.get("query", user_input)
                                    console.print(f"  [dim]  🔍 Retrieving: {query[:80]}...[/dim]")
                                    result = call_kb_retrieve(
                                        search_endpoint, kb_name, query,
                                        credential, conversation_history,
                                    )
                                    tool_outputs.append(
                                        ToolOutput(tool_call_id=tool_call.id, output=result)
                                    )
                                else:
                                    tool_outputs.append(
                                        ToolOutput(
                                            tool_call_id=tool_call.id,
                                            output="Unknown function",
                                        )
                                    )
                        agents_client.runs.submit_tool_outputs(
                            thread_id=thread.id,
                            run_id=run.id,
                            tool_outputs=tool_outputs,
                        )
                    continue

                if run.status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED):
                    break

                import time
                time.sleep(0.5)

            if run.status == RunStatus.FAILED:
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
                conversation_history.append(
                    {"role": "assistant", "content": last_msg.text.value}
                )
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
    """Create agent with agentic retrieval and start interactive chat."""
    console.print("[bold]Azure AI Foundry — Agent with Agentic Retrieval[/bold]\n")

    config = load_config()
    credential = DefaultAzureCredential()

    project_endpoint = config["PROJECT_ENDPOINT"]
    search_endpoint = config["AZURE_SEARCH_ENDPOINT"]
    kb_name = config.get("KNOWLEDGE_BASE_NAME", "demo-knowledge-base")

    console.print(f"  Project endpoint: [dim]{project_endpoint}[/dim]")
    console.print(f"  Search endpoint:  [dim]{search_endpoint}[/dim]")
    console.print(f"  Knowledge Base:   [cyan]{kb_name}[/cyan]")

    # Create agent client
    try:
        agents_client = AgentsClient(
            endpoint=project_endpoint,
            credential=credential,
        )
    except Exception as e:
        console.print(f"[red]Error creating AgentsClient:[/red] {e}")
        sys.exit(1)

    # Create agent with function tool
    agent = create_agent(agents_client, config)

    # Interactive chat with local KB retrieval
    run_chat_loop(agents_client, agent, search_endpoint, kb_name, credential)

    console.print("[bold green]Done![/bold green]")


if __name__ == "__main__":
    main()
