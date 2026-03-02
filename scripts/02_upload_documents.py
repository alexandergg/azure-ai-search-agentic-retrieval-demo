"""Upload PDF documents to Azure Blob Storage."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from azure.storage.blob import BlobServiceClient
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from utils.config import load_config

console = Console()


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
    """Upload all PDFs from data/sample-docs/ to Azure Blob Storage."""
    connection_string = config.get("AZURE_STORAGE_CONNECTION_STRING", "")
    container_name = config.get("AZURE_STORAGE_CONTAINER_NAME", "documents")

    if not connection_string:
        console.print("[red]Error:[/red] AZURE_STORAGE_CONNECTION_STRING is not set.")
        sys.exit(1)

    # Resolve sample-docs path relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    docs_dir = os.path.join(script_dir, "..", "data", "sample-docs")
    docs_dir = os.path.normpath(docs_dir)

    pdf_files = find_pdf_files(docs_dir)
    if not pdf_files:
        console.print(f"[yellow]No PDF files found in {docs_dir}[/yellow]")
        return

    console.print(f"Found [bold]{len(pdf_files)}[/bold] PDF file(s) in {docs_dir}")

    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    except Exception as e:
        console.print(f"[red]Error connecting to Azure Blob Storage:[/red] {e}")
        sys.exit(1)

    # Create container if it doesn't exist
    container_client = blob_service_client.get_container_client(container_name)
    try:
        container_client.get_container_properties()
        console.print(f"Container [cyan]{container_name}[/cyan] already exists.")
    except Exception:
        console.print(f"Creating container [cyan]{container_name}[/cyan]...")
        container_client.create_container()

    uploaded = 0
    failed = 0
    skipped = 0

    MAX_FILE_SIZE = 128 * 1024 * 1024  # 128 MB — Standard tier limit for document extraction

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Uploading documents...", total=len(pdf_files))

        for filepath in pdf_files:
            blob_name = os.path.basename(filepath)
            file_size = os.path.getsize(filepath)
            progress.update(task, description=f"Uploading {blob_name}...")

            if file_size > MAX_FILE_SIZE:
                size_mb = file_size / 1024 / 1024
                console.print(
                    f"[yellow]⚠ Skipping {blob_name} ({size_mb:.1f} MB) — "
                    f"exceeds 128 MB extraction limit for Standard tier[/yellow]"
                )
                skipped += 1
                progress.advance(task)
                continue

            try:
                with open(filepath, "rb") as f:
                    container_client.upload_blob(
                        name=blob_name, data=f, overwrite=True
                    )
                uploaded += 1
            except Exception as e:
                console.print(f"[red]Failed to upload {blob_name}:[/red] {e}")
                failed += 1
            progress.advance(task)

    console.print()
    console.print(
        f"[green]Upload complete:[/green] {uploaded} succeeded, {failed} failed, {skipped} skipped (oversized)."
    )


if __name__ == "__main__":
    console.print("[bold]Azure Blob Storage Document Upload[/bold]\n")
    config = load_config()
    upload_documents(config)
