@description('Required. Name of the AI Services project.')
param name string

@description('Required. The location of the Project resource.')
param location string = resourceGroup().location

@description('Optional. The description of the AI Foundry project to create. Defaults to the project name.')
param desc string = name

@description('Required. Name of the existing Cognitive Services resource to create the AI Foundry project in.')
param aiServicesName string

@description('Optional. Tags to be applied to the resources.')
param tags object = {}

@description('Optional. Use this parameter to use an existing AI project resource ID from different resource group')
param existingFoundryProjectResourceId string = ''

// // Extract components from existing AI Project Resource ID if provided
var useExistingProject = !empty(existingFoundryProjectResourceId)
var existingProjName = useExistingProject ? last(split(existingFoundryProjectResourceId, '/')) : ''
var existingProjEndpoint = useExistingProject ? format('https://{0}.services.ai.azure.com/api/projects/{1}', aiServicesName, existingProjName) : ''

// Reference to cognitive service in current resource group for new projects
resource cogServiceReference 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: aiServicesName
}

// Create new AI project only if not reusing existing one
resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = if(!useExistingProject) {
  parent: cogServiceReference
  name: name
  tags: tags
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: desc
    displayName: name
  }
}

resource searchIndexDataReaderRoleDefinition 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
}

// ========== Search Service to AI Services Role Assignment ========== //
resource searchServiceToAiServicesRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiProject.id, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  properties: {
    roleDefinitionId: searchIndexDataReaderRoleDefinition.id
    principalId: aiProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

@description('This is the built-in Search Service Contributor role.')
resource searchServiceContributorRoleDefinition 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  name: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
}

resource searchServiceContributorRoleAssignmentToAIFP 'Microsoft.Authorization/roleAssignments@2022-04-01' =  {
  name: guid(aiProject.id, searchServiceContributorRoleDefinition.id)
  properties: {
    roleDefinitionId: searchServiceContributorRoleDefinition.id
    principalId: aiProject.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

@description('AI Project metadata including name, resource ID, and API endpoint.')
output aiProjectInfo aiProjectOutputType = {
  name: useExistingProject ? existingProjName : aiProject.name
  resourceId: useExistingProject ? existingFoundryProjectResourceId : aiProject.id
  apiEndpoint: useExistingProject ? existingProjEndpoint : aiProject!.properties.endpoints['AI Foundry API']
}

@export()
@description('Output type representing AI project information.')
type aiProjectOutputType = {
  @description('Required. Name of the AI project.')
  name: string

  @description('Required. Resource ID of the AI project.')
  resourceId: string

  @description('Required. API endpoint for the AI project.')
  apiEndpoint: string
}
