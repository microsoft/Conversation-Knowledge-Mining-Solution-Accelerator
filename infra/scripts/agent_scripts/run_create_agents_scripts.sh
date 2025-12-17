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

# get parameters from azd env, if not provided
if [ -z "$projectEndpoint" ]; then
    projectEndpoint=$(azd env get-value AZURE_AI_AGENT_ENDPOINT)
fi

if [ -z "$solutionName" ]; then
    solutionName=$(azd env get-value SOLUTION_NAME)
fi

if [ -z "$gptModelName" ]; then
    gptModelName=$(azd env get-value AZURE_AI_AGENT_MODEL_DEPLOYMENT_NAME)
fi

if [ -z "$aiFoundryResourceId" ]; then
    aiFoundryResourceId=$(azd env get-value AZURE_AI_FOUNDRY_RESOURCE_ID)
fi

if [ -z "$apiAppName" ]; then
    apiAppName=$(azd env get-value API_APP_NAME)
fi

if [ -z "$aiSearchConnectionName" ]; then
    aiSearchConnectionName=$(azd env get-value AZURE_AI_SEARCH_CONNECTION_NAME)
fi

if [ -z "$aiSearchIndex" ]; then
    aiSearchIndex=$(azd env get-value AZURE_AI_SEARCH_INDEX)
fi

if [ -z "$resourceGroup" ]; then
    resourceGroup=$(azd env get-value AZURE_RESOURCE_GROUP)
fi


# Check if all required arguments are provided
if [ -z "$projectEndpoint" ] || [ -z "$solutionName" ] || [ -z "$gptModelName" ] || [ -z "$aiFoundryResourceId" ] || [ -z "$apiAppName" ] || [ -z "$aiSearchConnectionName" ] || [ -z "$aiSearchIndex" ] || [ -z "$resourceGroup" ]; then
    echo "Usage: $0 <projectEndpoint> <solutionName> <gptModelName> <aiFoundryResourceId> <apiAppName> <aiSearchConnectionName> <aiSearchIndex> <resourceGroup>"
    exit 1
fi

# Check if user is logged in to Azure
echo "Checking Azure authentication..."
if az account show &> /dev/null; then
    echo "Already authenticated with Azure."
else
    # Use Azure CLI login if running locally
    echo "Authenticating with Azure CLI..."
    az login --use-device-code
fi

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
