#!/usr/bin/env bash
# Upload PDF documents to Azure Blob Storage, organized by category.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils/config.sh"

echo -e "${BOLD}Azure Blob Storage — Multi-Category Document Upload${NC}\n"

load_config
CATALOG=$(load_catalog)

if [[ -z "${AZURE_STORAGE_CONNECTION_STRING:-}" ]]; then
    log_err "AZURE_STORAGE_CONNECTION_STRING is not set."
    exit 1
fi

MAX_FILE_SIZE=$((128 * 1024 * 1024))  # 128 MB

total_uploaded=0
total_failed=0
total_skipped=0

categories=$(echo "$CATALOG" | jq -c '.categories[]')

while IFS= read -r category; do
    category_name=$(echo "$category" | jq -r '.display_name')
    container_name=$(echo "$category" | jq -r '.container_name')
    local_path=$(echo "$category" | jq -r '.local_path')
    docs_dir="$PROJECT_ROOT/$local_path"

    # Find PDF files
    if [[ ! -d "$docs_dir" ]]; then
        echo -e "  ${YELLOW}Directory not found: ${docs_dir}${NC}"
        continue
    fi

    pdf_files=()
    while IFS= read -r -d '' f; do
        pdf_files+=("$f")
    done < <(find "$docs_dir" -maxdepth 1 -iname "*.pdf" -print0 | sort -z)

    if [[ ${#pdf_files[@]} -eq 0 ]]; then
        echo -e "  ${YELLOW}No PDF files found in ${docs_dir}${NC}"
        continue
    fi

    echo -e "\n  ${BOLD}${category_name}${NC}: ${#pdf_files[@]} file(s) → container ${CYAN}${container_name}${NC}"

    # Create container if it doesn't exist
    az storage container create \
        --name "$container_name" \
        --connection-string "$AZURE_STORAGE_CONNECTION_STRING" \
        --output none 2>/dev/null || true

    for filepath in "${pdf_files[@]}"; do
        blob_name=$(basename "$filepath")
        file_size=$(stat -f%z "$filepath" 2>/dev/null || stat --printf="%s" "$filepath" 2>/dev/null || echo 0)

        if [[ "$file_size" -gt "$MAX_FILE_SIZE" ]]; then
            size_mb=$(echo "scale=1; $file_size / 1048576" | bc 2>/dev/null || echo "?")
            echo -e "  ${YELLOW}⚠ Skipping ${blob_name} (${size_mb} MB) — exceeds 128 MB extraction limit${NC}"
            total_skipped=$((total_skipped + 1))
            continue
        fi

        echo -e "  Uploading ${blob_name}..."
        if az storage blob upload \
            --container-name "$container_name" \
            --file "$filepath" \
            --name "$blob_name" \
            --overwrite \
            --connection-string "$AZURE_STORAGE_CONNECTION_STRING" \
            --output none 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} ${blob_name}"
            total_uploaded=$((total_uploaded + 1))
        else
            echo -e "  ${RED}✗ Failed to upload ${blob_name}${NC}"
            total_failed=$((total_failed + 1))
        fi
    done
done <<< "$categories"

echo -e "\n${GREEN}Upload complete:${NC} ${total_uploaded} succeeded, ${total_failed} failed, ${total_skipped} skipped (oversized)."
