@description('Azure region for all resources.')
param location string

@description('Prefix used to generate resource names.')
param namePrefix string

@description('Azure AD tenant ID for the Key Vault.')
param tenantId string

var keyVaultName = '${namePrefix}-kv'

resource keyVault 'Microsoft.KeyVault/vaults@2024-04-01-preview' = {
  name: keyVaultName
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenantId
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: null
    enableRbacAuthorization: true
    accessPolicies: []
  }
}

output keyVaultName string = keyVault.name
output keyVaultId string = keyVault.id
output keyVaultUri string = keyVault.properties.vaultUri
