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

// ── Azure AI Services (Content Understanding) ──
module aiServices 'modules/ai-services.bicep' = {
  name: '${namePrefix}-aiservices'
  params: {
    location: location
    namePrefix: namePrefix
  }
}

// ── RBAC: AI Search → AI Services (Cognitive Services User) ──
resource searchToAiServicesRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, namePrefix, 'search-aiservices-coguser')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908') // Cognitive Services User
    principalId: aiSearch.outputs.searchPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── RBAC: AI Search → OpenAI (Cognitive Services OpenAI User for embeddings) ──
resource searchToOpenAiRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, namePrefix, 'search-openai-coguser')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd') // Cognitive Services OpenAI User
    principalId: aiSearch.outputs.searchPrincipalId
    principalType: 'ServicePrincipal'
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
output aiServicesName string = aiServices.outputs.aiServicesName
output aiServicesEndpoint string = aiServices.outputs.aiServicesEndpoint
