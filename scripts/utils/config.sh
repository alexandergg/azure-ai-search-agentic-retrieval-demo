#!/usr/bin/env bash
# Shared configuration loader for the demo scripts.
# Sources .env and provides helper functions for catalog.json parsing.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
CATALOG_FILE="$PROJECT_ROOT/data/catalog.json"

# ── Colors ──────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m' # No Color

# ── Output helpers ──────────────────────────────────────────────────────────────
log_ok()   { echo -e "  ${GREEN}✓${NC} $*"; }
log_warn() { echo -e "  ${YELLOW}⚠${NC} $*"; }
log_err()  { echo -e "  ${RED}✗${NC} $*"; }
log_info() { echo -e "  ${DIM}$*${NC}"; }
log_bold() { echo -e "${BOLD}$*${NC}"; }

# ── Check jq ────────────────────────────────────────────────────────────────────
check_jq() {
    if ! command -v jq &>/dev/null; then
        log_err "jq is required but not installed. Install it: https://jqlang.github.io/jq/"
        exit 1
    fi
}

# ── Load .env ───────────────────────────────────────────────────────────────────
load_config() {
    if [[ ! -f "$ENV_FILE" ]]; then
        log_err ".env file not found at $ENV_FILE. Run 01_deploy_infra.ps1 first."
        exit 1
    fi

    # Source .env (skip comments and empty lines)
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Skip comments and empty lines
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        # Export the variable
        export "$line"
    done < "$ENV_FILE"

    # Validate required variables
    local required_vars=(
        "AZURE_SEARCH_ENDPOINT"
        "PROJECT_ENDPOINT"
        "PROJECT_RESOURCE_ID"
        "AZURE_AI_SERVICES_ENDPOINT"
    )

    local missing=()
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            missing+=("$var")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_err "Missing required environment variables: ${missing[*]}"
        echo "Please check your .env file."
        exit 1
    fi

    # Set defaults for optional variables
    : "${AZURE_OPENAI_EMBEDDING_DEPLOYMENT:=text-embedding-3-large}"
    : "${AZURE_OPENAI_EMBEDDING_MODEL:=text-embedding-3-large}"
    : "${AZURE_OPENAI_GPT_DEPLOYMENT:=gpt-4o}"
    : "${AZURE_OPENAI_GPT_MINI_DEPLOYMENT:=gpt-4o-mini}"
    : "${AZURE_STORAGE_CONNECTION_STRING:=}"
    : "${AZURE_STORAGE_CONTAINER_NAME:=documents}"
    : "${FOUNDRY_PROJECT_ENDPOINT:=}"
    : "${FOUNDRY_PROJECT_RESOURCE_ID:=}"
    : "${AGENT_MODEL:=gpt-4o}"
    : "${KNOWLEDGE_SOURCE_NAME:=demo-blob-ks}"
    : "${KNOWLEDGE_BASE_NAME:=demo-knowledge-base}"
    : "${AZURE_SEARCH_API_KEY:=}"

    export AZURE_OPENAI_EMBEDDING_DEPLOYMENT AZURE_OPENAI_EMBEDDING_MODEL
    export AZURE_OPENAI_GPT_DEPLOYMENT AZURE_OPENAI_GPT_MINI_DEPLOYMENT
    export AZURE_STORAGE_CONNECTION_STRING AZURE_STORAGE_CONTAINER_NAME
    export FOUNDRY_PROJECT_ENDPOINT FOUNDRY_PROJECT_RESOURCE_ID
    export AGENT_MODEL KNOWLEDGE_SOURCE_NAME KNOWLEDGE_BASE_NAME AZURE_SEARCH_API_KEY
}

# ── Load catalog ────────────────────────────────────────────────────────────────
load_catalog() {
    check_jq
    if [[ ! -f "$CATALOG_FILE" ]]; then
        log_err "Catalog not found at $CATALOG_FILE"
        exit 1
    fi
    cat "$CATALOG_FILE"
}

# ── Get Azure access token ──────────────────────────────────────────────────────
get_search_token() {
    az account get-access-token --resource "https://search.azure.com" --query accessToken -o tsv 2>/dev/null
}

get_management_token() {
    az account get-access-token --resource "https://management.azure.com" --query accessToken -o tsv 2>/dev/null
}
