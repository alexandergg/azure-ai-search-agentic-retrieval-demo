#!/usr/bin/env bash
# Clean up all demo resources: blobs, knowledge bases/sources, indexes,
# indexers, skillsets, data sources, MCP connections.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils/config.sh"

SEARCH_API_VERSION="2025-11-01-preview"
CONNECTION_ARM_API_VERSION="2025-10-01-preview"
MCP_CONNECTION_NAME="demofiq-kb-mcp-connection"

echo -e "${BOLD}Azure AI Search + Storage — Full Cleanup${NC}\n"

load_config
CATALOG=$(load_catalog)
TOKEN=$(get_search_token)
MGMT_TOKEN=$(get_management_token)

# ── Helper: delete search resource ──────────────────────────────────────────────
delete_search_resource() {
    local resource_type="$1"  # e.g., "knowledgebases", "knowledgesources", "indexes", "indexers", "skillsets", "datasources"
    local name="$2"
    local label="$3"

    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
        "${AZURE_SEARCH_ENDPOINT}/${resource_type}/${name}?api-version=${SEARCH_API_VERSION}" \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "Content-Type: application/json")

    if [[ "$http_code" -ge 200 && "$http_code" -lt 300 ]]; then
        echo -e "  ${RED}✗${NC} ${label}: ${name}"
        return 0
    elif [[ "$http_code" == "404" ]]; then
        return 0
    else
        log_warn "${label} delete returned HTTP ${http_code}: ${name}"
        return 0
    fi
}

# ── Helper: list search resources ───────────────────────────────────────────────
list_search_names() {
    local resource_type="$1"
    curl -s -X GET \
        "${AZURE_SEARCH_ENDPOINT}/${resource_type}?api-version=${SEARCH_API_VERSION}" \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "Content-Type: application/json" 2>/dev/null \
        | jq -r '.value[]?.name // empty' 2>/dev/null || true
}

# ── Inventory ───────────────────────────────────────────────────────────────────
echo -e "${BOLD}Scanning resources...${NC}"

kb_names=$(list_search_names "knowledgebases")
ks_names=$(list_search_names "knowledgesources")
indexer_names=$(list_search_names "indexers")
skillset_names=$(list_search_names "skillsets")
ds_names=$(list_search_names "datasources")
index_names=$(list_search_names "indexes")

kb_count=$(echo "$kb_names" | grep -c . 2>/dev/null || echo 0)
ks_count=$(echo "$ks_names" | grep -c . 2>/dev/null || echo 0)
indexer_count=$(echo "$indexer_names" | grep -c . 2>/dev/null || echo 0)
skillset_count=$(echo "$skillset_names" | grep -c . 2>/dev/null || echo 0)
ds_count=$(echo "$ds_names" | grep -c . 2>/dev/null || echo 0)
index_count=$(echo "$index_names" | grep -c . 2>/dev/null || echo 0)

# Count blobs
blob_count=0
if [[ -n "${AZURE_STORAGE_CONNECTION_STRING:-}" ]]; then
    container_names=$(echo "$CATALOG" | jq -r '.categories[].container_name')
    while IFS= read -r container_name; do
        [[ -z "$container_name" ]] && continue
        count=$(az storage blob list \
            --container-name "$container_name" \
            --connection-string "$AZURE_STORAGE_CONNECTION_STRING" \
            --query "length(@)" -o tsv 2>/dev/null || echo 0)
        blob_count=$((blob_count + count))
    done <<< "$container_names"
fi

# Check MCP connection
mcp_conn_exists=0
if [[ -n "${PROJECT_RESOURCE_ID:-}" ]]; then
    mcp_http_code=$(curl -s -o /dev/null -w "%{http_code}" -X GET \
        "https://management.azure.com${PROJECT_RESOURCE_ID}/connections/${MCP_CONNECTION_NAME}?api-version=${CONNECTION_ARM_API_VERSION}" \
        -H "Authorization: Bearer ${MGMT_TOKEN}" 2>/dev/null || echo 0)
    [[ "$mcp_http_code" == "200" ]] && mcp_conn_exists=1
fi

echo -e "  Knowledge Bases:   ${CYAN}${kb_count}${NC}"
echo -e "  Knowledge Sources: ${CYAN}${ks_count}${NC}"
echo -e "  Indexers:          ${CYAN}${indexer_count}${NC}"
echo -e "  Skillsets:         ${CYAN}${skillset_count}${NC}"
echo -e "  Data Sources:      ${CYAN}${ds_count}${NC}"
echo -e "  Indexes:           ${CYAN}${index_count}${NC}"
echo -e "  Blobs:             ${CYAN}${blob_count}${NC}"
echo -e "  MCP Connection:    ${CYAN}${mcp_conn_exists}${NC}"

