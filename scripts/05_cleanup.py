"""Clean up all demo resources: blobs, knowledge bases/sources, indexes, indexers, skillsets, data sources, MCP connections."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import requests as http_requests

from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.storage.blob import ContainerClient
from rich.console import Console
from rich.prompt import Confirm

from utils.config import load_config

console = Console()

MCP_CONNECTION_NAME = "demofiq-kb-mcp-connection"


def cleanup_knowledge_bases(index_client: SearchIndexClient) -> int:
    """Delete all knowledge bases."""
    count = 0
    try:
        for kb in index_client.list_knowledge_bases():
            name = kb.name
            index_client.delete_knowledge_base(name)
            console.print(f"  [red]✗[/red] Knowledge Base: {name}")
            count += 1
    except Exception as e:
        console.print(f"  [yellow]Warning:[/yellow] {e}")
    return count


def cleanup_knowledge_sources(index_client: SearchIndexClient) -> int:
    """Delete all knowledge sources."""
    count = 0
    try:
        for ks in index_client.list_knowledge_sources():
            name = ks.name
            index_client.delete_knowledge_source(name)
            console.print(f"  [red]✗[/red] Knowledge Source: {name}")
            count += 1
    except Exception as e:
        console.print(f"  [yellow]Warning:[/yellow] {e}")
    return count


def cleanup_indexers(indexer_client: SearchIndexerClient) -> int:
    """Delete all indexers."""
    count = 0
    try:
        for name in indexer_client.get_indexer_names():
            indexer_client.delete_indexer(name)
            console.print(f"  [red]✗[/red] Indexer: {name}")
            count += 1
    except Exception as e:
        console.print(f"  [yellow]Warning:[/yellow] {e}")
    return count


def cleanup_skillsets(indexer_client: SearchIndexerClient) -> int:
    """Delete all skillsets."""
    count = 0
    try:
        for name in indexer_client.get_skillset_names():
            indexer_client.delete_skillset(name)
            console.print(f"  [red]✗[/red] Skillset: {name}")
            count += 1
    except Exception as e:
        console.print(f"  [yellow]Warning:[/yellow] {e}")
    return count


def cleanup_data_sources(indexer_client: SearchIndexerClient) -> int:
    """Delete all data source connections."""
    count = 0
    try:
        for name in indexer_client.get_data_source_connection_names():
            indexer_client.delete_data_source_connection(name)
            console.print(f"  [red]✗[/red] Data Source: {name}")
            count += 1
    except Exception as e:
        console.print(f"  [yellow]Warning:[/yellow] {e}")
    return count


def cleanup_indexes(index_client: SearchIndexClient) -> int:
    """Delete all search indexes."""
    count = 0
    try:
        for name in index_client.list_index_names():
            index_client.delete_index(name)
            console.print(f"  [red]✗[/red] Index: {name}")
            count += 1
    except Exception as e:
        console.print(f"  [yellow]Warning:[/yellow] {e}")
    return count


def cleanup_blobs(config: dict) -> int:
    """Delete all blobs in the documents container."""
    conn_str = config.get("AZURE_STORAGE_CONNECTION_STRING", "")
    container_name = config.get("AZURE_STORAGE_CONTAINER_NAME", "documents")

    if not conn_str:
        console.print("  [yellow]Warning:[/yellow] No storage connection string — skipping blob cleanup.")
        return 0

    count = 0
    try:
        container_client = ContainerClient.from_connection_string(conn_str, container_name)
        blobs = list(container_client.list_blobs())
        for blob in blobs:
            container_client.delete_blob(blob.name)
            console.print(f"  [red]✗[/red] Blob: {blob.name}")
            count += 1
    except Exception as e:
        console.print(f"  [yellow]Warning:[/yellow] {e}")
    return count


def cleanup_mcp_connection(config: dict, credential: DefaultAzureCredential) -> int:
    """Delete the RemoteTool project connection for MCP."""
    project_resource_id = config.get("PROJECT_RESOURCE_ID", "")
    if not project_resource_id:
        return 0

    count = 0
    try:
        token = credential.get_token("https://management.azure.com/.default").token
        url = (
            f"https://management.azure.com{project_resource_id}"
            f"/connections/{MCP_CONNECTION_NAME}?api-version=2025-10-01-preview"
        )
        resp = http_requests.delete(url, headers={"Authorization": f"Bearer {token}"})
        if resp.status_code in (200, 204):
            console.print(f"  [red]✗[/red] MCP Connection: {MCP_CONNECTION_NAME}")
            count = 1
        elif resp.status_code == 404:
            console.print(f"  [dim]MCP Connection not found (already deleted)[/dim]")
        else:
            console.print(f"  [yellow]Warning:[/yellow] MCP connection delete returned {resp.status_code}")
    except Exception as e:
        console.print(f"  [yellow]Warning:[/yellow] {e}")
    return count


def main() -> None:
    console.print("[bold]Azure AI Search + Storage — Full Cleanup[/bold]\n")

    config = load_config()
    credential = DefaultAzureCredential()
    search_endpoint = config["AZURE_SEARCH_ENDPOINT"]

    index_client = SearchIndexClient(endpoint=search_endpoint, credential=credential)
    indexer_client = SearchIndexerClient(endpoint=search_endpoint, credential=credential)

    # Inventory
    console.print("[bold]Scanning resources...[/bold]")
    kb_list = list(index_client.list_knowledge_bases())
    ks_list = list(index_client.list_knowledge_sources())
    indexer_names = indexer_client.get_indexer_names()
    skillset_names = indexer_client.get_skillset_names()
    ds_names = indexer_client.get_data_source_connection_names()
    index_names = list(index_client.list_index_names())

    conn_str = config.get("AZURE_STORAGE_CONNECTION_STRING", "")
    container_name = config.get("AZURE_STORAGE_CONTAINER_NAME", "documents")
    blob_count = 0
    if conn_str:
        try:
            cc = ContainerClient.from_connection_string(conn_str, container_name)
            blob_count = len(list(cc.list_blobs()))
        except Exception:
            pass

    # Check for MCP connection
    mcp_conn_exists = False
    project_resource_id = config.get("PROJECT_RESOURCE_ID", "")
    if project_resource_id:
        try:
            token = credential.get_token("https://management.azure.com/.default").token
            url = (
                f"https://management.azure.com{project_resource_id}"
                f"/connections/{MCP_CONNECTION_NAME}?api-version=2025-10-01-preview"
            )
            resp = http_requests.get(url, headers={"Authorization": f"Bearer {token}"})
            mcp_conn_exists = resp.status_code == 200
        except Exception:
            pass

    console.print(f"  Knowledge Bases:   [cyan]{len(kb_list)}[/cyan]")
    console.print(f"  Knowledge Sources: [cyan]{len(ks_list)}[/cyan]")
    console.print(f"  Indexers:          [cyan]{len(indexer_names)}[/cyan]")
    console.print(f"  Skillsets:         [cyan]{len(skillset_names)}[/cyan]")
    console.print(f"  Data Sources:      [cyan]{len(ds_names)}[/cyan]")
    console.print(f"  Indexes:           [cyan]{len(index_names)}[/cyan]")
    console.print(f"  Blobs:             [cyan]{blob_count}[/cyan]")
    console.print(f"  MCP Connection:    [cyan]{'1' if mcp_conn_exists else '0'}[/cyan]")

    total = len(kb_list) + len(ks_list) + len(indexer_names) + len(skillset_names) + len(ds_names) + len(index_names) + blob_count + (1 if mcp_conn_exists else 0)
    if total == 0:
        console.print("\n[green]Nothing to clean up — all clear![/green]")
        return

    console.print()
    if not Confirm.ask("[bold red]Delete ALL listed resources?[/bold red]", default=False):
        console.print("[dim]Aborted.[/dim]")
        return

    console.print()
    deleted = 0

    # Order matters: KB → KS → Indexers → Skillsets → Data Sources → Indexes → Blobs
    console.print("[bold]Deleting Knowledge Bases...[/bold]")
    deleted += cleanup_knowledge_bases(index_client)

    console.print("[bold]Deleting Knowledge Sources...[/bold]")
    deleted += cleanup_knowledge_sources(index_client)

    console.print("[bold]Deleting Indexers...[/bold]")
    deleted += cleanup_indexers(indexer_client)

    console.print("[bold]Deleting Skillsets...[/bold]")
    deleted += cleanup_skillsets(indexer_client)

    console.print("[bold]Deleting Data Sources...[/bold]")
    deleted += cleanup_data_sources(indexer_client)

    console.print("[bold]Deleting Indexes...[/bold]")
    deleted += cleanup_indexes(index_client)

    console.print("[bold]Deleting Blobs...[/bold]")
    deleted += cleanup_blobs(config)

    console.print("[bold]Deleting MCP Connection...[/bold]")
    deleted += cleanup_mcp_connection(config, credential)

    console.print(f"\n[bold green]Cleanup complete![/bold green] {deleted} resources deleted.")


if __name__ == "__main__":
    main()
