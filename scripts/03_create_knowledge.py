"""Create Knowledge Source and Knowledge Base for agentic retrieval."""

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
    KnowledgeSourceAzureOpenAIVectorizer,
    KnowledgeSourceIngestionParameters,
    KnowledgeSourceReference,
)
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.logging import RichHandler

from utils.config import load_config

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
        # Azure SDK HTTP logging
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
    index_client: SearchIndexClient, config: dict
) -> str:
    """Create an Azure Blob Knowledge Source for agentic retrieval."""
    ks_name = config["KNOWLEDGE_SOURCE_NAME"]
    connection_string = config.get("AZURE_STORAGE_CONNECTION_STRING", "")
    container_name = config.get("AZURE_STORAGE_CONTAINER_NAME", "documents")

    if not connection_string:
        console.print("[red]Error:[/red] AZURE_STORAGE_CONNECTION_STRING is not set.")
        sys.exit(1)

    console.print(f"\n[bold]Step 1 · Create Knowledge Source[/bold] [cyan]{ks_name}[/cyan]")
    console.print(f"  Container:           [dim]{container_name}[/dim]")
    console.print(f"  Extraction mode:     [dim]standard (Content Understanding)[/dim]")

    # Embedding model parameters (text-embedding-3-large)
    embedding_params = AzureOpenAIVectorizerParameters(
        resource_url=config["AZURE_OPENAI_ENDPOINT"],
        deployment_name=config["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
        model_name=config["AZURE_OPENAI_EMBEDDING_MODEL"],
    )
    console.print(f"  Embedding model:     [dim]{config['AZURE_OPENAI_EMBEDDING_DEPLOYMENT']}[/dim]")

    # Chat completion model parameters (gpt-4o-mini)
    chat_params = AzureOpenAIVectorizerParameters(
        resource_url=config["AZURE_OPENAI_ENDPOINT"],
        deployment_name=config["AZURE_OPENAI_GPT_MINI_DEPLOYMENT"],
        model_name=config["AZURE_OPENAI_GPT_MINI_DEPLOYMENT"],
    )
    console.print(f"  Chat model:          [dim]{config['AZURE_OPENAI_GPT_MINI_DEPLOYMENT']}[/dim]")

    # AI Services for Content Understanding
    ai_services_endpoint = config.get("AZURE_AI_SERVICES_ENDPOINT", "")
    if not ai_services_endpoint:
        console.print("[red]Error:[/red] AZURE_AI_SERVICES_ENDPOINT is not set.")
        sys.exit(1)
    console.print(f"  AI Services:         [dim]{ai_services_endpoint}[/dim]")

    ingestion_params = KnowledgeSourceIngestionParameters(
        disable_image_verbalization=False,
        content_extraction_mode="standard",
        embedding_model=KnowledgeSourceAzureOpenAIVectorizer(
            azure_open_ai_parameters=embedding_params
        ),
        chat_completion_model=KnowledgeBaseAzureOpenAIModel(
            azure_open_ai_parameters=chat_params
        ),
        ai_services=AIServices(uri=ai_services_endpoint),
    )

    blob_params = AzureBlobKnowledgeSourceParameters(
        connection_string=connection_string,
        container_name=container_name,
        is_adls_gen2=False,
        ingestion_parameters=ingestion_params,
    )

    knowledge_source = AzureBlobKnowledgeSource(
        name=ks_name,
        azure_blob_parameters=blob_params,
        description="Blob storage knowledge source for demo PDF documents",
    )

    dump_obj("Knowledge Source request payload", knowledge_source)

    console.print("\n  Calling [bold]create_or_update_knowledge_source[/bold]...")
    result = index_client.create_or_update_knowledge_source(knowledge_source)
    dump_obj("Knowledge Source response", result)
    console.print(f"  [green]✓ Knowledge Source created:[/green] {result.name}")

    console.print(
        Panel(
            "[dim]Behind the scenes, Azure AI Search now provisions:\n"
            "  1. Data Source Connection → points to blob container\n"
            "  2. Skillset → Content Understanding skill (layout analysis → markdown → semantic chunking)\n"
            "  3. Search Index → with vector fields for embeddings\n"
            "  4. Indexer → orchestrates the pipeline (runs automatically)[/dim]",
            title="What happens next",
            border_style="blue",
        )
    )

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
    ks_name: str,
) -> None:
    """Poll the knowledge source and indexer status until ingestion completes."""
    console.print(f"\n[bold]Step 2 · Monitor ingestion[/bold] for [cyan]{ks_name}[/cyan]")
    console.print(
        Panel(
            "[dim]Content Understanding pipeline stages per document:\n"
            "  1. Layout Analysis  — OCR + structure detection (paragraphs, tables, figures)\n"
            "  2. Markdown Convert — structural elements → Markdown (tables, headers)\n"
            "  3. Semantic Chunking — character-based chunking with overlap on Markdown\n"
            "  4. Embedding         — text-embedding-3-large vectors per chunk\n"
            "  5. Indexing          — chunks written to the search index[/dim]",
            title="Content Understanding Pipeline",
            border_style="magenta",
        )
    )

    resources_shown = False

    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        # ── Knowledge Source status ──
        try:
            status = index_client.get_knowledge_source_status(ks_name)
            d = status.as_dict()
            logger.debug("KS status poll %d: %s", attempt, json.dumps(d, indent=2, default=str))
        except Exception as e:
            console.print(f"  [yellow]⚠ Could not get KS status:[/yellow] {e}")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        sync_status = d.get("synchronization_status", "unknown")
        current = d.get("current_synchronization_state", {}) or {}
        last = d.get("last_synchronization_state", {}) or {}
        stats = d.get("statistics", {}) or {}

        cur_processed = current.get("items_updates_processed", 0)
        cur_failed = current.get("items_updates_failed", 0)
        cur_skipped = current.get("items_skipped", 0)
        cur_start = current.get("start_time", "")

        last_processed = last.get("items_updates_processed", 0)
        last_failed = last.get("items_updates_failed", 0)
        last_start = last.get("start_time", "")
        last_end = last.get("end_time", "")

        # ── Indexer status (auto-created) ──
        indexer_info = ""
        try:
            indexer_names = indexer_client.get_indexer_names()
            for iname in indexer_names:
                ist = indexer_client.get_indexer_status(iname).as_dict()
                logger.debug("Indexer %s status: %s", iname, json.dumps(ist, indent=2, default=str))
                lr = ist.get("last_result", {}) or {}
                exec_hist = ist.get("execution_history", []) or []
                lr_status = lr.get("status", "n/a")
                lr_items = lr.get("items_processed", 0)
                lr_failed = lr.get("items_failed", 0)
                lr_errors = lr.get("errors", []) or []
                lr_warnings = lr.get("warnings", []) or []
                indexer_info = (
                    f"  Indexer [cyan]{iname}[/cyan]: "
                    f"last_run=[bold]{lr_status}[/bold] "
                    f"items={lr_items} failed={lr_failed} "
                    f"errors={len(lr_errors)} warnings={len(lr_warnings)} "
                    f"runs={len(exec_hist)}"
                )
                # Show errors/warnings in detail
                for err in lr_errors[:3]:
                    msg = err.get("message", err.get("errorMessage", str(err)))
                    console.print(f"    [red]ERROR:[/red] {msg[:200]}")
                for warn in lr_warnings[:3]:
                    msg = warn.get("message", warn.get("name", str(warn)))
                    console.print(f"    [yellow]WARN:[/yellow] {msg[:200]}")
        except Exception:
            pass

        # Print consolidated status line
        console.print(
            f"  [{attempt}/{MAX_POLL_ATTEMPTS}] "
            f"KS sync=[bold]{sync_status}[/bold] | "
            f"current: {cur_processed} ok / {cur_failed} fail / {cur_skipped} skip"
        )
        if indexer_info:
            console.print(indexer_info)

        # Show auto-created resources once they appear
        if not resources_shown and indexer_client.get_indexer_names():
            show_auto_created_resources(indexer_client, index_client)
            resources_shown = True

        # Terminal states
        if sync_status.lower() in ("completed", "succeeded", "failed", "stopped"):
            if last_end:
                console.print(f"\n  [green]Ingestion finished:[/green] {sync_status}")
                console.print(f"    Started:   {last_start}")
                console.print(f"    Ended:     {last_end}")
                console.print(f"    Processed: {last_processed}")
                console.print(f"    Failed:    {last_failed}")
            else:
                console.print(f"\n  [green]Ingestion finished with status:[/green] {sync_status}")

            # Final index stats
            try:
                for idx_name in index_client.list_index_names():
                    idx_stats = index_client.get_index_statistics(idx_name)
                    console.print(
                        f"    Index [cyan]{idx_name}[/cyan]: "
                        f"{getattr(idx_stats, 'document_count', '?')} documents, "
                        f"{getattr(idx_stats, 'storage_size', 0) / 1024 / 1024:.1f} MB"
                    )
            except Exception:
                pass
            return

        if sync_status.lower() not in (
            "active", "creating", "running", "inprogress", "in_progress", "queued", "unknown"
        ):
            console.print(f"  [yellow]Unexpected status:[/yellow] {sync_status}")
            return

        time.sleep(POLL_INTERVAL_SECONDS)

    console.print("[yellow]Polling timed out. Check the Azure portal for status.[/yellow]")


