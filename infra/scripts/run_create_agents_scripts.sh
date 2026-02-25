#!/bin/bash
set -e
echo "Started the agent creation script setup..."

# Variables
projectEndpoint="$1"
solutionName="$2"
gptModelName="$3"
aiFoundryResourceId="$4"
apiAppName="$5"
aiSearchConnectionName="$6"
aiSearchIndex="$7"
resourceGroup="$8"

# Global variables to track original network access states for AI Foundry
original_foundry_public_access=""
aif_resource_group=""
aif_account_resource_id=""

# Function to enable public network access temporarily for AI Foundry
enable_foundry_public_access() {
	if [ -n "$aiFoundryResourceId" ] && [ "$aiFoundryResourceId" != "null" ]; then
		aif_account_resource_id="$aiFoundryResourceId"
		aif_resource_name=$(echo "$aiFoundryResourceId" | sed -n 's|.*/providers/Microsoft.CognitiveServices/accounts/\([^/]*\).*|\1|p')
		aif_resource_group=$(echo "$aiFoundryResourceId" | sed -n 's|.*/resourceGroups/\([^/]*\)/.*|\1|p')
		aif_subscription_id=$(echo "$aif_account_resource_id" | sed -n 's|.*/subscriptions/\([^/]*\)/.*|\1|p')
		
		original_foundry_public_access=$(az cognitiveservices account show \
			--name "$aif_resource_name" \
			--resource-group "$aif_resource_group" \
			--subscription "$aif_subscription_id" \
			--query "properties.publicNetworkAccess" \
			--output tsv)
		
		if [ -z "$original_foundry_public_access" ] || [ "$original_foundry_public_access" = "null" ]; then
			echo "⚠ Could not retrieve AI Foundry network access status"
		elif [ "$original_foundry_public_access" != "Enabled" ]; then
			echo "✓ Enabling AI Foundry public access"
			if ! MSYS_NO_PATHCONV=1 az resource update \
				--ids "$aif_account_resource_id" \
				--api-version 2024-10-01 \
				--set properties.publicNetworkAccess=Enabled properties.apiProperties="{}" \
				--output none; then
				echo "⚠ Failed to enable AI Foundry public access"
			fi
			# Wait a bit for changes to take effect
			sleep 10
		fi
	fi
	return 0
}

# Function to restore original network access settings for AI Foundry
restore_foundry_network_access() {
	if [ -n "$original_foundry_public_access" ] && [ "$original_foundry_public_access" != "Enabled" ]; then
		echo "✓ Restoring AI Foundry access"
		if ! MSYS_NO_PATHCONV=1 az resource update \
			--ids "$aif_account_resource_id" \
			--api-version 2024-10-01 \
			--set properties.publicNetworkAccess="$original_foundry_public_access" \
			--set properties.apiProperties.qnaAzureSearchEndpointKey="" \
			--set properties.networkAcls.bypass="AzureServices" \
			--output none 2>/dev/null; then
			echo "⚠ Failed to restore AI Foundry access - please check Azure portal"
		fi
	fi
}

# Function to handle script cleanup on exit
cleanup_on_exit() {
	exit_code=$?
	echo ""
	if [ $exit_code -ne 0 ]; then
		echo "❌ Script failed"
	else
		echo "✅ Script completed successfully"
	fi
	restore_foundry_network_access
	exit $exit_code
}

# Register cleanup function to run on script exit
trap cleanup_on_exit EXIT

# Check if azd is installed
check_azd_installed() {
	if command -v azd &> /dev/null; then
		return 0
	else
		return 1
	fi
}

