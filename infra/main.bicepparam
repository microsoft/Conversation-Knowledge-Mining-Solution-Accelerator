using './main.bicep'

param environmentName = readEnvironmentVariable('AZURE_ENV_NAME', 'env_name')
param contentUnderstandingLocation = readEnvironmentVariable('AZURE_ENV_CU_LOCATION', 'West US')
param secondaryLocation = readEnvironmentVariable('AZURE_ENV_SECONDARY_LOCATION', 'eastus2')
param deploymentType = readEnvironmentVariable('AZURE_ENV_MODEL_DEPLOYMENT_TYPE', 'GlobalStandard')
param gptModelName = readEnvironmentVariable('AZURE_ENV_MODEL_NAME', 'gpt-4o-mini')
param gptDeploymentCapacity = int(readEnvironmentVariable('AZURE_ENV_MODEL_CAPACITY', '30'))
param embeddingModel = readEnvironmentVariable('AZURE_ENV_EMBEDDING_MODEL_NAME', 'text-embedding-ada-002')
param embeddingDeploymentCapacity = int(readEnvironmentVariable('AZURE_ENV_EMBEDDING_MODEL_CAPACITY', '80'))
