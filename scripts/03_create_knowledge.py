"""Create Knowledge Sources and Knowledge Base for multi-domain agentic retrieval."""

# NOTE: This script uses azure-search-documents >= 11.7.0b2 preview SDK.
# API names may change in future releases.

import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.search.documents.indexes.models import (
    AIServices,
    AzureBlobKnowledgeSource,
    AzureBlobKnowledgeSourceParameters,
    AzureOpenAIVectorizerParameters,
    KnowledgeBase,
    KnowledgeBaseAzureOpenAIModel,
    KnowledgeRetrievalMinimalReasoningEffort,
    KnowledgeRetrievalOutputMode,
    KnowledgeSourceAzureOpenAIVectorizer,
    KnowledgeSourceIngestionParameters,
    KnowledgeSourceReference,
)
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.logging import RichHandler

from utils.config import load_config, load_catalog

# ── Logging setup ──────────────────────────────────────────────────────────────
LOG_FORMAT = "%(message)s"
logging.basicConfig(level=logging.WARNING, format=LOG_FORMAT, handlers=[RichHandler(rich_tracebacks=True)])
logger = logging.getLogger("knowledge")

console = Console()

POLL_INTERVAL_SECONDS = 15
MAX_POLL_ATTEMPTS = 80  # ~20 minutes max


def set_verbose(verbose: bool) -> None:
    """Enable verbose logging for Azure SDK HTTP calls."""
    if verbose:
        logger.setLevel(logging.DEBUG)
        logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.DEBUG)
        logging.getLogger("azure.search.documents").setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)


def dump_obj(label: str, obj: object) -> None:
    """Serialize an Azure SDK model to JSON and log it."""
    try:
        d = obj.as_dict() if hasattr(obj, "as_dict") else vars(obj)
        logger.debug("%s:\n%s", label, json.dumps(d, indent=2, default=str))
    except Exception:
        logger.debug("%s: %s", label, obj)


