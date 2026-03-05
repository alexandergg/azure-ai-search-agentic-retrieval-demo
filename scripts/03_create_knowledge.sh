#!/usr/bin/env bash
# Create Knowledge Sources and Knowledge Base for multi-domain agentic retrieval.
# Uses Azure AI Search REST API (2025-11-01-preview).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/utils/config.sh"

SEARCH_API_VERSION="2025-11-01-preview"
POLL_INTERVAL=15
MAX_POLL_ATTEMPTS=80

# Parse arguments
EXTRACTION_MODE="standard"
VERBOSE=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)    EXTRACTION_MODE="$2"; shift 2 ;;
        -v|--verbose) VERBOSE=true; shift ;;
        *)         echo "Usage: $0 [--mode minimal|standard] [-v|--verbose]"; exit 1 ;;
    esac
done

echo -e "${BOLD}Azure AI Search — Multi-Domain Knowledge Source & Base Setup${NC}"

load_config
CATALOG=$(load_catalog)
TOKEN=$(get_search_token)

echo -e "  Search endpoint:     ${DIM}${AZURE_SEARCH_ENDPOINT}${NC}"

categories=$(echo "$CATALOG" | jq -c '.categories[]')
cat_count=$(echo "$CATALOG" | jq '.categories | length')
echo -e "  Categories:          ${CYAN}${cat_count}${NC}"

echo "$CATALOG" | jq -r '.categories[] | "    • \(.display_name) → \(.knowledge_source_name)"'

# ── Create Knowledge Source ─────────────────────────────────────────────────────
create_knowledge_source() {
    local ks_name="$1"
    local container_name="$2"
    local ks_description="$3"
    local mode="$4"

    if [[ "$mode" == "standard" ]]; then
        mode_label="standard (Content Understanding — OCR, layout, semantic chunking)"
    else
        mode_label="minimal (built-in text extraction)"
    fi

    echo -e "\n${BOLD}Creating Knowledge Source${NC} ${CYAN}${ks_name}${NC}"
    echo -e "  Container:           ${DIM}${container_name}${NC}"
    echo -e "  Description:         ${DIM}${ks_description:0:80}...${NC}"
    echo -e "  Extraction mode:     ${DIM}${mode_label}${NC}"
    echo -e "  Embedding model:     ${DIM}${AZURE_OPENAI_EMBEDDING_DEPLOYMENT}${NC}"
    echo -e "  Chat model:          ${DIM}${AZURE_OPENAI_GPT_MINI_DEPLOYMENT}${NC}"

    # Build ingestion parameters
    local disable_image_verb="true"
    local chat_model_block=""
    local ai_services_block=""

    if [[ "$mode" == "standard" ]]; then
        disable_image_verb="false"
        chat_model_block=$(cat <<CHATEOF
            ,"chatCompletionModel": {
                "azureOpenAIParameters": {
                    "resourceUrl": "${AZURE_AI_SERVICES_ENDPOINT}",
                    "deploymentName": "${AZURE_OPENAI_GPT_MINI_DEPLOYMENT}",
                    "modelName": "${AZURE_OPENAI_GPT_MINI_DEPLOYMENT}"
                }
            }
CHATEOF
)
        ai_services_block=$(cat <<AIEOF
            ,"aiServices": {
                "uri": "${AZURE_AI_SERVICES_ENDPOINT}"
            }
AIEOF
)
    fi

    local body
    body=$(cat <<EOF
{
    "name": "${ks_name}",
    "description": "${ks_description}",
    "azureBlobParameters": {
        "connectionString": "${AZURE_STORAGE_CONNECTION_STRING}",
        "containerName": "${container_name}",
        "isAdlsGen2": false,
        "ingestionParameters": {
            "contentExtractionMode": "${mode}",
            "disableImageVerbalization": ${disable_image_verb},
            "embeddingModel": {
                "azureOpenAIParameters": {
                    "resourceUrl": "${AZURE_AI_SERVICES_ENDPOINT}",
                    "deploymentName": "${AZURE_OPENAI_EMBEDDING_DEPLOYMENT}",
                    "modelName": "${AZURE_OPENAI_EMBEDDING_MODEL}"
                }
            }${chat_model_block}${ai_services_block}
        }
    }
}
EOF
)

    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "  ${DIM}Request payload:${NC}"
        echo "$body" | jq . 2>/dev/null || echo "$body"
    fi

    echo -e "\n  Calling ${BOLD}create_or_update_knowledge_source${NC}..."

    local response
    response=$(curl -s -w "\n%{http_code}" -X PUT \
        "${AZURE_SEARCH_ENDPOINT}/knowledgesources/${ks_name}?api-version=${SEARCH_API_VERSION}" \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "Content-Type: application/json" \
        -d "$body")

    local http_code
    http_code=$(echo "$response" | tail -1)
    local resp_body
    resp_body=$(echo "$response" | sed '$d')

    if [[ "$http_code" -ge 200 && "$http_code" -lt 300 ]]; then
        log_ok "Knowledge Source created: ${ks_name}"
    else
        log_err "Failed to create knowledge source (HTTP ${http_code})"
        echo "$resp_body" | jq . 2>/dev/null || echo "$resp_body"
        exit 1
    fi

    if [[ "$VERBOSE" == "true" ]]; then
        echo "$resp_body" | jq . 2>/dev/null || echo "$resp_body"
    fi

    echo -e "  ${DIM}Behind the scenes, Azure AI Search now provisions:${NC}"
    echo -e "  ${DIM}  1. Data Source Connection → points to blob container${NC}"
    echo -e "  ${DIM}  2. Skillset → Content Understanding skill${NC}"
    echo -e "  ${DIM}  3. Search Index → with vector fields for embeddings${NC}"
    echo -e "  ${DIM}  4. Indexer → orchestrates the pipeline (runs automatically)${NC}"
}

