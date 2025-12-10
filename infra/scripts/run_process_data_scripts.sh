#!/bin/bash

# === Configuration ===
resourceGroupName="$1"
bicepFile="./../process_custom_data_scripts.bicep"

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
managedIdentityResourceId=$(az identity list --resource-group "$resourceGroupName" --query "[?starts_with(name, 'id-') && !starts_with(name, 'id-backend-')].id | [0]" -o tsv)

# === Normalize managedIdentityResourceId (necessary for compatibility in Git Bash on Windows) ===
managedIdentityResourceId=$(echo "$managedIdentityResourceId" | sed -E 's|.*(/subscriptions/)|\1|')

# === Get the location of the first SQL Server in the resource group ===
sqlServerLocation=$(az sql server list --resource-group "$resourceGroupName" --query "[0].location" -o tsv)

# === Retrieve the principal ID of the first user-assigned identity with name starting with 'id-' ===
managedIdentityClientId=$(az identity list --resource-group "$resourceGroupName" --query "[?starts_with(name, 'id-') && !starts_with(name, 'id-backend-')].clientId | [0]" -o tsv)

# === Check for VNet deployment ===
echo "Checking for VNet deployment in resource group: $resourceGroupName"
vnetResourceId=$(az network vnet list --resource-group "$resourceGroupName" --query "[0].id" -o tsv)

# === Get resource group location ===
rgLocation=$(az group show --name "$resourceGroupName" --query "location" -o tsv)

# === Find storage account (always needed) ===
echo "Looking for storage account in resource group..."
storageAccountResourceId=$(az storage account list --resource-group "$resourceGroupName" --query "[0].id" -o tsv)

if [ -z "$storageAccountResourceId" ]; then
    echo "ERROR: No storage account found in resource group $resourceGroupName"
    exit 1
else
    echo "Using storage account: $storageAccountResourceId"
fi

if [ -z "$vnetResourceId" ]; then
    echo "No VNet found in resource group. Private networking is disabled."
    enablePrivateNetworking="false"
    subnetId=""
    solutionLocation="$sqlServerLocation"
    echo "Using SQL Server location for solution: $solutionLocation"
else
    echo "VNet found: $vnetResourceId"
    echo "VNet detected - enabling private networking."
    enablePrivateNetworking="true"
    solutionLocation="$rgLocation"
    echo "Using Resource Group location for solution: $solutionLocation"
    
    # === Find the deployment script subnet ===
    echo "Looking for deployment-scripts subnet..."
    subnetId=$(az network vnet subnet list --resource-group "$resourceGroupName" --vnet-name $(basename "$vnetResourceId") --query "[?name=='deployment-scripts'].id | [0]" -o tsv)
    
    if [ -z "$subnetId" ]; then
        echo "Warning: deployment-scripts subnet not found. Checking for alternative subnet names..."
        # Try alternative names
        subnetId=$(az network vnet subnet list --resource-group "$resourceGroupName" --vnet-name $(basename "$vnetResourceId") --query "[?contains(name, 'deployment') || contains(name, 'script')].id | [0]" -o tsv)
    fi
    
    if [ -z "$subnetId" ]; then
        echo "Warning: No deployment script subnet found. Private networking will be disabled for deployment script."
        enablePrivateNetworking="false"
        subnetId=""
    else
        echo "Using deployment script subnet: $subnetId"
    fi
fi

# === Validate that all required resources were found ===
if [[ -z "$keyVaultName" || -z "$solutionLocation" || -z "$managedIdentityResourceId" || ! "$managedIdentityResourceId" =~ ^/subscriptions/ ]]; then
  echo "ERROR: Could not find required resources in resource group $resourceGroupName or managedIdentityResourceId is invalid"
  exit 1
fi

echo "Using Solution Location: $solutionLocation"
echo "Using Key Vault: $keyVaultName"
echo "Using Managed Identity Resource Id: $managedIdentityResourceId"
echo "Using Managed Identity ClientId Id: $managedIdentityClientId"
echo "Enable Private Networking: $enablePrivateNetworking"
echo "Subnet ID: $subnetId"
echo "Storage Account Resource ID: $storageAccountResourceId"

# === Deploy resources using the specified Bicep template ===
echo "Deploying Bicep template..."

# Build base parameters
deploymentParams="solutionLocation=$solutionLocation keyVaultName=$keyVaultName managedIdentityResourceId=$managedIdentityResourceId managedIdentityClientId=$managedIdentityClientId storageAccount=$storageAccountResourceId"

# Add networking parameters if VNet is deployed
if [ "$enablePrivateNetworking" = "true" ]; then
    deploymentParams="$deploymentParams enablePrivateNetworking=true"
    if [ -n "$subnetId" ]; then
        deploymentParams="$deploymentParams subnetId=$subnetId"
    fi
else
    deploymentParams="$deploymentParams enablePrivateNetworking=false"
fi

echo "Deployment parameters: $deploymentParams"

# MSYS_NO_PATHCONV disables path conversion in Git Bash for Windows
MSYS_NO_PATHCONV=1 az deployment group create \
  --resource-group "$resourceGroupName" \
  --template-file "$bicepFile" \
  --parameters $deploymentParams

echo "Deployment completed."
