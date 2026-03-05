#!/usr/bin/env python3
"""Download sample documents from public URLs into category folders.

Cross-platform alternative to 00_download_documents.sh.
Reads catalog.json and downloads all documents with remote source URLs.
"""

import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CATALOG_FILE = PROJECT_ROOT / "data" / "catalog.json"


def main():
    if not CATALOG_FILE.exists():
        print(f"Error: Catalog not found at {CATALOG_FILE}")
        sys.exit(1)

    with open(CATALOG_FILE, encoding="utf-8") as f:
        catalog = json.load(f)

    # Collect remote documents
    remote_docs = []
    for category in catalog["categories"]:
        for doc in category["documents"]:
            if doc["source"] != "local":
                remote_docs.append({
                    "category_name": category["name"],
                    "display_name": category["display_name"],
                    "local_path": category["local_path"],
                    "filename": doc["filename"],
                    "source": doc["source"],
                    "description": doc["description"],
                })

    if not remote_docs:
        print("No remote documents to download.")
        return

    print(f"Found {len(remote_docs)} remote document(s) to download\n")

    downloaded = 0
    skipped = 0
    failed = 0

    for doc in remote_docs:
        dest_dir = PROJECT_ROOT / doc["local_path"]
        dest_dir.mkdir(parents=True, exist_ok=True)
        filepath = dest_dir / doc["filename"]

        if filepath.exists():
            print(f"  ⏭ {doc['filename']} already exists in {doc['category_name']}/ — skipping")
            skipped += 1
            continue

        print(f"  ⬇ Downloading {doc['filename']}...")
        print(f"    {doc['description']}")

        try:
            req = urllib.request.Request(doc["source"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as response:
                data = response.read()
                filepath.write_bytes(data)

            size_mb = filepath.stat().st_size / (1024 * 1024)
            print(f"  ✓ {doc['filename']} → {doc['category_name']}/ ({size_mb:.1f} MB)")
            downloaded += 1
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            print(f"  ✗ Failed to download {doc['filename']}: {e}")
            filepath.unlink(missing_ok=True)
            failed += 1

    print(f"\nDownload complete: {downloaded} succeeded, {failed} failed, {skipped} skipped (already exist).")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
