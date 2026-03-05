#!/usr/bin/env bash
# Download sample documents from public URLs into category folders.
#
# Reads catalog.json and downloads all documents with remote source URLs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils/config.sh"

echo -e "${BOLD}Document Catalog — Download Remote Documents${NC}\n"

CATALOG=$(load_catalog)

# Collect remote documents
remote_docs=$(echo "$CATALOG" | jq -c '
    [.categories[] | . as $cat |
     .documents[] | select(.source != "local") |
     {category_name: $cat.name, local_path: $cat.local_path, filename: .filename, source: .source, description: .description}]')

count=$(echo "$remote_docs" | jq 'length')

if [[ "$count" -eq 0 ]]; then
    echo -e "${YELLOW}No remote documents to download.${NC}"
    exit 0
fi

echo -e "Found ${BOLD}${count}${NC} remote document(s) to download\n"

downloaded=0
skipped=0
failed=0

for i in $(seq 0 $((count - 1))); do
    doc=$(echo "$remote_docs" | jq -c ".[$i]")
    category_name=$(echo "$doc" | jq -r '.category_name')
    local_path=$(echo "$doc" | jq -r '.local_path')
    filename=$(echo "$doc" | jq -r '.filename')
    source_url=$(echo "$doc" | jq -r '.source')
    description=$(echo "$doc" | jq -r '.description')

    dest_dir="$PROJECT_ROOT/$local_path"
    mkdir -p "$dest_dir"
    filepath="$dest_dir/$filename"

    if [[ -f "$filepath" ]]; then
        echo -e "  ${DIM}⏭ ${filename} already exists in ${category_name}/ — skipping${NC}"
        skipped=$((skipped + 1))
        continue
    fi

    echo -e "  ⬇ Downloading ${filename}..."
    echo -e "    ${description}"
    if curl -fSL --progress-bar --connect-timeout 60 -o "$filepath" "$source_url" 2>&1; then
        file_size=$(stat -f%z "$filepath" 2>/dev/null || stat --printf="%s" "$filepath" 2>/dev/null || echo 0)
        file_size_mb=$(echo "scale=1; $file_size / 1048576" | bc 2>/dev/null || echo "?")
        echo -e "  ${GREEN}✓${NC} ${filename} → ${category_name}/ (${file_size_mb} MB)"
        downloaded=$((downloaded + 1))
    else
        echo -e "  ${RED}✗ Failed to download ${filename}${NC}"
        rm -f "$filepath"
        failed=$((failed + 1))
    fi
done

echo -e "\n${GREEN}Download complete:${NC} ${downloaded} succeeded, ${failed} failed, ${skipped} skipped (already exist)."

if [[ "$failed" -gt 0 ]]; then
    exit 1
fi