total=$((kb_count + ks_count + indexer_count + skillset_count + ds_count + index_count + blob_count + mcp_conn_exists))
if [[ "$total" -eq 0 ]]; then
    echo -e "\n${GREEN}Nothing to clean up — all clear!${NC}"
    exit 0
fi

# ── Confirm ─────────────────────────────────────────────────────────────────────
echo ""
read -rp "$(echo -e "${RED}${BOLD}Delete ALL listed resources? [y/N]${NC} ")" confirm
if [[ "${confirm,,}" != "y" ]]; then
    echo -e "${DIM}Aborted.${NC}"
    exit 0
fi

echo ""
deleted=0

# ── Delete (order matters) ──────────────────────────────────────────────────────

echo -e "${BOLD}Deleting Knowledge Bases...${NC}"
while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    delete_search_resource "knowledgebases" "$name" "Knowledge Base"
    deleted=$((deleted + 1))
done <<< "$kb_names"

echo -e "${BOLD}Deleting Knowledge Sources...${NC}"
while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    delete_search_resource "knowledgesources" "$name" "Knowledge Source"
    deleted=$((deleted + 1))
done <<< "$ks_names"

echo -e "${BOLD}Deleting Indexers...${NC}"
while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    delete_search_resource "indexers" "$name" "Indexer"
    deleted=$((deleted + 1))
done <<< "$indexer_names"

echo -e "${BOLD}Deleting Skillsets...${NC}"
while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    delete_search_resource "skillsets" "$name" "Skillset"
    deleted=$((deleted + 1))
done <<< "$skillset_names"

echo -e "${BOLD}Deleting Data Sources...${NC}"
while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    delete_search_resource "datasources" "$name" "Data Source"
    deleted=$((deleted + 1))
done <<< "$ds_names"

echo -e "${BOLD}Deleting Indexes...${NC}"
while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    delete_search_resource "indexes" "$name" "Index"
    deleted=$((deleted + 1))
done <<< "$index_names"

echo -e "${BOLD}Deleting Blobs...${NC}"
if [[ -n "${AZURE_STORAGE_CONNECTION_STRING:-}" ]]; then
    container_names=$(echo "$CATALOG" | jq -r '.categories[].container_name')
    legacy_container="${AZURE_STORAGE_CONTAINER_NAME:-documents}"

    # Add legacy container if not already in list
    if ! echo "$container_names" | grep -qx "$legacy_container"; then
        container_names="$container_names"$'\n'"$legacy_container"
    fi

    while IFS= read -r container_name; do
        [[ -z "$container_name" ]] && continue
        blob_names=$(az storage blob list \
            --container-name "$container_name" \
            --connection-string "$AZURE_STORAGE_CONNECTION_STRING" \
            --query "[].name" -o tsv 2>/dev/null || true)

        while IFS= read -r blob_name; do
            [[ -z "$blob_name" ]] && continue
            if az storage blob delete \
                --container-name "$container_name" \
                --name "$blob_name" \
                --connection-string "$AZURE_STORAGE_CONNECTION_STRING" \
                --output none 2>/dev/null; then
                echo -e "  ${RED}✗${NC} Blob: ${container_name}/${blob_name}"
                deleted=$((deleted + 1))
            fi
        done <<< "$blob_names"
    done <<< "$container_names"
else
    log_warn "No storage connection string — skipping blob cleanup."
fi

echo -e "${BOLD}Deleting MCP Connection...${NC}"
if [[ "$mcp_conn_exists" -eq 1 && -n "${PROJECT_RESOURCE_ID:-}" ]]; then
    mcp_del_code=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE \
        "https://management.azure.com${PROJECT_RESOURCE_ID}/connections/${MCP_CONNECTION_NAME}?api-version=${CONNECTION_ARM_API_VERSION}" \
        -H "Authorization: Bearer ${MGMT_TOKEN}" 2>/dev/null || echo 0)

    if [[ "$mcp_del_code" -ge 200 && "$mcp_del_code" -lt 300 ]]; then
        echo -e "  ${RED}✗${NC} MCP Connection: ${MCP_CONNECTION_NAME}"
        deleted=$((deleted + 1))
    elif [[ "$mcp_del_code" == "404" ]]; then
        echo -e "  ${DIM}MCP Connection not found (already deleted)${NC}"
    else
        log_warn "MCP connection delete returned ${mcp_del_code}"
    fi
fi

echo -e "\n${GREEN}${BOLD}Cleanup complete!${NC} ${deleted} resources deleted."
