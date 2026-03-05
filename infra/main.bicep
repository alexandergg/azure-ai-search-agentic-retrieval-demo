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

// ── Azure AI Services (hosts all model deployments + Foundry project) ──
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

// ── AI Foundry (Hub + Project) ──
module aiFoundry 'modules/ai-foundry.bicep' = {
  name: '${namePrefix}-ai-foundry'
  params: {
    location: location
    namePrefix: namePrefix
    keyVaultId: keyVault.outputs.keyVaultId
    storageAccountId: storage.outputs.storageAccountId
    searchServiceId: aiSearch.outputs.searchServiceId
    openAiId: aiServices.outputs.aiServicesId
    openAiEndpoint: aiServices.outputs.aiServicesEndpoint
    searchEndpoint: aiSearch.outputs.searchEndpoint
  }
}

// ── RBAC: Foundry Project MI → Search (Search Index Data Reader) ──
resource foundryProjectToSearchReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, namePrefix, 'foundry-search-datareader')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '1407120a-92aa-4202-b7e9-c0e197c71c8f') // Search Index Data Reader
    principalId: aiServices.outputs.foundryProjectPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── RBAC: Foundry Project MI → Search (Search Service Contributor, for KB MCP) ──
resource foundryProjectToSearchContrib 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, namePrefix, 'foundry-search-contrib')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7ca78c08-252a-4471-8644-bb5ff32d4ba0') // Search Service Contributor
    principalId: aiServices.outputs.foundryProjectPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── Container Registry ──
module containerRegistry 'modules/container-registry.bicep' = {
  name: '${namePrefix}-acr'
  params: {
    location: location
    namePrefix: namePrefix
  }
}

// ── Container Apps ──
module containerApps 'modules/container-apps.bicep' = {
  name: '${namePrefix}-container-apps'
  params: {
    location: location
    namePrefix: namePrefix
    acrLoginServer: containerRegistry.outputs.acrLoginServer
    acrName: containerRegistry.outputs.acrName
  }
}

// ── Outputs ──
output storageAccountName string = storage.outputs.storageAccountName
output storageConnectionString string = storage.outputs.connectionString
output keyVaultName string = keyVault.outputs.keyVaultName
output keyVaultUri string = keyVault.outputs.keyVaultUri
output searchServiceName string = aiSearch.outputs.searchServiceName
output searchEndpoint string = aiSearch.outputs.searchEndpoint
output hubName string = aiFoundry.outputs.hubName
output projectName string = aiFoundry.outputs.projectName
output projectResourceId string = aiFoundry.outputs.projectId
output projectEndpoint string = aiFoundry.outputs.projectEndpoint
output aiServicesName string = aiServices.outputs.aiServicesName
output aiServicesEndpoint string = aiServices.outputs.aiServicesEndpoint
output foundryProjectName string = aiServices.outputs.foundryProjectName
output foundryProjectEndpoint string = aiServices.outputs.foundryProjectEndpoint
output foundryProjectResourceId string = aiServices.outputs.foundryProjectResourceId
output acrName string = containerRegistry.outputs.acrName
output acrLoginServer string = containerRegistry.outputs.acrLoginServer
output containerAppsUrl string = containerApps.outputs.appUrl