get_values_from_azd_env() {
	# Use grep with a regex to ensure we're only capturing sanitized values to avoid command injection
	projectEndpoint=$(azd env get-value AZURE_AI_AGENT_ENDPOINT 2>&1 | grep -E '^https?://[a-zA-Z0-9._/:/-]+$')
	solutionName=$(azd env get-value SOLUTION_NAME 2>&1 | grep -E '^[a-zA-Z0-9._-]+$')
	gptModelName=$(azd env get-value AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME 2>&1 | grep -E '^[a-zA-Z0-9._-]+$')
	aiFoundryResourceId=$(azd env get-value AZURE_AI_FOUNDRY_RESOURCE_ID 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	apiAppName=$(azd env get-value API_APP_NAME 2>&1 | grep -E '^[a-zA-Z0-9._-]+$')
	aiSearchConnectionName=$(azd env get-value AZURE_AI_SEARCH_CONNECTION_NAME 2>&1 | grep -E '^[a-zA-Z0-9._-]+$')
	aiSearchIndex=$(azd env get-value AZURE_AI_SEARCH_INDEX 2>&1 | grep -E '^[a-zA-Z0-9._-]+$')
	resourceGroup=$(azd env get-value RESOURCE_GROUP_NAME 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	
	# Validate that we extracted all required values
	if [ -z "$projectEndpoint" ] || [ -z "$solutionName" ] || [ -z "$gptModelName" ] || [ -z "$aiFoundryResourceId" ] || [ -z "$apiAppName" ] || [ -z "$aiSearchConnectionName" ] || [ -z "$aiSearchIndex" ] || [ -z "$resourceGroup" ]; then
		echo "Error: One or more required values could not be retrieved from azd environment."
		return 1
	fi
	return 0
}

get_values_from_az_deployment() {
	echo "Getting values from Azure deployment outputs..."
 
    deploymentName=$(az group show --name "$resourceGroup" --query "tags.DeploymentName" -o tsv)
    echo "Deployment Name (from tag): $deploymentName"
 
    echo "Fetching deployment outputs..."
	# Get all outputs
    deploymentOutputs=$(az deployment group show \
        --name "$deploymentName" \
        --resource-group "$resourceGroup" \
        --query "properties.outputs" -o json)

	# Helper function to extract value from deployment outputs
	# Usage: extract_value "primaryKey" "fallbackKey"
	extract_value() {
		local primary_key="$1"
		local fallback_key="$2"
		local value
		
		value=$(echo "$deploymentOutputs" | grep -A 3 "\"$primary_key\"" | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
		if [ -z "$value" ] && [ -n "$fallback_key" ]; then
			value=$(echo "$deploymentOutputs" | grep -A 3 "\"$fallback_key\"" | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
		fi
		echo "$value"
	}

	# Extract each value using the helper function
	projectEndpoint=$(extract_value "azureAiAgentEndpoint" "azurE_AI_AGENT_ENDPOINT")
	solutionName=$(extract_value "solutionName" "solutioN_NAME")
	gptModelName=$(extract_value "azureAIAgentModelDeploymentName" "azurE_AI_AGENT_MODEL_DEPLOYMENT_NAME")
	aiFoundryResourceId=$(extract_value "aiFoundryResourceId" "aI_FOUNDRY_RESOURCE_ID")
	apiAppName=$(extract_value "apiAppName" "apI_APP_NAME")
	aiSearchConnectionName=$(extract_value "azureAISearchConnectionName" "azurE_AI_SEARCH_CONNECTION_NAME")
	aiSearchIndex=$(extract_value "azureAISearchIndex" "azurE_AI_SEARCH_INDEX")
	
	# Define required values with their display names for error reporting
	declare -A required_values=(
		["projectEndpoint"]="AZURE_AI_AGENT_ENDPOINT"
		["solutionName"]="SOLUTION_NAME"
		["gptModelName"]="AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME"
		["aiFoundryResourceId"]="AZURE_AI_FOUNDRY_RESOURCE_ID"
		["apiAppName"]="API_APP_NAME"
		["aiSearchConnectionName"]="AZURE_AI_SEARCH_CONNECTION_NAME"
		["aiSearchIndex"]="AZURE_AI_SEARCH_INDEX"
	)

	# Validate and collect missing values
	missing_values=()
	for var_name in "${!required_values[@]}"; do
		if [ -z "${!var_name}" ]; then
			missing_values+=("${required_values[$var_name]}")
		fi
	done

	if [ ${#missing_values[@]} -gt 0 ]; then
		echo "Error: The following required values could not be retrieved from Azure deployment outputs:"
		printf '  - %s\n' "${missing_values[@]}" | sort
		return 1
	fi
	return 0
}

# Check if user is logged in to Azure
echo "Checking Azure authentication..."
if az account show &> /dev/null; then
    echo "Already authenticated with Azure."
else
    # Use Azure CLI login if running locally
    echo "Authenticating with Azure CLI..."
    if ! az login --use-device-code; then
        echo "✗ Failed to authenticate with Azure"
        exit 1
    fi
fi

echo ""

if [ -z "$resourceGroup" ]; then
    # No resource group provided - use azd env
    if ! get_values_from_azd_env; then
        echo "Failed to get values from azd environment."
		echo ""
        echo "If you want to use deployment outputs instead, please provide the resource group name as an argument."
        echo "Usage: $0 [ResourceGroupName]"
		echo "Example: $0 my-resource-group"
		echo ""
        exit 1
    fi
else
    # Resource group provided - use deployment outputs
	echo ""
    echo "Resource group provided: $resourceGroup"

    # Call deployment function
    if ! get_values_from_az_deployment; then
        echo "Failed to get values from deployment outputs."
		echo ""
        echo "Exiting script."
        exit 1
	fi
fi

# Validate all required parameters are present
if [ -z "$projectEndpoint" ] || [ -z "$solutionName" ] || [ -z "$gptModelName" ] || [ -z "$aiFoundryResourceId" ] || [ -z "$apiAppName" ] || [ -z "$aiSearchConnectionName" ] || [ -z "$aiSearchIndex" ] || [ -z "$resourceGroup" ]; then
    echo ""
    echo "Error: Missing required parameters."
    echo "Usage: $0 <projectEndpoint> <solutionName> <gptModelName> <aiFoundryResourceId> <apiAppName> <aiSearchConnectionName> <aiSearchIndex> <resourceGroup>"
    echo ""
    echo "Or run without parameters to use azd environment values."
    exit 1
fi

echo ""
echo "==============================================="
echo "Values to be used:"
echo "==============================================="
echo "Resource Group: $resourceGroup"
echo "Project Endpoint: $projectEndpoint"
echo "Solution Name: $solutionName"
echo "GPT Model Name: $gptModelName"
echo "AI Foundry Resource ID: $aiFoundryResourceId"
echo "API App Name: $apiAppName"
echo "AI Search Connection Name: $aiSearchConnectionName"
echo "AI Search Index: $aiSearchIndex"
echo "==============================================="
echo ""

echo "Getting signed in user id"
signed_user_id=$(az ad signed-in-user show --query id -o tsv) || signed_user_id=${AZURE_CLIENT_ID}

echo "Checking if the user has Azure AI User role on the AI Foundry"
role_assignment=$(MSYS_NO_PATHCONV=1 az role assignment list \
  --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" \
  --scope "$aiFoundryResourceId" \
  --assignee "$signed_user_id" \
  --query "[].roleDefinitionId" -o tsv)

if [ -z "$role_assignment" ]; then
    echo "User does not have the Azure AI User role. Assigning the role..."
    MSYS_NO_PATHCONV=1 az role assignment create \
      --assignee "$signed_user_id" \
      --role "53ca6127-db72-4b80-b1b0-d745d6d5456d" \
      --scope "$aiFoundryResourceId" \
      --output none

    if [ $? -eq 0 ]; then
        echo "✅ Azure AI User role assigned successfully."
    else
        echo "❌ Failed to assign Azure AI User role."
        exit 1
    fi
else
    echo "User already has the Azure AI User role."
fi


requirementFile="infra/scripts/agent_scripts/requirements.txt"

# Download and install Python requirements
python -m pip install --upgrade pip
python -m pip install --quiet -r "$requirementFile"

# Enable public network access for AI Foundry before agent creation
enable_foundry_public_access
if [ $? -ne 0 ]; then
	echo "Error: Failed to enable public network access for AI Foundry."
	exit 1
fi

# Execute the Python scripts
echo "Running Python agents creation script..."
eval $(python infra/scripts/agent_scripts/01_create_agents.py --ai_project_endpoint="$projectEndpoint" --solution_name="$solutionName" --gpt_model_name="$gptModelName" --azure_ai_search_connection_name="$aiSearchConnectionName" --azure_ai_search_index="$aiSearchIndex")

echo "Agents creation completed."

# Update environment variables of API App
az webapp config appsettings set \
  --resource-group "$resourceGroup" \
  --name "$apiAppName" \
  --settings AGENT_NAME_CONVERSATION="$conversationAgentName" AGENT_NAME_TITLE="$titleAgentName" \
  -o none

azd env set AGENT_NAME_CONVERSATION "$conversationAgentName"
azd env set AGENT_NAME_TITLE "$titleAgentName"
echo "Environment variables updated for App Service: $apiAppName"
