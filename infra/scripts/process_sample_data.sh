#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Variables - Grouped by service for clarity
# General Azure
resourceGroupName="${1}"
azSubscriptionId="${2}"

# Storage
storageAccountName="${3}"
fileSystem="${4}"

# SQL Database
sqlServerName="${5}"
SqlDatabaseName="${6}"
backendUserMidClientId="${7}"
backendUserMidDisplayName="${8}"

# AI Search
aiSearchName="${9}"
searchEndpoint="${10}"

# AI Foundry
aif_resource_id="${11}"
cu_foundry_resource_id="${12}"

# OpenAI
openaiEndpoint="${13}"
embeddingModel="${14}"
deploymentModel="${15}"

# Content Understanding & AI Agent
cuEndpoint="${16}"
cuApiVersion="${17}"
aiAgentEndpoint="${18}"

usecase="${19}"

# Global variables to track original network access states
original_storage_public_access=""
original_storage_default_action=""
original_foundry_public_access=""
original_cu_foundry_public_access=""
aif_resource_group=""
aif_account_resource_id=""
cu_resource_group=""
cu_account_resource_id=""
# Add global variable for SQL Server public access
original_sql_public_access=""
created_sql_allow_all_firewall_rule="false"
original_full_range_rule_present="false"

# Function to enable public network access temporarily
enable_public_access() {
	
	# Enable public access for Storage Account
	original_storage_public_access=$(az storage account show \
		--name "$storageAccountName" \
		--resource-group "$resourceGroupName" \
		--query "publicNetworkAccess" \
		-o tsv 2>&1)
	if [ -z "$original_storage_public_access" ] || [[ "$original_storage_public_access" == *"ERROR"* ]]; then
		echo "✗ Failed to get Storage Account public access status"
		return 1
	fi
	
	original_storage_default_action=$(az storage account show \
		--name "$storageAccountName" \
		--resource-group "$resourceGroupName" \
		--query "networkRuleSet.defaultAction" \
		-o tsv 2>&1)
	if [ -z "$original_storage_default_action" ] || [[ "$original_storage_default_action" == *"ERROR"* ]]; then
		echo "✗ Failed to get Storage Account network default action"
		return 1
	fi
	
	if [ "$original_storage_public_access" != "Enabled" ]; then
		echo "✓ Enabling Storage Account public access"
		az storage account update \
			--name "$storageAccountName" \
			--resource-group "$resourceGroupName" \
			--public-network-access Enabled \
			--output none
		if [ $? -ne 0 ]; then
			echo "✗ Failed to enable Storage Account public access"
			return 1
		fi
	fi
	
	# Also ensure the default network action allows access
	if [ "$original_storage_default_action" != "Allow" ]; then
		echo "✓ Setting Storage Account network default action to Allow"
		az storage account update \
			--name "$storageAccountName" \
			--resource-group "$resourceGroupName" \
			--default-action Allow \
			--output none
		if [ $? -ne 0 ]; then
			echo "✗ Failed to set Storage Account network default action"
			return 1
		fi
	fi
	
	# Enable public access for AI Foundry
	if [ -n "$aif_resource_id" ] && [ "$aif_resource_id" != "null" ]; then
		aif_account_resource_id="$aif_resource_id"
		aif_resource_name=$(echo "$aif_resource_id" | sed -n 's|.*/providers/Microsoft.CognitiveServices/accounts/\([^/]*\).*|\1|p')
		aif_resource_group=$(echo "$aif_resource_id" | sed -n 's|.*/resourceGroups/\([^/]*\)/.*|\1|p')
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
		fi
	fi
	
	# Enable public access for Content Understanding Foundry
	if [ -n "$cu_foundry_resource_id" ] && [ "$cu_foundry_resource_id" != "null" ]; then
		cu_account_resource_id="$cu_foundry_resource_id"
		cu_resource_name=$(echo "$cu_foundry_resource_id" | sed -n 's|.*/providers/Microsoft.CognitiveServices/accounts/\([^/]*\).*|\1|p')
		cu_resource_group=$(echo "$cu_foundry_resource_id" | sed -n 's|.*/resourceGroups/\([^/]*\)/.*|\1|p')
		cu_subscription_id=$(echo "$cu_account_resource_id" | sed -n 's|.*/subscriptions/\([^/]*\)/.*|\1|p')
		
		original_cu_foundry_public_access=$(az cognitiveservices account show \
			--name "$cu_resource_name" \
			--resource-group "$cu_resource_group" \
			--subscription "$cu_subscription_id" \
			--query "properties.publicNetworkAccess" \
			--output tsv)
		
		if [ -z "$original_cu_foundry_public_access" ] || [ "$original_cu_foundry_public_access" = "null" ]; then
			echo "⚠ Could not retrieve CU Foundry network access status"
		elif [ "$original_cu_foundry_public_access" != "Enabled" ]; then
			echo "✓ Enabling CU Foundry public access"
			if ! MSYS_NO_PATHCONV=1 az resource update \
				--ids "$cu_account_resource_id" \
				--api-version 2024-10-01 \
				--set properties.publicNetworkAccess=Enabled properties.apiProperties="{}" \
				--output none; then
				echo "⚠ Failed to enable CU Foundry public access"
			fi
		fi
	fi
	
	# Enable public access for SQL Server
	original_sql_public_access=$(az sql server show \
		--name "$sqlServerName" \
		--resource-group "$resourceGroupName" \
		--query "publicNetworkAccess" \
		-o tsv)
	
	if [ "$original_sql_public_access" != "Enabled" ]; then
		echo "✓ Enabling SQL Server public access"
		az sql server update \
			--name "$sqlServerName" \
			--resource-group "$resourceGroupName" \
			--enable-public-network true \
			--output none
		if [ $? -ne 0 ]; then
			echo "✗ Failed to enable SQL Server public access"
			return 1
		fi
	fi
	
	# Create temporary allow-all firewall rule for SQL Server
	sql_allow_all_rule_name="TempAllowAll"
	
	# Check if there's already a rule allowing full IP range to avoid creating a duplicate
	pre_existing_full_range_rule=$(az sql server firewall-rule list \
	    --server "$sqlServerName" \
	    --resource-group "$resourceGroupName" \
	    --query "[?startIpAddress=='0.0.0.0' && endIpAddress=='255.255.255.255'] | [0].name" \
	    -o tsv 2>/dev/null)
	
	if [ -n "$pre_existing_full_range_rule" ]; then
	    original_full_range_rule_present="true"
	fi
	
	existing_allow_all_rule=$(az sql server firewall-rule list \
	    --server "$sqlServerName" \
	    --resource-group "$resourceGroupName" \
	    --query "[?name=='${sql_allow_all_rule_name}'] | [0].name" \
	    -o tsv 2>/dev/null)
	
	if [ -z "$existing_allow_all_rule" ] && [ -z "$pre_existing_full_range_rule" ]; then
		echo "✓ Creating temporary SQL firewall rule"
		if az sql server firewall-rule create \
			--resource-group "$resourceGroupName" \
			--server "$sqlServerName" \
			--name "$sql_allow_all_rule_name" \
			--start-ip-address 0.0.0.0 \
			--end-ip-address 255.255.255.255 \
			--output none; then
			created_sql_allow_all_firewall_rule="true"
		else
			echo "⚠ Failed to create firewall rule"
		fi
	else
		original_full_range_rule_present="true"
	fi
		
	# Wait a bit for changes to take effect
	sleep 10
	return 0
}