# ── Poll Ingestion Status ───────────────────────────────────────────────────────
poll_ingestion_status() {
    local ks_name="$1"

    echo -e "\n${BOLD}Monitor ingestion${NC} for ${CYAN}${ks_name}${NC}"

    for attempt in $(seq 1 $MAX_POLL_ATTEMPTS); do
        local response
        response=$(curl -s -X GET \
            "${AZURE_SEARCH_ENDPOINT}/knowledgesources/${ks_name}/status?api-version=${SEARCH_API_VERSION}" \
            -H "Authorization: Bearer ${TOKEN}" \
            -H "Content-Type: application/json" 2>/dev/null || echo "{}")

        local sync_status
        sync_status=$(echo "$response" | jq -r '.synchronizationStatus // "unknown"')

        local cur_processed cur_failed
        cur_processed=$(echo "$response" | jq -r '.currentSynchronizationState.itemsUpdatesProcessed // 0')
        cur_failed=$(echo "$response" | jq -r '.currentSynchronizationState.itemsUpdatesFailed // 0')

        echo -e "  [${attempt}/${MAX_POLL_ATTEMPTS}] KS sync=${BOLD}${sync_status}${NC} | current: ${cur_processed} ok / ${cur_failed} fail"

        # Check indexer status
        local indexers_response
        indexers_response=$(curl -s -X GET \
            "${AZURE_SEARCH_ENDPOINT}/indexers?api-version=${SEARCH_API_VERSION}" \
            -H "Authorization: Bearer ${TOKEN}" \
            -H "Content-Type: application/json" 2>/dev/null || echo '{"value":[]}')

        local ingestion_done=false

        # Check if KS sync is in a terminal state
        case "${sync_status,,}" in
            completed|succeeded|failed|stopped) ingestion_done=true ;;
        esac

        # Check indexer last run
        if [[ "$ingestion_done" == "false" ]]; then
            local indexer_status
            indexer_status=$(echo "$indexers_response" | jq -r '
                [.value[] | .lastResult // empty |
                 select(.status == "success" and (.itemsProcessed // 0) > 0)] | length')
            if [[ "${indexer_status:-0}" -gt 0 ]]; then
                ingestion_done=true
            fi

            # Also check: indexer succeeded with 0 items (already indexed)
            local indexer_done_no_items
            indexer_done_no_items=$(echo "$indexers_response" | jq -r '
                [.value[] | select(.lastResult.status == "success")] | length')
            local exec_history_count
            exec_history_count=$(echo "$indexers_response" | jq -r '
                [.value[] | (.executionHistory // []) | length] | add // 0')
            if [[ "${indexer_done_no_items:-0}" -gt 0 && "${exec_history_count:-0}" -gt 0 ]]; then
                ingestion_done=true
            fi
        fi

        if [[ "$ingestion_done" == "true" ]]; then
            local last_end
            last_end=$(echo "$response" | jq -r '.lastSynchronizationState.endTime // empty')
            if [[ -n "$last_end" ]]; then
                local last_start last_processed last_failed_count
                last_start=$(echo "$response" | jq -r '.lastSynchronizationState.startTime // "?"')
                last_processed=$(echo "$response" | jq -r '.lastSynchronizationState.itemsUpdatesProcessed // 0')
                last_failed_count=$(echo "$response" | jq -r '.lastSynchronizationState.itemsUpdatesFailed // 0')
                echo -e "\n  ${GREEN}Ingestion finished:${NC} ${sync_status}"
                echo -e "    Started:   ${last_start}"
                echo -e "    Ended:     ${last_end}"
                echo -e "    Processed: ${last_processed}"
                echo -e "    Failed:    ${last_failed_count}"
            else
                echo -e "\n  ${GREEN}Ingestion finished with status:${NC} ${sync_status}"
            fi
            return
        fi

        case "${sync_status,,}" in
            active|creating|running|inprogress|in_progress|queued|unknown) ;;
            *)
                echo -e "  ${YELLOW}Unexpected status:${NC} ${sync_status}"
                return
                ;;
        esac

        sleep "$POLL_INTERVAL"
    done

    echo -e "${YELLOW}Polling timed out. Check the Azure portal for status.${NC}"
}

# ── Create Knowledge Base ───────────────────────────────────────────────────────
create_knowledge_base() {
    local ks_names_json="$1"  # JSON array of knowledge source names

    local kb_name
    kb_name=$(echo "$CATALOG" | jq -r '.knowledge_base.name // "demo-knowledge-base"')
    local kb_description
    kb_description=$(echo "$CATALOG" | jq -r '.knowledge_base.description // "Multi-domain knowledge base"')
    local retrieval_instructions
    retrieval_instructions=$(echo "$CATALOG" | jq -r '.knowledge_base.retrieval_instructions // ""')
    local answer_instructions
    answer_instructions=$(echo "$CATALOG" | jq -r '.knowledge_base.answer_instructions // ""')

    echo -e "\n${BOLD}Creating Knowledge Base${NC} ${CYAN}${kb_name}${NC}"
    echo "$ks_names_json" | jq -r '.[] | "  Knowledge Source:    \(.)"'
    echo -e "  Reasoning model:     ${DIM}${AZURE_OPENAI_GPT_MINI_DEPLOYMENT}${NC}"
    echo -e "  Output mode:         ${DIM}ExtractiveData${NC}"
    echo -e "  Reasoning effort:    ${DIM}minimal (no LLM query planning)${NC}"

    # Build knowledge sources references array
    local ks_refs
    ks_refs=$(echo "$ks_names_json" | jq '[.[] | {name: .}]')

    local body
    body=$(jq -n \
        --arg name "$kb_name" \
        --arg desc "$kb_description" \
        --arg retrieval "$retrieval_instructions" \
        --arg answer "$answer_instructions" \
        --arg resource_url "$AZURE_AI_SERVICES_ENDPOINT" \
        --arg deployment "$AZURE_OPENAI_GPT_MINI_DEPLOYMENT" \
        --argjson ks_refs "$ks_refs" \
        '{
            name: $name,
            description: $desc,
            knowledgeSources: $ks_refs,
            models: [{
                azureOpenAIParameters: {
                    resourceUrl: $resource_url,
                    deploymentName: $deployment,
                    modelName: $deployment
                }
            }],
            retrievalReasoningEffort: { kind: "minimal" },
            outputMode: "extractiveData",
            retrievalInstructions: $retrieval,
            answerInstructions: $answer
        }')

    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "  ${DIM}Request payload:${NC}"
        echo "$body" | jq .
    fi

    echo -e "  Calling ${BOLD}create_or_update_knowledge_base${NC}..."

    local response
    response=$(curl -s -w "\n%{http_code}" -X PUT \
        "${AZURE_SEARCH_ENDPOINT}/knowledgebases/${kb_name}?api-version=${SEARCH_API_VERSION}" \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "Content-Type: application/json" \
        -d "$body")

    local http_code
    http_code=$(echo "$response" | tail -1)
    local resp_body
    resp_body=$(echo "$response" | sed '$d')

    if [[ "$http_code" -ge 200 && "$http_code" -lt 300 ]]; then
        log_ok "Knowledge Base created: ${kb_name}"
    else
        log_err "Failed to create knowledge base (HTTP ${http_code})"
        echo "$resp_body" | jq . 2>/dev/null || echo "$resp_body"
        exit 1
    fi

    # Summary
    local mcp_endpoint="${AZURE_SEARCH_ENDPOINT}/knowledgebases/${kb_name}/mcp"
    echo ""
    echo -e "  ══════════════════════════════════════════════════════"
    echo -e "  ${GREEN}${BOLD}Multi-domain setup complete!${NC}"
    echo -e "  Knowledge Sources:"
    echo "$ks_names_json" | jq -r '.[] | "    • \(.)"'
    echo -e "  Knowledge Base:   ${CYAN}${kb_name}${NC}"
    echo -e "  MCP Endpoint:     ${DIM}${mcp_endpoint}${NC}"
    echo -e "  ══════════════════════════════════════════════════════"
}

# ── Main ────────────────────────────────────────────────────────────────────────

# Step 1: Create knowledge sources (one per category)
echo -e "\n${BOLD}Step 1 · Create ${cat_count} Knowledge Sources${NC}"
echo -e "${DIM}Each category gets its own blob container, indexer, and search index.${NC}"

ks_names="[]"
i=0

echo "$CATALOG" | jq -c '.categories[]' | while IFS= read -r category; do
    i=$((i + 1))
    ks_name=$(echo "$category" | jq -r '.knowledge_source_name')
    container_name=$(echo "$category" | jq -r '.container_name')
    ks_description=$(echo "$category" | jq -r '.description')
    display_name=$(echo "$category" | jq -r '.display_name')

    echo -e "\n────────────────────────────────────────────────────────────"
    echo -e "  [${i}/${cat_count}] Category: ${BOLD}${display_name}${NC}"

    create_knowledge_source "$ks_name" "$container_name" "$ks_description" "$EXTRACTION_MODE"

    # Append to ks_names file (workaround for subshell)
    echo "$ks_name" >> /tmp/demofiq_ks_names.txt
done

# Read ks_names back
ks_names_json="[]"
if [[ -f /tmp/demofiq_ks_names.txt ]]; then
    ks_names_json=$(jq -R -s 'split("\n") | map(select(length > 0))' < /tmp/demofiq_ks_names.txt)
    rm -f /tmp/demofiq_ks_names.txt
fi

# Step 2: Poll ingestion for all knowledge sources
echo -e "\n${BOLD}Step 2 · Monitor ingestion for $(echo "$ks_names_json" | jq 'length') Knowledge Sources${NC}"

# Refresh token before polling (may take a while)
TOKEN=$(get_search_token)

echo "$ks_names_json" | jq -r '.[]' | while IFS= read -r ks_name; do
    poll_ingestion_status "$ks_name"
done

# Step 3: Create knowledge base
echo -e "\n${BOLD}Step 3 · Create Knowledge Base${NC}"
echo -e "${DIM}Referencing $(echo "$ks_names_json" | jq 'length') knowledge sources for cross-domain agentic retrieval.${NC}"

# Refresh token
TOKEN=$(get_search_token)

create_knowledge_base "$ks_names_json"
