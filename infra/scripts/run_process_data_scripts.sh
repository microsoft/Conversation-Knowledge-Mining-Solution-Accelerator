#!/bin/bash

# === Configuration ===
resourceGroupName="$1"
bicepFile="./../process_data_scripts.bicep"

# If resourcegroup not provided as an argument, get it from AZD environment
if [ -z "$resourceGroupName" ]; then
    resourceGroupName=$(azd env get-value RESOURCE_GROUP_NAME 2>/dev/null)
fi

# Validate the value was eventually set
if [ -z "$resourceGroupName" ]; then
    echo "Usage: $0 <resourceGroupName>"
    echo "ERROR: resourceGroupName not provided and not found in AZD environment."
    exit 1
fi

# === Ensure user is logged in to Azure CLI ===
az account show > /dev/null 2>&1 || az login

echo "Fetching Key Vault and Managed Identity from resource group: $resourceGroupName"

# === Retrieve the first Key Vault name from the specified resource group ===
keyVaultName=$(az keyvault list --resource-group "$resourceGroupName" --query "[0].name" -o tsv)

# === Retrieve the ID of the first user-assigned identity with name starting with 'id-' ===
managedIdentityResourceId=$(az identity list --resource-group "$resourceGroupName" --query "[?starts_with(name, 'id-')].id | [0]" -o tsv)

# === Normalize managedIdentityResourceId (necessary for compatibility in Git Bash on Windows) ===
managedIdentityResourceId=$(echo "$managedIdentityResourceId" | sed -E 's|.*(/subscriptions/)|\1|')

# === Get the location of the first SQL Server in the resource group ===
sqlServerLocation=$(az sql server list --resource-group "$resourceGroupName" --query "[0].location" -o tsv)

# === Retrieve the principal ID of the first user-assigned identity with name starting with 'id-' ===
managedIdentityClientId=$(az identity list --resource-group "$resourceGroupName" --query "[?starts_with(name, 'id-')].clientId | [0]" -o tsv)

# === Validate that all required resources were found ===
if [[ -z "$keyVaultName" || -z "$sqlServerLocation" || -z "$managedIdentityResourceId" || ! "$managedIdentityResourceId" =~ ^/subscriptions/ ]]; then
  echo "ERROR: Could not find required resources in resource group $resourceGroupName or managedIdentityResourceId is invalid"
  exit 1
fi

echo "Using SQL Server Location: $sqlServerLocation"
echo "Using Key Vault: $keyVaultName"
echo "Using Managed Identity Resource Id: $managedIdentityResourceId"
echo "Using Managed Identity ClientId Id: $managedIdentityClientId"

# === Deploy resources using the specified Bicep template ===
echo "Deploying Bicep template..."

# MSYS_NO_PATHCONV disables path conversion in Git Bash for Windows
MSYS_NO_PATHCONV=1 az deployment group create \
  --resource-group "$resourceGroupName" \
  --template-file "$bicepFile" \
  --parameters solutionLocation="$sqlServerLocation" keyVaultName="$keyVaultName" managedIdentityResourceId="$managedIdentityResourceId" managedIdentityClientId="$managedIdentityClientId"

echo "Deployment completed."
