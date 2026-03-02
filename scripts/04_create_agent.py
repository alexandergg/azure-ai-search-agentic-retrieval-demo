"""Create an AI Agent with MCP-based agentic retrieval and run interactive chat.

This script follows the official Azure AI Search agentic retrieval pipeline
(2025-11-01-preview) best practices:

1. Creates a RemoteTool project connection (ProjectManagedIdentity auth)
   from the CognitiveServices-based Foundry project to the KB MCP endpoint
2. Creates an agent with MCPTool + PromptAgentDefinition via AIProjectClient
3. Chats using the OpenAI Responses API (conversations + agent references)
4. Displays retrieval journey insights (query planning, subqueries, timing,
   token usage, references) for each agent response
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

import requests as http_requests

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from rich.console import Console
from openai import RateLimitError
from openai.types.responses import ResponseCompletedEvent
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from rich import box

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


# ── Retrieval journey helpers ────────────────────────────────────────────────


def _fmt_ms(ms: float | int | None) -> str:
    """Format milliseconds to human-readable."""
    if ms is None:
        return "—"
    if ms >= 1000:
        return f"{ms / 1000:.1f}s"
    return f"{int(ms)}ms"


def _fmt_tokens(n: int | None) -> str:
    """Format token count with K/M suffix."""
    if n is None or n == 0:
        return "—"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1000:.1f}K"
    return str(n)


RETRIEVAL_TYPES = frozenset(
    ["searchIndex", "azureBlob", "web", "remoteSharePoint",
     "indexedSharePoint", "indexedOneLake"]
)


def _get_search_query(act: dict) -> str:
    """Extract the search query text from a retrieval activity record."""
    for key in ("searchIndexArguments", "azureBlobArguments", "webArguments",
                "remoteSharePointArguments", "indexedSharePointArguments",
                "indexedOneLakeArguments"):
        args = act.get(key)
        if args and "search" in args:
            return args["search"]
    return "—"


def extract_mcp_retrieval_data(response) -> tuple[list, list, list]:
    """Extract activity, references, and MCP call arguments from response.

    Returns (activity, references, mcp_calls) where mcp_calls is a list
    of dicts with 'name', 'arguments', 'output' keys.
    """
    activity, references, mcp_calls = [], [], []

    if not hasattr(response, "output") or not response.output:
        return activity, references, mcp_calls

    for item in response.output:
        item_type = getattr(item, "type", None)
        if item_type != "mcp_call":
            continue

        call_info = {
            "name": getattr(item, "name", ""),
            "arguments": getattr(item, "arguments", ""),
            "output": getattr(item, "output", ""),
            "status": getattr(item, "status", ""),
        }
        mcp_calls.append(call_info)

        raw_output = call_info["output"]
        if not raw_output:
            continue

        # Try to parse the MCP output as JSON (KB retrieval response)
        try:
            kb_data = json.loads(raw_output)
        except (json.JSONDecodeError, TypeError):
            # MCP might return plain text or wrapped format
            continue

        # Direct KB response format: {response, activity, references}
        if isinstance(kb_data, dict):
            if "activity" in kb_data:
                activity = kb_data["activity"]
            if "references" in kb_data:
                references = kb_data["references"]

        # MCP protocol content format: {content: [{type: "text", text: "..."}]}
        if not activity and isinstance(kb_data, dict) and "content" in kb_data:
            for block in kb_data.get("content", []):
                if block.get("type") == "text":
                    try:
                        inner = json.loads(block["text"])
                        if isinstance(inner, dict):
                            activity = inner.get("activity", activity)
                            references = inner.get("references", references)
                    except (json.JSONDecodeError, TypeError):
                        pass

    return activity, references, mcp_calls


def retrieve_journey_direct(
    credential: DefaultAzureCredential,
    search_endpoint: str,
    kb_name: str,
    user_query: str,
    knowledge_source_name: str | None = None,
) -> tuple[list, list]:
    """Make a direct KB retrieve call with activity/references included.

    Overrides reasoning effort to 'low' so we get query planning and
    reasoning activity even if the KB defaults to 'minimal'.
    """
    token_provider = get_bearer_token_provider(
        credential, "https://search.azure.com/.default"
    )
    url = (
        f"{search_endpoint}/knowledgebases/{kb_name}/retrieve"
        f"?api-version={MCP_API_VERSION}"
    )
    body: dict = {
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": user_query}]}
        ],
        "retrievalReasoningEffort": {"kind": "low"},
        "includeActivity": True,
    }
    # Per-source reference params
    if knowledge_source_name:
        body["knowledgeSourceParams"] = [
            {
                "knowledgeSourceName": knowledge_source_name,
                "kind": "searchIndex",
                "includeReferences": True,
                "includeReferenceSourceData": True,
            }
        ]
    try:
        resp = http_requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token_provider()}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=60,
        )
        if resp.status_code in (200, 206):
            data = resp.json()
            return data.get("activity", []), data.get("references", [])
        else:
            console.print(
                f"[dim yellow]  ⚠ KB retrieve returned {resp.status_code}: "
                f"{resp.text[:300]}[/dim yellow]"
            )
    except Exception as e:
        console.print(f"[dim yellow]  ⚠ KB retrieve error: {e}[/dim yellow]")
    return [], []


def display_retrieval_journey(
    activity: list,
    references: list,
    mcp_calls: list | None = None,
    verbose: bool = False,
) -> None:
    """Display a rich CLI panel showing the agentic retrieval journey."""
    if not activity and not mcp_calls:
        return

    # ── Categorize activities ────────────────────────────────────────────
    planning = [a for a in activity if a.get("type") == "modelQueryPlanning"]
    searches = [a for a in activity if a.get("type") in RETRIEVAL_TYPES]
    reasoning = [a for a in activity if a.get("type") == "agenticReasoning"]
    synthesis = [a for a in activity if a.get("type") == "modelAnswerSynthesis"]

    total_time = sum(a.get("elapsedMs", 0) for a in activity)
    total_docs = sum(a.get("count", 0) for a in searches)

    # ── Summary header ───────────────────────────────────────────────────
    summary_parts = []
    if searches:
        summary_parts.append(f"[cyan]{len(searches)}[/cyan] sub-queries")
    if total_docs:
        summary_parts.append(f"[cyan]{total_docs}[/cyan] docs retrieved")
    if references:
        summary_parts.append(f"[cyan]{len(references)}[/cyan] references cited")
    if total_time:
        summary_parts.append(f"[cyan]{_fmt_ms(total_time)}[/cyan] total")
    summary_line = " · ".join(summary_parts) if summary_parts else "No activity data"

    # ── Build the journey tree ───────────────────────────────────────────
    tree = Tree(f"[bold]Retrieval Journey[/bold]  {summary_line}")

    # 1. Query Planning
    for i, p in enumerate(planning):
        label = "Query Planning" if len(planning) == 1 else f"Query Planning (round {i+1})"
        in_tok = p.get("inputTokens", 0)
        out_tok = p.get("outputTokens", 0)
        elapsed = p.get("elapsedMs")
        detail = f"[dim]{_fmt_tokens(in_tok)} in / {_fmt_tokens(out_tok)} out · {_fmt_ms(elapsed)}[/dim]"
        planning_node = tree.add(f"🧠  [bold blue]{label}[/bold blue]  {detail}")

        # Show which subqueries were decomposed from this planning step
        # Activity records are ordered by id; searches following this planning
        # step (before next planning) belong to it
        p_id = p.get("id", -1)
        next_planning_id = None
        for pp in planning:
            if pp.get("id", -1) > p_id:
                if next_planning_id is None or pp["id"] < next_planning_id:
                    next_planning_id = pp["id"]
        related = [
            s for s in searches
            if s.get("id", 0) > p_id
            and (next_planning_id is None or s.get("id", 0) < next_planning_id)
        ]
        if related:
            planning_node.add(
                f"[dim]→ Decomposed into {len(related)} sub-queries[/dim]"
            )

    # 2. Search Queries
    if searches:
        search_node = tree.add(
            f"🔍  [bold magenta]Search Execution[/bold magenta]  "
            f"[dim]{len(searches)} queries · {total_docs} docs · "
            f"{_fmt_ms(sum(s.get('elapsedMs', 0) for s in searches))}[/dim]"
        )
        for s in searches:
            query_text = _get_search_query(s)
            source = s.get("knowledgeSourceName", s.get("type", "?"))
            count = s.get("count", 0)
            elapsed = s.get("elapsedMs")
            search_node.add(
                f'[dim]"{query_text}"[/dim]  '
                f"→ [cyan]{count}[/cyan] docs from [dim]{source}[/dim]  "
                f"[dim]{_fmt_ms(elapsed)}[/dim]"
            )

    # 3. Agentic Reasoning
    for r in reasoning:
        reason_tok = r.get("reasoningTokens", 0)
        effort = r.get("retrievalReasoningEffort", {}).get("kind", "?")
        elapsed = r.get("elapsedMs")
        tree.add(
            f"⚡  [bold purple]Agentic Reasoning[/bold purple]  "
            f"[dim]{_fmt_tokens(reason_tok)} tokens · effort={effort} · {_fmt_ms(elapsed)}[/dim]"
        )

    # 4. Answer Synthesis
    for s in synthesis:
        in_tok = s.get("inputTokens", 0)
        out_tok = s.get("outputTokens", 0)
        elapsed = s.get("elapsedMs")
        tree.add(
            f"📝  [bold green]Answer Synthesis[/bold green]  "
            f"[dim]{_fmt_tokens(in_tok)} in / {_fmt_tokens(out_tok)} out · {_fmt_ms(elapsed)}[/dim]"
        )

    # 5. References
    if references:
        ref_node = tree.add(
            f"📚  [bold yellow]References[/bold yellow]  "
            f"[dim]{len(references)} sources cited[/dim]"
        )
        for ref in references[:10]:
            doc_key = ref.get("docKey", ref.get("id", "?"))
            score = ref.get("rerankerScore")
            ref_type = ref.get("type", "?")
            score_str = f"  score={score:.4f}" if score is not None else ""
            ref_node.add(f"[dim]{doc_key}[/dim]  [dim]({ref_type}{score_str})[/dim]")
        if len(references) > 10:
            ref_node.add(f"[dim]… and {len(references) - 10} more[/dim]")

    console.print()
    console.print(Panel(tree, border_style="dim cyan", padding=(0, 1)))

    # ── Token usage summary table ────────────────────────────────────────
    if planning or synthesis or reasoning:
        table = Table(
            title="Token Usage", box=box.SIMPLE, show_header=True,
            title_style="bold dim", border_style="dim"
        )
        table.add_column("Phase", style="dim")
        table.add_column("Input", justify="right")
        table.add_column("Output", justify="right")
        table.add_column("Time", justify="right")

        for p in planning:
            table.add_row(
                "Query Planning",
                _fmt_tokens(p.get("inputTokens")),
                _fmt_tokens(p.get("outputTokens")),
                _fmt_ms(p.get("elapsedMs")),
            )
        for s_act in searches:
            table.add_row(
                f'Search: "{_get_search_query(s_act)[:40]}"',
                "—",
                f'{s_act.get("count", 0)} docs',
                _fmt_ms(s_act.get("elapsedMs")),
            )
        for r in reasoning:
            table.add_row(
                "Reasoning",
                "—",
                _fmt_tokens(r.get("reasoningTokens")),
                _fmt_ms(r.get("elapsedMs")),
            )
        for s in synthesis:
            table.add_row(
                "Synthesis",
                _fmt_tokens(s.get("inputTokens")),
                _fmt_tokens(s.get("outputTokens")),
                _fmt_ms(s.get("elapsedMs")),
            )
        table.add_section()
        total_in = sum(a.get("inputTokens", 0) for a in planning + synthesis)
        total_out = sum(a.get("outputTokens", 0) for a in planning + synthesis)
        total_reason = sum(a.get("reasoningTokens", 0) for a in reasoning)
        table.add_row(
            "[bold]Total[/bold]",
            f"[bold]{_fmt_tokens(total_in)}[/bold]",
            f"[bold]{_fmt_tokens(total_out + total_reason)}[/bold]",
            f"[bold]{_fmt_ms(total_time)}[/bold]",
        )
        console.print(table)

    # ── Verbose: raw MCP calls ───────────────────────────────────────────
    if verbose and mcp_calls:
        for i, call in enumerate(mcp_calls):
            console.print(
                Panel(
                    f"[bold]Tool:[/bold] {call['name']}\n"
                    f"[bold]Status:[/bold] {call['status']}\n"
                    f"[bold]Arguments:[/bold]\n{json.dumps(json.loads(call['arguments']), indent=2) if call['arguments'] else '—'}\n"
                    f"[bold]Output (first 2000 chars):[/bold]\n{call['output'][:2000] if call['output'] else '—'}",
                    title=f"MCP Call {i + 1} (raw)",
                    border_style="dim",
                )
            )


# ── Chat loop ────────────────────────────────────────────────────────────────


def run_chat_loop(
    project_client: AIProjectClient,
    agent: object,
    credential: DefaultAzureCredential,
    search_endpoint: str,
    kb_name: str,
    knowledge_source_name: str | None = None,
    verbose: bool = False,
) -> None:
    """Run interactive chat via OpenAI Responses API with retrieval journey."""
    openai_client = project_client.get_openai_client()

    conversation = openai_client.conversations.create()
    console.print(f"  [green]✓ Conversation created:[/green] {conversation.id}\n")

    console.print(
        Panel(
            "Type your question and press Enter.\n"
            "The agent uses [bold]MCP agentic retrieval[/bold]\n"
            "(query decomposition → parallel subqueries → semantic reranking → response).\n"
            "After each answer, a [bold cyan]Retrieval Journey[/bold cyan] panel shows the "
            "query processing pipeline.\n"
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
                # Retry with exponential backoff for 429 rate limits
                stream = None
                for attempt in range(4):
                    try:
                        stream = openai_client.responses.create(
                            conversation=conversation.id,
                            tool_choice="required",
                            input=user_input,
                            stream=True,
                            extra_body={
                                "agent_reference": {
                                    "name": agent.name,
                                    "type": "agent_reference",
                                }
                            },
                        )
                        break
                    except RateLimitError as rle:
                        wait = min(2 ** attempt * 15, 60)
                        if attempt < 3:
                            console.print(
                                f"[yellow]  ⚠ Rate limited — retrying in {wait}s "
                                f"(attempt {attempt + 1}/4)...[/yellow]"
                            )
                            time.sleep(wait)
                        else:
                            raise rle

                # ── Stream the agent's answer ─────────────────────────────
                console.print()
                console.print("[bold green]Agent:[/bold green]")
                full_text = ""
                completed_response = None
                mcp_tool_active = False

                with Live("", console=console, refresh_per_second=12) as live:
                    for event in stream:
                        etype = event.type

                        if etype == "response.mcp_call.in_progress":
                            mcp_tool_active = True
                            live.update(
                                Text("  🔍 Retrieving from knowledge base...",
                                     style="dim")
                            )

                        elif etype == "response.mcp_call.completed":
                            mcp_tool_active = False

                        elif etype == "response.output_text.delta":
                            full_text += event.delta
                            live.update(Markdown(full_text))

                        elif etype == "response.completed":
                            completed_response = event.response

                        elif etype == "response.failed":
                            error_msg = getattr(event, "error", event)
                            live.update(
                                Text(f"Error: {error_msg}", style="red")
                            )

                if not full_text:
                    console.print("[yellow]No response from agent.[/yellow]")

                # ── Extract & display retrieval journey ──────────────────
                if completed_response:
                    activity, references, mcp_calls = (
                        extract_mcp_retrieval_data(completed_response)
                    )
                else:
                    activity, references, mcp_calls = [], [], []

                if mcp_calls and not activity:
                    console.print(
                        f"[dim]  ℹ MCP tool returned {len(mcp_calls)} call(s) "
                        f"but no activity data (use -v to inspect raw output)[/dim]"
                    )

                # Fallback: direct KB retrieve call if MCP output lacks activity
                if not activity:
                    console.print(
                        "[dim]  ⏳ Fetching retrieval journey (direct KB call)...[/dim]"
                    )
                    activity, references = retrieve_journey_direct(
                        credential, search_endpoint, kb_name, user_input,
                        knowledge_source_name,
                    )

                if activity or mcp_calls:
                    display_retrieval_journey(
                        activity, references, mcp_calls, verbose=verbose
                    )

                console.print()

            except Exception as e:
                console.print(f"[red]Error:[/red] {e}\n")

    except KeyboardInterrupt:
        console.print("\n[dim]Chat interrupted.[/dim]")


def main() -> None:
    """Create agent with MCP agentic retrieval and start interactive chat."""
    console.print("[bold]Azure AI Foundry — Agent with MCP Agentic Retrieval[/bold]\n")

    verbose = "--verbose" in sys.argv or "-v" in sys.argv

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

    connection_name = "demofiq-kb-mcp-connection"
    agent_name = "demofiq-knowledge-agent"
    knowledge_source_name = config.get("KNOWLEDGE_SOURCE_NAME", None)

    console.print(f"  Foundry endpoint: [dim]{foundry_endpoint}[/dim]")
    console.print(f"  Search endpoint:  [dim]{search_endpoint}[/dim]")
    console.print(f"  Knowledge Base:   [cyan]{kb_name}[/cyan]")
    if verbose:
        console.print(f"  Verbose mode:     [yellow]ON[/yellow]")

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

    # Step 3: Interactive chat via Responses API with retrieval journey
    run_chat_loop(
        project_client, agent, credential, search_endpoint, kb_name,
        knowledge_source_name, verbose
    )

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