def create_knowledge_source(
    index_client: SearchIndexClient,
    config: dict,
    ks_name: str,
    container_name: str,
    ks_description: str,
    extraction_mode: str = "minimal",
) -> str:
    """Create an Azure Blob Knowledge Source for agentic retrieval."""
    connection_string = config.get("AZURE_STORAGE_CONNECTION_STRING", "")

    if not connection_string:
        console.print("[red]Error:[/red] AZURE_STORAGE_CONNECTION_STRING is not set.")
        sys.exit(1)

    mode_label = (
        "standard (Content Understanding — OCR, layout, semantic chunking)"
        if extraction_mode == "standard"
        else "minimal (built-in text extraction)"
    )
    console.print(f"\n[bold]Creating Knowledge Source[/bold] [cyan]{ks_name}[/cyan]")
    console.print(f"  Container:           [dim]{container_name}[/dim]")
    console.print(f"  Description:         [dim]{ks_description[:80]}...[/dim]")
    console.print(f"  Extraction mode:     [dim]{mode_label}[/dim]")

    ai_services_endpoint = config.get("AZURE_AI_SERVICES_ENDPOINT", "")

    # Embedding model parameters
    embedding_params = AzureOpenAIVectorizerParameters(
        resource_url=ai_services_endpoint,
        deployment_name=config["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
        model_name=config["AZURE_OPENAI_EMBEDDING_MODEL"],
    )
    console.print(f"  Embedding model:     [dim]{config['AZURE_OPENAI_EMBEDDING_DEPLOYMENT']}[/dim]")

    # Chat completion model parameters
    chat_params = AzureOpenAIVectorizerParameters(
        resource_url=ai_services_endpoint,
        deployment_name=config["AZURE_OPENAI_GPT_MINI_DEPLOYMENT"],
        model_name=config["AZURE_OPENAI_GPT_MINI_DEPLOYMENT"],
    )
    console.print(f"  Chat model:          [dim]{config['AZURE_OPENAI_GPT_MINI_DEPLOYMENT']}[/dim]")

    # Build ingestion parameters
    ingestion_kwargs = dict(
        content_extraction_mode=extraction_mode,
        embedding_model=KnowledgeSourceAzureOpenAIVectorizer(
            azure_open_ai_parameters=embedding_params
        ),
    )

    if extraction_mode == "standard":
        ingestion_kwargs["disable_image_verbalization"] = False
        ingestion_kwargs["chat_completion_model"] = KnowledgeBaseAzureOpenAIModel(
            azure_open_ai_parameters=chat_params
        )
        if not ai_services_endpoint:
            console.print("[red]Error:[/red] AZURE_AI_SERVICES_ENDPOINT is required for 'standard' mode.")
            sys.exit(1)
        console.print(f"  AI Services:         [dim]{ai_services_endpoint}[/dim]")
        ingestion_kwargs["ai_services"] = AIServices(uri=ai_services_endpoint)
    else:
        ingestion_kwargs["disable_image_verbalization"] = True

    ingestion_params = KnowledgeSourceIngestionParameters(**ingestion_kwargs)

    blob_params = AzureBlobKnowledgeSourceParameters(
        connection_string=connection_string,
        container_name=container_name,
        is_adls_gen2=False,
        ingestion_parameters=ingestion_params,
    )

    knowledge_source = AzureBlobKnowledgeSource(
        name=ks_name,
        azure_blob_parameters=blob_params,
        description=ks_description,
    )

    dump_obj("Knowledge Source request payload", knowledge_source)

    console.print("  Calling [bold]create_or_update_knowledge_source[/bold]...")
    result = index_client.create_or_update_knowledge_source(knowledge_source)
    dump_obj("Knowledge Source response", result)
    console.print(f"  [green]✓ Knowledge Source created:[/green] {result.name}")

    return result.name


def show_auto_created_resources(indexer_client: SearchIndexerClient, index_client: SearchIndexClient) -> None:
    """List the auto-created indexers, skillsets, data sources, and indexes."""
    console.print("\n[bold]Auto-provisioned resources:[/bold]")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Type", style="cyan")
    table.add_column("Name")
    table.add_column("Details", style="dim")

    for name in indexer_client.get_data_source_connection_names():
        try:
            ds = indexer_client.get_data_source_connection(name)
            detail = getattr(ds, "type", "")
            table.add_row("Data Source", name, str(detail))
        except Exception:
            table.add_row("Data Source", name, "")

    for name in indexer_client.get_skillset_names():
        try:
            ss = indexer_client.get_skillset(name)
            skills = getattr(ss, "skills", [])
            skill_types = [type(s).__name__ for s in skills] if skills else []
            table.add_row("Skillset", name, ", ".join(skill_types))
        except Exception:
            table.add_row("Skillset", name, "")

    for name in index_client.list_index_names():
        try:
            stats = index_client.get_index_statistics(name)
            doc_count = getattr(stats, "document_count", "?")
            size = getattr(stats, "storage_size", 0)
            size_mb = f"{size / 1024 / 1024:.1f} MB" if size else "0 MB"
            table.add_row("Index", name, f"{doc_count} docs, {size_mb}")
        except Exception:
            table.add_row("Index", name, "")

    for name in indexer_client.get_indexer_names():
        try:
            status = indexer_client.get_indexer_status(name)
            st = status.as_dict()
            overall = st.get("status", "?")
            last = st.get("last_result", {})
            last_status = last.get("status", "n/a")
            items_processed = last.get("items_processed", 0)
            items_failed = last.get("items_failed", 0)
            detail = f"status={overall}, last_run={last_status} ({items_processed} ok, {items_failed} fail)"
            table.add_row("Indexer", name, detail)
        except Exception:
            table.add_row("Indexer", name, "")

    if table.row_count == 0:
        console.print("  [dim]None yet (still provisioning...)[/dim]")
    else:
        console.print(table)


def poll_ingestion_status(
    index_client: SearchIndexClient,
    indexer_client: SearchIndexerClient,
    ks_names: list[str],
) -> None:
    """Poll all knowledge sources until ingestion completes for each one."""
    console.print(f"\n[bold]Monitoring ingestion[/bold] for {len(ks_names)} knowledge source(s)")
    for name in ks_names:
        console.print(f"  • [cyan]{name}[/cyan]")

    pending = set(ks_names)

    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        still_pending = set()

        for ks_name in sorted(pending):
            try:
                status = index_client.get_knowledge_source_status(ks_name)
                d = status.as_dict()
            except Exception as e:
                console.print(f"  [yellow]⚠ Could not get status for {ks_name}:[/yellow] {e}")
                still_pending.add(ks_name)
                continue

            sync_status = d.get("synchronization_status", "unknown")
            current = d.get("current_synchronization_state", {}) or {}
            last = d.get("last_synchronization_state", {}) or {}

            cur_processed = current.get("items_updates_processed", 0)
            cur_failed = current.get("items_updates_failed", 0)

            last_end = last.get("end_time", "")
            last_processed = last.get("items_updates_processed", 0)
            last_failed = last.get("items_updates_failed", 0)

            done = False
            if sync_status.lower() in ("completed", "succeeded", "failed", "stopped"):
                done = True

            # Check auto-created indexers for this KS
            try:
                for iname in indexer_client.get_indexer_names():
                    if ks_name not in iname:
                        continue
                    ist = indexer_client.get_indexer_status(iname).as_dict()
                    lr = ist.get("last_result", {}) or {}
                    lr_status = lr.get("status", "")
                    lr_items = lr.get("items_processed", 0)
                    exec_hist = ist.get("execution_history", []) or []
                    if lr_status == "success" and (lr_items > 0 or len(exec_hist) > 0):
                        done = True
                        break
            except Exception:
                pass

            if done:
                console.print(
                    f"  [{attempt}/{MAX_POLL_ATTEMPTS}] "
                    f"[cyan]{ks_name}[/cyan] [green]✓ done[/green] "
                    f"({last_processed} processed, {last_failed} failed)"
                )
            else:
                console.print(
                    f"  [{attempt}/{MAX_POLL_ATTEMPTS}] "
                    f"[cyan]{ks_name}[/cyan] sync=[bold]{sync_status}[/bold] "
                    f"({cur_processed} ok / {cur_failed} fail)"
                )
                still_pending.add(ks_name)

        pending = still_pending
        if not pending:
            console.print("\n  [green]All knowledge sources finished ingestion.[/green]")
            # Show final index stats
            try:
                for idx_name in index_client.list_index_names():
                    idx_stats = index_client.get_index_statistics(idx_name)
                    doc_count = getattr(idx_stats, "document_count", "?")
                    storage = getattr(idx_stats, "storage_size", 0) / 1024 / 1024
                    console.print(
                        f"    Index [cyan]{idx_name}[/cyan]: "
                        f"{doc_count} documents, {storage:.1f} MB"
                    )
            except Exception:
                pass
            return

        time.sleep(POLL_INTERVAL_SECONDS)

    console.print("[yellow]Polling timed out. Check the Azure portal for status.[/yellow]")


def create_knowledge_base(
    index_client: SearchIndexClient, config: dict, catalog: dict, ks_names: list[str]
) -> str:
    """Create a Knowledge Base referencing all knowledge sources."""
    kb_config = catalog.get("knowledge_base", {})
    kb_name = kb_config.get("name", config.get("KNOWLEDGE_BASE_NAME", "demo-knowledge-base"))

    console.print(f"\n[bold]Creating Knowledge Base[/bold] [cyan]{kb_name}[/cyan]")
    for name in ks_names:
        console.print(f"  Knowledge Source:    [dim]{name}[/dim]")

    ai_services_endpoint = config.get("AZURE_AI_SERVICES_ENDPOINT", "")
    chat_params = AzureOpenAIVectorizerParameters(
        resource_url=ai_services_endpoint,
        deployment_name=config["AZURE_OPENAI_GPT_MINI_DEPLOYMENT"],
        model_name=config["AZURE_OPENAI_GPT_MINI_DEPLOYMENT"],
    )
    console.print(f"  Reasoning model:     [dim]{config['AZURE_OPENAI_GPT_MINI_DEPLOYMENT']}[/dim]")

    knowledge_base = KnowledgeBase(
        name=kb_name,
        knowledge_sources=[KnowledgeSourceReference(name=n) for n in ks_names],
        models=[
            KnowledgeBaseAzureOpenAIModel(azure_open_ai_parameters=chat_params)
        ],
        retrieval_reasoning_effort=KnowledgeRetrievalMinimalReasoningEffort(),
        output_mode=KnowledgeRetrievalOutputMode.EXTRACTIVE_DATA,
        description=kb_config.get("description", "Multi-domain agentic retrieval knowledge base"),
        retrieval_instructions=kb_config.get("retrieval_instructions", ""),
        answer_instructions=kb_config.get("answer_instructions", ""),
    )

    dump_obj("Knowledge Base request payload", knowledge_base)

    console.print("  Calling [bold]create_or_update_knowledge_base[/bold]...")
    result = index_client.create_or_update_knowledge_base(knowledge_base)
    dump_obj("Knowledge Base response", result)
    console.print(f"  [green]✓ Knowledge Base created:[/green] {result.name}")
    return result.name


def main() -> None:
    """Create Knowledge Sources (one per category) and a single Knowledge Base."""
    import argparse

    parser = argparse.ArgumentParser(description="Create Knowledge Sources & Base for agentic retrieval")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose/debug logging")
    parser.add_argument(
        "--mode", choices=["minimal", "standard"], default="standard",
        help="Content extraction mode: 'standard' (OCR, layout, semantic chunking) or 'minimal' (text only). Default: standard",
    )
    args = parser.parse_args()

    set_verbose(args.verbose)

    console.print("[bold]Azure AI Search — Multi-Domain Knowledge Setup[/bold]")

    config = load_config()
    catalog = load_catalog()
    search_endpoint = config["AZURE_SEARCH_ENDPOINT"]
    credential = DefaultAzureCredential()

    console.print(f"  Search endpoint:     [dim]{search_endpoint}[/dim]")
    console.print(f"  Categories:          [dim]{len(catalog['categories'])}[/dim]")

    try:
        index_client = SearchIndexClient(endpoint=search_endpoint, credential=credential)
        indexer_client = SearchIndexerClient(endpoint=search_endpoint, credential=credential)
    except Exception as e:
        console.print(f"[red]Error creating clients:[/red] {e}")
        sys.exit(1)

    # Step 1: Create one knowledge source per category
    ks_names = []
    for category in catalog["categories"]:
        ks_name = create_knowledge_source(
            index_client,
            config,
            ks_name=category["knowledge_source_name"],
            container_name=category["container_name"],
            ks_description=f"{category['display_name']} — {category.get('description', '')}",
            extraction_mode=args.mode,
        )
        ks_names.append(ks_name)

    # Step 2: Poll ingestion for all knowledge sources
    poll_ingestion_status(index_client, indexer_client, ks_names)

    # Step 3: Create knowledge base referencing all sources
    kb_name = create_knowledge_base(index_client, config, catalog, ks_names)

    # Final summary
    mcp_endpoint = f"{search_endpoint}/knowledgebases/{kb_name}/mcp"
    ks_list = "\n".join(f"    • [cyan]{n}[/cyan]" for n in ks_names)
    console.print(
        Panel(
            f"  Knowledge Sources:\n{ks_list}\n"
            f"  Knowledge Base:   [cyan]{kb_name}[/cyan]\n"
            f"  MCP Endpoint:     [dim]{mcp_endpoint}[/dim]",
            title="[bold green]Setup complete![/bold green]",
            border_style="green",
        )
    )


if __name__ == "__main__":
    main()
