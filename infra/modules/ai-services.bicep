@description('Azure region for all resources.')
param location string

@description('Prefix used to generate resource names.')
param namePrefix string

var aiServicesName = '${namePrefix}-aiservices'
var foundryProjectName = '${namePrefix}-foundry-project'

// ── AI Services account (also hosts the Foundry project + model deployments) ──
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: aiServicesName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: aiServicesName
    publicNetworkAccess: 'Enabled'
    allowProjectManagement: true
  }
}

// ── GPT-4o deployment (for the Foundry agent) ──
resource gpt4oDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: aiServices
  name: 'gpt-4o'
  sku: {
    name: 'GlobalStandard'
    capacity: 30
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-11-20'
    }
  }
}

// ── Foundry Project (CognitiveServices-based, for AIProjectClient + MCP) ──
resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiServices
  name: foundryProjectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
  dependsOn: [gpt4oDeployment]
}

output aiServicesName string = aiServices.name
output aiServicesId string = aiServices.id
output aiServicesEndpoint string = aiServices.properties.endpoint
output foundryProjectName string = foundryProject.name
output foundryProjectResourceId string = foundryProject.id
output foundryProjectEndpoint string = 'https://${aiServicesName}.services.ai.azure.com/api/projects/${foundryProjectName}'
output foundryProjectPrincipalId string = foundryProject.identity.principalId