def create_knowledge_base(
    index_client: SearchIndexClient, config: dict, ks_name: str
) -> str:
    """Create a Knowledge Base referencing the knowledge source."""
    kb_name = config["KNOWLEDGE_BASE_NAME"]

    console.print(f"\n[bold]Step 3 · Create Knowledge Base[/bold] [cyan]{kb_name}[/cyan]")
    console.print(f"  Knowledge Source:    [dim]{ks_name}[/dim]")

    chat_params = AzureOpenAIVectorizerParameters(
        resource_url=config["AZURE_OPENAI_ENDPOINT"],
        deployment_name=config["AZURE_OPENAI_GPT_MINI_DEPLOYMENT"],
        model_name=config["AZURE_OPENAI_GPT_MINI_DEPLOYMENT"],
    )
    console.print(f"  Reasoning model:     [dim]{config['AZURE_OPENAI_GPT_MINI_DEPLOYMENT']}[/dim]")

    knowledge_base = KnowledgeBase(
        name=kb_name,
        knowledge_sources=[
            KnowledgeSourceReference(name=ks_name)
        ],
        models=[
            KnowledgeBaseAzureOpenAIModel(
                azure_open_ai_parameters=chat_params
            )
        ],
        description="Knowledge base for Foundry IQ demo with agentic retrieval",
    )

    dump_obj("Knowledge Base request payload", knowledge_base)

    console.print("  Calling [bold]create_or_update_knowledge_base[/bold]...")
    result = index_client.create_or_update_knowledge_base(knowledge_base)
    dump_obj("Knowledge Base response", result)
    console.print(f"  [green]✓ Knowledge Base created:[/green] {result.name}")
    return result.name


