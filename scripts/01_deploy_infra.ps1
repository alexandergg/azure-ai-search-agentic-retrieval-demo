<#
.SYNOPSIS
    Deploys Azure infrastructure for the AI Foundry IQ demo.

.DESCRIPTION
    This script provisions all required Azure resources using Bicep, generates a
    .env file with deployment outputs, and assigns RBAC roles so the current user
    can interact with the deployed services.

.EXAMPLE
    .\scripts\01_deploy_infra.ps1

.NOTES
    Prerequisites: Azure CLI with Bicep extension, Python 3.10+, authenticated
    Azure session (az login).
#>

$ErrorActionPreference = "Stop"

# ── Helper ──────────────────────────────────────────────────────────────────────
function Write-Step  { param([string]$Msg) Write-Host "`n▶ $Msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$Msg) Write-Host "  ✓ $Msg" -ForegroundColor Green }
function Write-Warn  { param([string]$Msg) Write-Host "  ⚠ $Msg" -ForegroundColor Yellow }
function Write-Err   { param([string]$Msg) Write-Host "  ✗ $Msg" -ForegroundColor Red }

function Assert-ExitCode {
    param([string]$Step)
    if ($LASTEXITCODE -ne 0) {
        Write-Err "$Step failed (exit code $LASTEXITCODE)."
        throw "$Step failed."
    }
}

# ── Variables ───────────────────────────────────────────────────────────────────
$ResourceGroupName = "rg-demo-foundry-iq"
$Location          = "eastus2"
$NamePrefix        = "demofiq"
$ScriptDir         = $PSScriptRoot
$InfraPath         = Join-Path $ScriptDir "..\infra\main.bicep"
$ProjectRoot       = Join-Path $ScriptDir ".."
$EnvFilePath       = Join-Path $ProjectRoot ".env"

# ── 1. Validate prerequisites ──────────────────────────────────────────────────
Write-Step "Validating prerequisites"

# Azure CLI
try {
    $null = az --version 2>&1
    Assert-ExitCode "az --version"
    Write-Ok "Azure CLI installed"
} catch {
    Write-Err "Azure CLI is not installed. See https://aka.ms/installazurecli"
    exit 1
}

# Logged-in session
try {
    $null = az account show 2>&1
    Assert-ExitCode "az account show"
    Write-Ok "Azure CLI authenticated"
} catch {
    Write-Err "Not logged in. Run 'az login' first."
    exit 1
}

# Bicep
try {
    $null = az bicep version 2>&1
    Assert-ExitCode "az bicep version"
    Write-Ok "Bicep available"
} catch {
    Write-Err "Bicep not available. Run 'az bicep install'."
    exit 1
}

# Python
try {
    $null = python --version 2>&1
    Assert-ExitCode "python --version"
    Write-Ok "Python installed"
} catch {
    Write-Err "Python is not installed."
    exit 1
}

# Bicep template
if (-not (Test-Path $InfraPath)) {
    Write-Err "Bicep template not found at: $InfraPath"
    exit 1
}
Write-Ok "Bicep template found at $InfraPath"

# ── 2. Create resource group ───────────────────────────────────────────────────
Write-Step "Creating resource group '$ResourceGroupName' in '$Location'"

az group create --name $ResourceGroupName --location $Location --output none 2>&1
Assert-ExitCode "az group create"
Write-Ok "Resource group ready"

# ── 3. Deploy Bicep template ───────────────────────────────────────────────────
Write-Step "Deploying Bicep template (this may take several minutes)..."

# Use --query to extract outputs directly, avoiding JSON parse issues with stderr
az deployment group create `
    --resource-group $ResourceGroupName `
    --name           main `
    --template-file  $InfraPath `
    --parameters     location=$Location namePrefix=$NamePrefix `
    --output         none

Assert-ExitCode "az deployment group create"
Write-Ok "Deployment succeeded"

# ── 4. Extract deployment outputs ──────────────────────────────────────────────
Write-Step "Extracting deployment outputs"

# Query each output individually, suppressing stderr to avoid AutoRun noise
$searchEndpoint          = "$(az deployment group show --resource-group $ResourceGroupName --name main --query properties.outputs.searchEndpoint.value -o tsv 2>$null)".Trim()
$openAiEndpoint          = "$(az deployment group show --resource-group $ResourceGroupName --name main --query properties.outputs.openAiEndpoint.value -o tsv 2>$null)".Trim()
$storageConnectionString = "$(az deployment group show --resource-group $ResourceGroupName --name main --query properties.outputs.storageConnectionString.value -o tsv 2>$null)".Trim()
$projectEndpoint         = "$(az deployment group show --resource-group $ResourceGroupName --name main --query properties.outputs.projectEndpoint.value -o tsv 2>$null)".Trim()
$projectResourceId       = "$(az deployment group show --resource-group $ResourceGroupName --name main --query properties.outputs.projectResourceId.value -o tsv 2>$null)".Trim()
$searchServiceName       = "$(az deployment group show --resource-group $ResourceGroupName --name main --query properties.outputs.searchServiceName.value -o tsv 2>$null)".Trim()
$aiServicesEndpoint      = "$(az deployment group show --resource-group $ResourceGroupName --name main --query properties.outputs.aiServicesEndpoint.value -o tsv 2>$null)".Trim()
$foundryProjectEndpoint  = "$(az deployment group show --resource-group $ResourceGroupName --name main --query properties.outputs.foundryProjectEndpoint.value -o tsv 2>$null)".Trim()
$foundryProjectResourceId = "$(az deployment group show --resource-group $ResourceGroupName --name main --query properties.outputs.foundryProjectResourceId.value -o tsv 2>$null)".Trim()

# Get Search admin API key (needed for MCP tool auth)
$searchApiKey = "$(az search admin-key show --resource-group $ResourceGroupName --service-name $searchServiceName --query primaryKey -o tsv 2>$null)".Trim()

Write-Ok "Outputs extracted"

# ── 5. Generate .env file ──────────────────────────────────────────────────────
Write-Step "Generating .env file at $EnvFilePath"

$envContent = @"
# Azure AI Search
AZURE_SEARCH_ENDPOINT=$searchEndpoint

# Azure AI Foundry Project (ML Workspace — legacy, used by AgentsClient)
PROJECT_ENDPOINT=$projectEndpoint
PROJECT_RESOURCE_ID=$projectResourceId

# Azure AI Foundry Project (CognitiveServices — for AIProjectClient + MCP)
FOUNDRY_PROJECT_ENDPOINT=$foundryProjectEndpoint
FOUNDRY_PROJECT_RESOURCE_ID=$foundryProjectResourceId

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=$openAiEndpoint
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_OPENAI_EMBEDDING_MODEL=text-embedding-3-large
AZURE_OPENAI_GPT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_GPT_MINI_DEPLOYMENT=gpt-4o-mini

# Azure Storage
AZURE_STORAGE_CONNECTION_STRING=$storageConnectionString
AZURE_STORAGE_CONTAINER_NAME=documents

# Azure AI Search API Key (for legacy auth)
AZURE_SEARCH_API_KEY=$searchApiKey

# Azure AI Services (for Content Understanding)
AZURE_AI_SERVICES_ENDPOINT=$aiServicesEndpoint

# Agent configuration
AGENT_MODEL=gpt-4o
KNOWLEDGE_SOURCE_NAME=demo-blob-ks
KNOWLEDGE_BASE_NAME=demo-knowledge-base
"@

Set-Content -Path $EnvFilePath -Value $envContent -Encoding UTF8
Write-Ok ".env file written"

# ── 6. Assign RBAC roles ───────────────────────────────────────────────────────
Write-Step "Assigning RBAC roles to current user"

$currentUserObjectId = (az ad signed-in-user show --query id -o tsv 2>$null)
Assert-ExitCode "az ad signed-in-user show"
$currentUserObjectId = "$currentUserObjectId".Trim()
Write-Ok "Current user object ID: $currentUserObjectId"

$roleAssignments = @(
    @{ Role = "Search Service Contributor";    Scope = $searchServiceResourceId }
    @{ Role = "Search Index Data Contributor"; Scope = $searchServiceResourceId }
    @{ Role = "Search Index Data Reader";      Scope = $searchServiceResourceId }
)

foreach ($ra in $roleAssignments) {
    $roleName  = $ra.Role
    $roleScope = $ra.Scope

    if ([string]::IsNullOrWhiteSpace($roleScope)) {
        Write-Warn "Skipping '$roleName' — scope not available in deployment outputs"
        continue
    }

    try {
        Write-Host "  Assigning '$roleName'..." -ForegroundColor Gray
        $null = az role assignment create `
            --assignee-object-id   $currentUserObjectId `
            --assignee-principal-type User `
            --role                 $roleName `
            --scope                $roleScope `
            --output               none 2>$null

        if ($LASTEXITCODE -ne 0) {
            Write-Warn "'$roleName' — may already be assigned (non-zero exit)"
        } else {
            Write-Ok "'$roleName' assigned"
        }
    } catch {
        Write-Warn "'$roleName' — skipped ($($_.Exception.Message))"
    }
}

