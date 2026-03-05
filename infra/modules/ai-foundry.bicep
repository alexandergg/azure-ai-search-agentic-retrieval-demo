@description('Azure region for all resources.')
param location string

@description('Prefix used to generate resource names.')
param namePrefix string

@description('Resource ID of the Key Vault.')
param keyVaultId string

@description('Resource ID of the Storage Account.')
param storageAccountId string

@description('Resource ID of the AI Search service.')
param searchServiceId string

@description('Resource ID of the Azure AI Services account.')
param openAiId string

@description('Endpoint URL of the Azure AI Services account.')
param openAiEndpoint string

@description('Endpoint URL of the AI Search service.')
param searchEndpoint string

var hubName = '${namePrefix}-hub'
var projectName = '${namePrefix}-project'

resource hub 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = {
  name: hubName
  location: location
  kind: 'Hub'
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: '${namePrefix} AI Hub'
    keyVault: keyVaultId
    storageAccount: storageAccountId
  }
}

resource openAiConnection 'Microsoft.MachineLearningServices/workspaces/connections@2024-10-01' = {
  parent: hub
  name: '${namePrefix}-openai-connection'
  properties: {
    category: 'AzureOpenAI'
    authType: 'AAD'
    isSharedToAll: true
    target: openAiEndpoint
    metadata: {
      ApiType: 'Azure'
      ResourceId: openAiId
    }
  }
}

resource searchConnection 'Microsoft.MachineLearningServices/workspaces/connections@2024-10-01' = {
  parent: hub
  name: '${namePrefix}-search-connection'
  properties: {
    category: 'CognitiveSearch'
    authType: 'AAD'
    isSharedToAll: true
    target: searchEndpoint
    metadata: {
      ResourceId: searchServiceId
    }
  }
}

resource project 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = {
  name: projectName
  location: location
  kind: 'Project'
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: '${namePrefix} AI Project'
    hubResourceId: hub.id
  }
}

output hubName string = hub.name
output projectName string = project.name
output projectId string = project.id
output projectEndpoint string = project.properties.agentsEndpointUri