# Function to restore original network access settings
restore_network_access() {
	
	# Restore Storage Account access
	if [ -n "$original_storage_public_access" ] && [ "$original_storage_public_access" != "Enabled" ]; then
		echo "✓ Restoring Storage Account access"
		case "$original_storage_public_access" in
			"enabled"|"Enabled") restore_value="Enabled" ;;
			"disabled"|"Disabled") restore_value="Disabled" ;;
			*) restore_value="$original_storage_public_access" ;;
		esac
		az storage account update \
			--name "$storageAccountName" \
			--resource-group "$resourceGroupName" \
			--public-network-access "$restore_value" \
			--output none
		if [ $? -ne 0 ]; then
			echo "✗ Failed to restore Storage Account access"
		fi
	fi
		
	# Restore Storage Account network default action
	if [ -n "$original_storage_default_action" ] && [ "$original_storage_default_action" != "Allow" ]; then
		echo "✓ Restoring Storage Account network default action"
		az storage account update \
			--name "$storageAccountName" \
			--resource-group "$resourceGroupName" \
			--default-action "$original_storage_default_action" \
			--output none
		if [ $? -ne 0 ]; then
			echo "✗ Failed to restore Storage Account network default action"
		fi
	fi
		
	# Restore AI Foundry access
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
	
	# Restore CU Foundry access
	if [ -n "$original_cu_foundry_public_access" ] && [ "$original_cu_foundry_public_access" != "Enabled" ]; then
		echo "✓ Restoring CU Foundry access"
		if ! MSYS_NO_PATHCONV=1 az resource update \
			--ids "$cu_account_resource_id" \
			--api-version 2024-10-01 \
			--set properties.publicNetworkAccess="$original_cu_foundry_public_access" \
        	--set properties.apiProperties.qnaAzureSearchEndpointKey="" \
        	--set properties.networkAcls.bypass="AzureServices" \
			--output none 2>/dev/null; then
			echo "⚠ Failed to restore CU Foundry access - please check Azure portal"
		fi
	fi
	
	
	# Restore SQL Server public access
	if [ -n "$original_sql_public_access" ] && [ "$original_sql_public_access" != "Enabled" ]; then
		echo "✓ Restoring SQL Server access"
		case "$original_sql_public_access" in
			"enabled"|"Enabled") restore_value=true ;;
			"disabled"|"Disabled") restore_value=false ;;
			*) restore_value="$original_sql_public_access" ;;
		esac
		az sql server update \
			--name "$sqlServerName" \
			--resource-group "$resourceGroupName" \
			--enable-public-network $restore_value \
			--output none
		if [ $? -ne 0 ]; then
			echo "✗ Failed to restore SQL Server access"
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
	restore_network_access
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
	resourceGroupName=$(azd env get-value RESOURCE_GROUP_NAME 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	storageAccountName=$(azd env get-value STORAGE_ACCOUNT_NAME 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	fileSystem=$(azd env get-value STORAGE_CONTAINER_NAME 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	sqlServerName=$(azd env get-value SQLDB_SERVER 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	SqlDatabaseName=$(azd env get-value SQLDB_DATABASE 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	backendUserMidClientId=$(azd env get-value BACKEND_USER_MID 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	backendUserMidDisplayName=$(azd env get-value BACKEND_USER_MID_NAME 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	aiSearchName=$(azd env get-value AZURE_AI_SEARCH_NAME 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	aif_resource_id=$(azd env get-value AI_FOUNDRY_RESOURCE_ID 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	cu_foundry_resource_id=$(azd env get-value CU_FOUNDRY_RESOURCE_ID 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	searchEndpoint=$(azd env get-value AZURE_AI_SEARCH_ENDPOINT 2>&1 | grep -E '^https?://[a-zA-Z0-9._/-]+$')
	openaiEndpoint=$(azd env get-value AZURE_OPENAI_ENDPOINT 2>&1 | grep -E '^https?://[a-zA-Z0-9._/-]+/?$')
	embeddingModel=$(azd env get-value AZURE_OPENAI_EMBEDDING_MODEL 2>&1 | grep -E '^[a-zA-Z0-9._-]+$')
	cuEndpoint=$(azd env get-value AZURE_OPENAI_CU_ENDPOINT 2>&1 | grep -E '^https?://[a-zA-Z0-9._/-]+$')
	aiAgentEndpoint=$(azd env get-value AZURE_AI_AGENT_ENDPOINT 2>&1 | grep -E '^https?://[a-zA-Z0-9._/:/-]+$')
	cuApiVersion=$(azd env get-value AZURE_CONTENT_UNDERSTANDING_API_VERSION 2>&1 | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}(-preview)?$')
	deploymentModel=$(azd env get-value AZURE_OPENAI_DEPLOYMENT_MODEL 2>&1 | grep -E '^[a-zA-Z0-9._-]+$')
	usecase=$(azd env get-value USE_CASE 2>&1 | grep -E '^[a-zA-Z0-9._-]+$')
	
	# Strip FQDN suffix from SQL server name if present (Azure CLI needs just the server name)
	sqlServerName="${sqlServerName%.database.windows.net}"
	
	# Validate that we extracted all required values
	if [ -z "$resourceGroupName" ] || [ -z "$storageAccountName" ] || [ -z "$fileSystem" ] || [ -z "$sqlServerName" ] || [ -z "$SqlDatabaseName" ] || [ -z "$backendUserMidClientId" ] || [ -z "$backendUserMidDisplayName" ] || [ -z "$aiSearchName" ] || [ -z "$aif_resource_id" ] || [ -z "$usecase" ]; then
		echo "Error: One or more required values could not be retrieved from azd environment."
		return 1
	fi
	return 0
}

get_values_from_az_deployment() {
	echo "Getting values from Azure deployment outputs..."
 
    deploymentName=$(az group show --name "$resourceGroupName" --query "tags.DeploymentName" -o tsv)
    echo "Deployment Name (from tag): $deploymentName"
 
    echo "Fetching deployment outputs..."
	# Get all outputs
    deploymentOutputs=$(az deployment group show \
        --name "$deploymentName" \
        --resource-group "$resourceGroupName" \
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
	storageAccountName=$(extract_value "storageAccountName" "storagE_ACCOUNT_NAME")
	fileSystem=$(extract_value "storageContainerName" "storagE_CONTAINER_NAME")
	sqlServerName=$(extract_value "sqlDBServer" "sqldB_SERVER")
	SqlDatabaseName=$(extract_value "sqlDBDatabase" "sqldB_DATABASE")
	backendUserMidClientId=$(extract_value "backendUserMid" "backenD_USER_MID")
	backendUserMidDisplayName=$(extract_value "backendUserMidName" "backenD_USER_MID_NAME")
	aiSearchName=$(extract_value "azureAISearchName" "azurE_AI_SEARCH_NAME")
	searchEndpoint=$(extract_value "azureAISearchEndpoint" "azurE_AI_SEARCH_ENDPOINT")
	aif_resource_id=$(extract_value "aiFoundryResourceId" "aI_FOUNDRY_RESOURCE_ID")
	cu_foundry_resource_id=$(extract_value "cuFoundryResourceId" "cU_FOUNDRY_RESOURCE_ID")
	openaiEndpoint=$(extract_value "azureOpenAIEndpoint" "azurE_OPENAI_ENDPOINT")
	embeddingModel=$(extract_value "azureOpenAIEmbeddingModel" "azurE_OPENAI_EMBEDDING_MODEL")
	cuEndpoint=$(extract_value "azureOpenAICuEndpoint" "azurE_OPENAI_CU_ENDPOINT")
	aiAgentEndpoint=$(extract_value "azureAiAgentEndpoint" "azurE_AI_AGENT_ENDPOINT")
	cuApiVersion=$(extract_value "azureContentUnderstandingApiVersion" "azurE_CONTENT_UNDERSTANDING_API_VERSION")
	deploymentModel=$(extract_value "azureOpenAIDeploymentModel" "azurE_OPENAI_DEPLOYMENT_MODEL")
	usecase=$(extract_value "useCase" "usE_CASE")
	
	# Strip FQDN suffix from SQL server name if present (Azure CLI needs just the server name)
	sqlServerName="${sqlServerName%.database.windows.net}"
	
	# Define required values with their display names for error reporting
	declare -A required_values=(
		["storageAccountName"]="STORAGE_ACCOUNT_NAME"
		["fileSystem"]="STORAGE_CONTAINER_NAME"
		["sqlServerName"]="SQLDB_SERVER"
		["SqlDatabaseName"]="SQLDB_DATABASE"
		["backendUserMidClientId"]="BACKEND_USER_MID"
		["backendUserMidDisplayName"]="BACKEND_USER_MID_NAME"
		["aiSearchName"]="AZURE_AI_SEARCH_NAME"
		["aif_resource_id"]="AI_FOUNDRY_RESOURCE_ID"
		["cu_foundry_resource_id"]="CU_FOUNDRY_RESOURCE_ID"
		["searchEndpoint"]="AZURE_AI_SEARCH_ENDPOINT"
		["openaiEndpoint"]="AZURE_OPENAI_ENDPOINT"
		["embeddingModel"]="AZURE_OPENAI_EMBEDDING_MODEL"
		["cuEndpoint"]="AZURE_OPENAI_CU_ENDPOINT"
		["aiAgentEndpoint"]="AZURE_AI_AGENT_ENDPOINT"
		["cuApiVersion"]="AZURE_CONTENT_UNDERSTANDING_API_VERSION"
		["deploymentModel"]="AZURE_OPENAI_DEPLOYMENT_MODEL"
		["usecase"]="USE_CASE"
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

if check_azd_installed; then
    azSubscriptionId=$(azd env get-value AZURE_SUBSCRIPTION_ID) || azSubscriptionId="$AZURE_SUBSCRIPTION_ID" || azSubscriptionId=""
fi

#check if user has selected the correct subscription
echo ""
currentSubscriptionId=$(az account show --query id -o tsv 2>/dev/null)
currentSubscriptionName=$(az account show --query name -o tsv 2>/dev/null)
if [ -z "$currentSubscriptionId" ] || [ -z "$currentSubscriptionName" ]; then
    echo "✗ Failed to get current subscription information"
    exit 1
fi
if [ "$currentSubscriptionId" != "$azSubscriptionId" ]; then
	echo "Current selected subscription is $currentSubscriptionName ( $currentSubscriptionId )."
	read -rp "Do you want to continue with this subscription?(y/n): " confirmation
	if [[ "$confirmation" != "y" && "$confirmation" != "Y" ]]; then
		echo "Fetching available subscriptions..."
		availableSubscriptions=$(az account list --query "[?state=='Enabled'].[name,id]" --output tsv)
		while true; do
			echo ""
			echo "Available Subscriptions:"
			echo "========================"
			echo "$availableSubscriptions" | awk '{printf "%d. %s ( %s )\n", NR, $1, $2}'
			echo "========================"
			echo ""
			read -rp "Enter the number of the subscription (1-$(echo "$availableSubscriptions" | wc -l)) to use: " subscriptionIndex
			if [[ "$subscriptionIndex" =~ ^[0-9]+$ ]] && [ "$subscriptionIndex" -ge 1 ] && [ "$subscriptionIndex" -le $(echo "$availableSubscriptions" | wc -l) ]; then
				selectedSubscription=$(echo "$availableSubscriptions" | sed -n "${subscriptionIndex}p")
				selectedSubscriptionName=$(echo "$selectedSubscription" | cut -f1)
				selectedSubscriptionId=$(echo "$selectedSubscription" | cut -f2)

				# Set the selected subscription
				if  az account set --subscription "$selectedSubscriptionId"; then
					echo "Switched to subscription: $selectedSubscriptionName ( $selectedSubscriptionId )"
					break
				else
					echo "Failed to switch to subscription: $selectedSubscriptionName ( $selectedSubscriptionId )."
				fi
			else
				echo "Invalid selection. Please try again."
			fi
		done
	else
		echo "Proceeding with the current subscription: $currentSubscriptionName ( $currentSubscriptionId )"
		if ! az account set --subscription "$currentSubscriptionId"; then
			echo "✗ Failed to set subscription"
			exit 1
		fi
	fi
else
	echo "Proceeding with the subscription: $currentSubscriptionName ( $currentSubscriptionId )"
	if ! az account set --subscription "$currentSubscriptionId"; then
		echo "✗ Failed to set subscription"
		exit 1
	fi
fi
echo ""

echo ""

if [ -z "$resourceGroupName" ]; then
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
    echo "Resource group provided: $resourceGroupName"

    # Call deployment function
    if ! get_values_from_az_deployment; then
        echo "Failed to get values from deployment outputs."
		echo ""
		echo "Would you like to enter the values manually? (y/n): "
		read -r manual_input_choice
		if [[ "$manual_input_choice" == "y" || "$manual_input_choice" == "Y" ]]; then
			if ! get_values_from_user; then
				echo "Error: Manual input failed."
				exit 1
			fi
		else
			echo "Exiting script."
			exit 1
		fi
	fi
fi

echo ""
echo "==============================================="
echo "Values to be used:"
echo "==============================================="
echo "Resource Group Name: $resourceGroupName"
echo "Storage Account Name: $storageAccountName"
echo "Storage Container Name: $fileSystem"
echo "SQL Server Name: $sqlServerName"
echo "SQL Database Name: $SqlDatabaseName"
echo "Backend User-Assigned Managed Identity Display Name: $backendUserMidDisplayName"
echo "Backend User-Assigned Managed Identity Client ID: $backendUserMidClientId"
echo "AI Search Service Name: $aiSearchName"
echo "AI Foundry Resource ID: $aif_resource_id"
echo "CU Foundry Resource ID: $cu_foundry_resource_id"
echo "Search Endpoint: $searchEndpoint"
echo "OpenAI Endpoint: $openaiEndpoint"
echo "Embedding Model: $embeddingModel"
echo "CU Endpoint: $cuEndpoint"
echo "CU API Version: $cuApiVersion"
echo "AI Agent Endpoint: $aiAgentEndpoint"
echo "Deployment Model: $deploymentModel"
echo "==============================================="
echo ""

# Enable public network access for required services
enable_public_access
if [ $? -ne 0 ]; then
	echo "Error: Failed to enable public network access for services."
	exit 1
fi

# Call copy_kb_files.sh
echo "Running copy_kb_files.sh"
bash "$SCRIPT_DIR/copy_kb_files.sh" "$storageAccountName" "$fileSystem" "$resourceGroupName" "$usecase"
if [ $? -ne 0 ]; then
	echo "Error: copy_kb_files.sh failed."
	exit 1
fi
echo "copy_kb_files.sh completed successfully."

# Call run_create_index_scripts.sh
echo "Running run_create_index_scripts.sh"
# Pass all required environment variables and backend managed identity info for role assignment
bash "$SCRIPT_DIR/run_create_index_scripts.sh" "$resourceGroupName" "$aiSearchName" "$searchEndpoint" "$sqlServerName" "$SqlDatabaseName" "$backendUserMidDisplayName" "$backendUserMidClientId" "$storageAccountName" "$openaiEndpoint" "$deploymentModel" "$embeddingModel" "$cuEndpoint" "$cuApiVersion" "$aif_resource_id" "$cu_foundry_resource_id" "$aiAgentEndpoint" "$usecase"
if [ $? -ne 0 ]; then
	echo "Error: run_create_index_scripts.sh failed."
	exit 1
fi
echo "run_create_index_scripts.sh completed successfully."

echo "All scripts executed successfully."