# ── 6b. Assign RBAC roles to AI Foundry project managed identity ─────────────
Write-Step "Assigning RBAC roles to project managed identity"

$projectMiId = "$(az resource show --ids $projectResourceId --query identity.principalId -o tsv 2>$null)".Trim()
if (-not [string]::IsNullOrWhiteSpace($projectMiId)) {
    Write-Ok "ML Project MI: $projectMiId"
    $rgScope = "/subscriptions/$(az account show --query id -o tsv 2>$null)/resourceGroups/$ResourceGroupName"

    $miRoles = @(
        @{ Role = "Cognitive Services OpenAI Contributor"; Scope = $rgScope }
        @{ Role = "Azure AI Developer";                    Scope = $rgScope }
        @{ Role = "Search Index Data Reader";              Scope = $rgScope }
        @{ Role = "Search Service Contributor";            Scope = $rgScope }
    )

    foreach ($ra in $miRoles) {
        try {
            Write-Host "  Assigning '$($ra.Role)' to ML project MI..." -ForegroundColor Gray
            $null = az role assignment create `
                --assignee-object-id   $projectMiId `
                --assignee-principal-type ServicePrincipal `
                --role                 $ra.Role `
                --scope                $ra.Scope `
                --output               none 2>$null
        } catch {}
    }
    Write-Ok "ML Project MI roles assigned"
} else {
}

# ── 6c. Assign RBAC for Foundry (CognitiveServices) project MI ───────────────
Write-Step "Assigning RBAC roles to Foundry project managed identity"

$foundryProjectMiId = "$(az resource show --ids $foundryProjectResourceId --query identity.principalId -o tsv 2>$null)".Trim()
if (-not [string]::IsNullOrWhiteSpace($foundryProjectMiId)) {
    Write-Ok "Foundry Project MI: $foundryProjectMiId"
    $rgScope = "/subscriptions/$(az account show --query id -o tsv 2>$null)/resourceGroups/$ResourceGroupName"

    $foundryMiRoles = @(
        @{ Role = "Search Index Data Reader";    Scope = $rgScope }
        @{ Role = "Search Service Contributor";  Scope = $rgScope }
        @{ Role = "Cognitive Services User";     Scope = $rgScope }
    )

    foreach ($ra in $foundryMiRoles) {
        try {
            Write-Host "  Assigning '$($ra.Role)' to Foundry project MI..." -ForegroundColor Gray
            $null = az role assignment create `
                --assignee-object-id   $foundryProjectMiId `
                --assignee-principal-type ServicePrincipal `
                --role                 $ra.Role `
                --scope                $ra.Scope `
                --output               none 2>$null
        } catch {}
    }
    Write-Ok "Foundry Project MI roles assigned"
} else {
    Write-Warn "Could not get Foundry project MI — RBAC not assigned"
}