def main() -> None:
    """Create Knowledge Source and Knowledge Base."""
    import argparse

    parser = argparse.ArgumentParser(description="Create Knowledge Source & Base for agentic retrieval")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose/debug logging (SDK HTTP traces)")
    args = parser.parse_args()

    set_verbose(args.verbose)

    console.print("[bold]Azure AI Search — Knowledge Source & Base Setup[/bold]")

    config = load_config()
    search_endpoint = config["AZURE_SEARCH_ENDPOINT"]
    credential = DefaultAzureCredential()

    console.print(f"  Search endpoint:     [dim]{search_endpoint}[/dim]")

    try:
        index_client = SearchIndexClient(endpoint=search_endpoint, credential=credential)
        indexer_client = SearchIndexerClient(endpoint=search_endpoint, credential=credential)
    except Exception as e:
        console.print(f"[red]Error creating clients:[/red] {e}")
        sys.exit(1)

    # Step 1: Create knowledge source
    ks_name = create_knowledge_source(index_client, config)

    # Step 2: Poll ingestion until complete
    poll_ingestion_status(index_client, indexer_client, ks_name)

    # Step 3: Create knowledge base
    kb_name = create_knowledge_base(index_client, config, ks_name)

    # Final summary
    mcp_endpoint = f"{search_endpoint}/knowledgebases/{kb_name}/mcp"
    console.print(
        Panel(
            f"  Knowledge Source: [cyan]{ks_name}[/cyan]\n"
            f"  Knowledge Base:   [cyan]{kb_name}[/cyan]\n"
            f"  MCP Endpoint:     [dim]{mcp_endpoint}[/dim]",
            title="[bold green]Setup complete![/bold green]",
            border_style="green",
        )
    )


if __name__ == "__main__":
    main()
