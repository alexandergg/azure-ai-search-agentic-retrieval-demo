targetScope = 'resourceGroup'

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Prefix used to generate resource names.')
param namePrefix string = 'demofiq'

@description('Azure AD tenant ID for Key Vault.')
param tenantId string = subscription().tenantId

// ── Storage Account ──
module storage 'modules/storage.bicep' = {
  name: '${namePrefix}-storage'
  params: {
    location: location
    namePrefix: namePrefix
  }
}

// ── Key Vault ──
module keyVault 'modules/keyvault.bicep' = {
  name: '${namePrefix}-keyvault'
  params: {
    location: location
    namePrefix: namePrefix
    tenantId: tenantId
  }
}

// ── AI Search ──
module aiSearch 'modules/ai-search.bicep' = {
  name: '${namePrefix}-ai-search'
  params: {
    location: location
    namePrefix: namePrefix
  }
}

// ── Azure OpenAI ──
module openAi 'modules/openai.bicep' = {
  name: '${namePrefix}-openai'
  params: {
    location: location
    namePrefix: namePrefix
  }
}

// ── AI Foundry (Hub + Project) ──
module aiFoundry 'modules/ai-foundry.bicep' = {
  name: '${namePrefix}-ai-foundry'
  params: {
    location: location
    namePrefix: namePrefix
    keyVaultId: keyVault.outputs.keyVaultId
    storageAccountId: storage.outputs.storageAccountId
    searchServiceId: aiSearch.outputs.searchServiceId
    openAiId: openAi.outputs.openAiId
    openAiEndpoint: openAi.outputs.openAiEndpoint
    searchEndpoint: aiSearch.outputs.searchEndpoint
  }
}

// ── Outputs ──
output storageAccountName string = storage.outputs.storageAccountName
output storageConnectionString string = storage.outputs.connectionString
output keyVaultName string = keyVault.outputs.keyVaultName
output keyVaultUri string = keyVault.outputs.keyVaultUri
output searchServiceName string = aiSearch.outputs.searchServiceName
output searchEndpoint string = aiSearch.outputs.searchEndpoint
output openAiName string = openAi.outputs.openAiName
output openAiEndpoint string = openAi.outputs.openAiEndpoint
output hubName string = aiFoundry.outputs.hubName
output projectName string = aiFoundry.outputs.projectName
output projectResourceId string = aiFoundry.outputs.projectId
output projectEndpoint string = aiFoundry.outputs.projectEndpoint
