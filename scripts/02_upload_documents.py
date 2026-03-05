"""Upload PDF documents to Azure Blob Storage, organized by category."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from azure.storage.blob import BlobServiceClient
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from utils.config import load_config, load_catalog

console = Console()

MAX_FILE_SIZE = 128 * 1024 * 1024  # 128 MB — Standard tier limit


def find_pdf_files(base_dir: str) -> list[str]:
    """Find all PDF files in the given directory."""
    pdf_files = []
    if not os.path.isdir(base_dir):
        return pdf_files
    for filename in sorted(os.listdir(base_dir)):
        if filename.lower().endswith(".pdf"):
            pdf_files.append(os.path.join(base_dir, filename))
    return pdf_files


def upload_documents(config: dict) -> None:
    """Upload all PDFs from category folders to Azure Blob Storage."""
    connection_string = config.get("AZURE_STORAGE_CONNECTION_STRING", "")

    if not connection_string:
        console.print("[red]Error:[/red] AZURE_STORAGE_CONNECTION_STRING is not set.")
        sys.exit(1)

    catalog = load_catalog()
    project_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    except Exception as e:
        console.print(f"[red]Error connecting to Azure Blob Storage:[/red] {e}")
        sys.exit(1)

    total_uploaded = 0
    total_failed = 0
    total_skipped = 0

    for category in catalog["categories"]:
        display_name = category["display_name"]
        container_name = category["container_name"]
        local_path = category["local_path"]
        docs_dir = os.path.normpath(os.path.join(project_root, local_path))

        pdf_files = find_pdf_files(docs_dir)
        if not pdf_files:
            console.print(f"  [yellow]No PDF files found in {docs_dir}[/yellow]")
            continue

        console.print(
            f"\n  [bold]{display_name}[/bold]: {len(pdf_files)} file(s) → "
            f"container [cyan]{container_name}[/cyan]"
        )

        # Create container if it doesn't exist
        container_client = blob_service_client.get_container_client(container_name)
        try:
            container_client.get_container_properties()
        except Exception:
            container_client.create_container()

        for filepath in pdf_files:
            blob_name = os.path.basename(filepath)
            file_size = os.path.getsize(filepath)

            if file_size > MAX_FILE_SIZE:
                size_mb = file_size / 1024 / 1024
                console.print(
                    f"  [yellow]⚠ Skipping {blob_name} ({size_mb:.1f} MB) — "
                    f"exceeds 128 MB extraction limit[/yellow]"
                )
                total_skipped += 1
                continue

            console.print(f"  Uploading {blob_name}...")
            try:
                with open(filepath, "rb") as f:
                    container_client.upload_blob(name=blob_name, data=f, overwrite=True)
                console.print(f"  [green]✓[/green] {blob_name}")
                total_uploaded += 1
            except Exception as e:
                console.print(f"  [red]✗ Failed to upload {blob_name}:[/red] {e}")
                total_failed += 1

    console.print(
        f"\n[green]Upload complete:[/green] {total_uploaded} succeeded, "
        f"{total_failed} failed, {total_skipped} skipped (oversized)."
    )


if __name__ == "__main__":
    console.print("[bold]Azure Blob Storage — Multi-Category Document Upload[/bold]\n")
    config = load_config()
    upload_documents(config)
