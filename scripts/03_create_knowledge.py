"""Create Knowledge Source and Knowledge Base for agentic retrieval."""

# NOTE: This script uses azure-search-documents >= 11.7.0b2 preview SDK.
# API names may change in future releases.

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
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

from utils.config import load_config

console = Console()

POLL_INTERVAL_SECONDS = 15
MAX_POLL_ATTEMPTS = 80  # ~20 minutes max


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

    console.print(f"Creating Knowledge Source [cyan]{ks_name}[/cyan]...")

    # Embedding model parameters (text-embedding-3-large)
    embedding_params = AzureOpenAIVectorizerParameters(
        resource_url=config["AZURE_OPENAI_ENDPOINT"],
        deployment_name=config["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
        model_name=config["AZURE_OPENAI_EMBEDDING_MODEL"],
    )

    # Chat completion model parameters (gpt-4o-mini)
    chat_params = AzureOpenAIVectorizerParameters(
        resource_url=config["AZURE_OPENAI_ENDPOINT"],
        deployment_name=config["AZURE_OPENAI_GPT_MINI_DEPLOYMENT"],
        model_name=config["AZURE_OPENAI_GPT_MINI_DEPLOYMENT"],
    )

    # Ingestion parameters with Content Understanding
    ai_services_endpoint = config.get("AZURE_AI_SERVICES_ENDPOINT", "")
    if not ai_services_endpoint:
        console.print("[red]Error:[/red] AZURE_AI_SERVICES_ENDPOINT is not set.")
        sys.exit(1)

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

    # Blob source parameters
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

    result = index_client.create_or_update_knowledge_source(knowledge_source)
    console.print(f"[green]Knowledge Source created:[/green] {result.name}")
    return result.name


def poll_ingestion_status(index_client: SearchIndexClient, ks_name: str) -> None:
    """Poll the knowledge source ingestion status until complete."""
    console.print(f"\nPolling ingestion status for [cyan]{ks_name}[/cyan]...")

    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        try:
            status = index_client.get_knowledge_source_status(ks_name)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not get status:[/yellow] {e}")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        sync_status = getattr(status, "synchronization_status", None)
        items_processed = getattr(status, "items_processed", 0)
        items_failed = getattr(status, "items_failed", 0)

        console.print(
            f"  [{attempt}/{MAX_POLL_ATTEMPTS}] "
            f"Status: [bold]{sync_status}[/bold] | "
            f"Processed: {items_processed} | Failed: {items_failed}"
        )

        if sync_status and sync_status.lower() in ("completed", "succeeded", "failed", "stopped"):
            console.print(f"[green]Ingestion finished with status:[/green] {sync_status}")
            return

        if sync_status and sync_status.lower() not in ("active", "creating", "running", "inprogress", "in_progress", "queued"):
            console.print(f"[yellow]Unexpected status:[/yellow] {sync_status}")
            return

        time.sleep(POLL_INTERVAL_SECONDS)

    console.print("[yellow]Polling timed out. Check the Azure portal for status.[/yellow]")


def create_knowledge_base(
    index_client: SearchIndexClient, config: dict, ks_name: str
) -> str:
    """Create a Knowledge Base referencing the knowledge source."""
    kb_name = config["KNOWLEDGE_BASE_NAME"]

    console.print(f"\nCreating Knowledge Base [cyan]{kb_name}[/cyan]...")

    # Chat completion model for query planning
    chat_params = AzureOpenAIVectorizerParameters(
        resource_url=config["AZURE_OPENAI_ENDPOINT"],
        deployment_name=config["AZURE_OPENAI_GPT_MINI_DEPLOYMENT"],
        model_name=config["AZURE_OPENAI_GPT_MINI_DEPLOYMENT"],
    )

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

    result = index_client.create_or_update_knowledge_base(knowledge_base)
    console.print(f"[green]Knowledge Base created:[/green] {result.name}")
    return result.name


def main() -> None:
    """Create Knowledge Source and Knowledge Base."""
    console.print("[bold]Azure AI Search — Knowledge Source & Base Setup[/bold]\n")

    config = load_config()

    search_endpoint = config["AZURE_SEARCH_ENDPOINT"]
    credential = DefaultAzureCredential()

    try:
        index_client = SearchIndexClient(
            endpoint=search_endpoint, credential=credential
        )
    except Exception as e:
        console.print(f"[red]Error creating SearchIndexClient:[/red] {e}")
        sys.exit(1)

    # Step 1: Create knowledge source
    ks_name = create_knowledge_source(index_client, config)

    # Step 2: Poll ingestion until complete
    poll_ingestion_status(index_client, ks_name)

    # Step 3: Create knowledge base
    kb_name = create_knowledge_base(index_client, config, ks_name)

    # Summary
    console.print("\n[bold green]Setup complete![/bold green]")
    console.print(f"  Knowledge Source: [cyan]{ks_name}[/cyan]")
    console.print(f"  Knowledge Base:   [cyan]{kb_name}[/cyan]")
    console.print(
        f"  MCP Endpoint:     [dim]{search_endpoint}/knowledgebases/{kb_name}/mcp[/dim]"
    )


if __name__ == "__main__":
    main()