# ── 6d. Assign RBAC for current user on AI Services ──────────────────────────
Write-Step "Assigning AI Services roles to current user"

$rgScope = "/subscriptions/$(az account show --query id -o tsv 2>$null)/resourceGroups/$ResourceGroupName"
$userAiRoles = @(
    @{ Role = "Azure AI User";            Scope = $rgScope }
    @{ Role = "Azure AI Project Manager"; Scope = $rgScope }
)

foreach ($ra in $userAiRoles) {
    try {
        Write-Host "  Assigning '$($ra.Role)' to current user..." -ForegroundColor Gray
        $null = az role assignment create `
            --assignee-object-id   $currentUserObjectId `
            --assignee-principal-type User `
            --role                 $ra.Role `
            --scope                $ra.Scope `
            --output               none 2>$null
    } catch {}
}
Write-Ok "AI Services user roles assigned"

# ── 7. Summary ──────────────────────────────────────────────────────────────────Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Deployment Complete" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Resource Group:        $ResourceGroupName" -ForegroundColor White
Write-Host "  Location:              $Location" -ForegroundColor White
Write-Host "  Search Endpoint:       $searchEndpoint" -ForegroundColor White
Write-Host "  OpenAI Endpoint:       $openAiEndpoint" -ForegroundColor White
Write-Host "  AI Services Endpoint:  $aiServicesEndpoint" -ForegroundColor White
Write-Host "  Foundry Project:       $foundryProjectEndpoint" -ForegroundColor White
Write-Host "  .env File:             $EnvFilePath" -ForegroundColor White
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor Yellow
Write-Host "    1. pip install -r requirements.txt" -ForegroundColor White
Write-Host "    2. python scripts\02_upload_documents.py" -ForegroundColor White
Write-Host "    3. python scripts\03_create_knowledge.py" -ForegroundColor White
Write-Host "    4. python scripts\04_create_agent.py" -ForegroundColor White
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
