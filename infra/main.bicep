// Mariano's scraper: one Container Apps Job per location, twice-weekly cron, Blob Storage for state + output.
targetScope = 'resourceGroup'

param location string = resourceGroup().location
param prefix string = 'marianos'
@description('Full image reference already pushed to your ACR, e.g. myacr.azurecr.io/marianos-scraper:1.0.0')
param image string
@description('Name of an EXISTING Azure Container Registry in this resource group')
param acrName string
@description('Location ids from config/locations.yaml; one scheduled job is created per id')
param locations array = ['chicago-roosevelt']
@description('UTC cron. Default: Tuesday and Friday 08:00 UTC (twice weekly)')
param cron string = '0 8 * * 2,5'
@secure()
param proxyServer string = ''
@secure()
param proxyUsername string = ''
@secure()
param proxyPassword string = ''
@description('Optional Azure Key Vault secret URL for proxy server (if using Key Vault references)')
param keyVaultProxyServerUrl string = ''

var storageName = toLower(replace('${prefix}st${uniqueString(resourceGroup().id)}', '-', ''))
var useProxy = !empty(proxyServer) || !empty(keyVaultProxyServerUrl)

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = { name: acrName }

resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-id'
  location: location
}

resource sa 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: take(storageName, 24)
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: { allowBlobPublicAccess: false, minimumTlsVersion: 'TLS1_2', supportsHttpsTrafficOnly: true }
}

resource blobSvc 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: sa
  name: 'default'
  properties: { deleteRetentionPolicy: { enabled: true, days: 14 } }
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobSvc
  name: 'marianos-scraper'
}

var blobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var acrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource raStorage 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: sa
  name: guid(sa.id, uami.id, blobDataContributor)
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobDataContributor)
  }
}

resource raAcr 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, uami.id, acrPull)
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPull)
  }
}

resource logs 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: '${prefix}-logs'
  location: location
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${prefix}-env'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

var baseEnv = [
  { name: 'AZURE_STORAGE_ACCOUNT_URL', value: sa.properties.primaryEndpoints.blob }
  { name: 'AZURE_CLIENT_ID', value: uami.properties.clientId }
  { name: 'MARIANOS_STORAGE', value: 'azure' }
]
var proxyEnv = useProxy ? [
  { name: 'PROXY_SERVER', secretRef: 'proxy-server' }
  { name: 'PROXY_USERNAME', secretRef: 'proxy-username' }
  { name: 'PROXY_PASSWORD', secretRef: 'proxy-password' }
] : []
var proxySecrets = useProxy ? concat(
  !empty(keyVaultProxyServerUrl) ? [{ name: 'proxy-server', keyVaultUrl: keyVaultProxyServerUrl, identity: uami.id }] : [{ name: 'proxy-server', value: proxyServer }],
  [{ name: 'proxy-username', value: proxyUsername }, { name: 'proxy-password', value: proxyPassword }]
) : []

resource jobs 'Microsoft.App/jobs@2024-03-01' = [for loc in locations: {
  name: take('${prefix}-${loc}', 32)
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${uami.id}': {} } }
  dependsOn: [raAcr, raStorage]
  properties: {
    environmentId: env.id
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 28800
      replicaRetryLimit: 0
      scheduleTriggerConfig: { cronExpression: cron, parallelism: 1, replicaCompletionCount: 1 }
      registries: [{ server: acr.properties.loginServer, identity: uami.id }]
      secrets: proxySecrets
    }
    template: {
      containers: [{
        name: 'scraper'
        image: image
        args: ['run', '--location', loc]
        resources: { cpu: json('2.0'), memory: '4Gi' }
        env: concat(baseEnv, proxyEnv, [{ name: 'CODE_VERSION', value: image }])
      }]
    }
  }
}]

// Log Analytics Alert Rule for Failed Job Executions or non-published run_final status
resource alertRule 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: '${prefix}-scraper-failure-alert'
  location: location
  properties: {
    displayName: 'Mariano Scraper Failure or Rejected Run Alert'
    enabled: true
    source: {
      query: '''
        ContainerAppConsoleLogs_CL
        | where Log_s has "run_final" and (Log_s has "status\":\"rejected\"" or Log_s has "status\":\"interrupted\"" or Log_s has "run_failed")
        | summarize Count = count() by bin(TimeGenerated, 1h), Computer
      '''
      dataSourceId: logs.id
    }
    schedule: {
      frequencyInMinutes: 60
      timeWindowInMinutes: 60
    }
    trigger: {
      operator: 'GreaterThan'
      threshold: 0
    }
    actions: {}
  }
}

output storageAccount string = sa.name
output jobNames array = [for (loc, i) in locations: jobs[i].name]
