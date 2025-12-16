#!/bin/bash

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
aiAgentEndpoint="${17}"
cuApiVersion="${18}"

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
		-o tsv)
	original_storage_default_action=$(az storage account show \
		--name "$storageAccountName" \
		--resource-group "$resourceGroupName" \
		--query "networkRuleSet.defaultAction" \
		-o tsv)
	
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
	
	# Strip FQDN suffix from SQL server name if present (Azure CLI needs just the server name)
	sqlServerName="${sqlServerName%.database.windows.net}"
	
	# Validate that we extracted all required values
	if [ -z "$resourceGroupName" ] || [ -z "$storageAccountName" ] || [ -z "$fileSystem" ] || [ -z "$sqlServerName" ] || [ -z "$SqlDatabaseName" ] || [ -z "$backendUserMidClientId" ] || [ -z "$backendUserMidDisplayName" ] || [ -z "$aiSearchName" ] || [ -z "$aif_resource_id" ]; then
		echo "Error: One or more required values could not be retrieved from azd environment."
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
    az login --use-device-code
fi

if check_azd_installed; then
    azSubscriptionId=$(azd env get-value AZURE_SUBSCRIPTION_ID) || azSubscriptionId="$AZURE_SUBSCRIPTION_ID" || azSubscriptionId=""
fi

#check if user has selected the correct subscription
echo ""
currentSubscriptionId=$(az account show --query id -o tsv)
currentSubscriptionName=$(az account show --query name -o tsv)
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
		az account set --subscription "$currentSubscriptionId"
	fi
else
	echo "Proceeding with the subscription: $currentSubscriptionName ( $currentSubscriptionId )"
	az account set --subscription "$currentSubscriptionId"
fi
echo ""

echo ""
if ! get_values_from_azd_env; then
    echo "Failed to get values from azd environment."
    echo ""
    exit 1
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

pythonScriptPath="infra/scripts/index_scripts/"

# Install the requirements
pip install --quiet -r ${pythonScriptPath}requirements.txt

# Create Content Understanding analyzers
echo "✓ Creating Content Understanding analyzer templates"
python infra/scripts/index_scripts/02_create_cu_template_text.py --cu_endpoint="$cuEndpoint" --cu_api_version="$cuApiVersion"
if [ $? -ne 0 ]; then
	echo "Error: 02_create_cu_template_text.py failed."
	exit 1
fi

python infra/scripts/index_scripts/02_create_cu_template_audio.py --cu_endpoint="$cuEndpoint" --cu_api_version="$cuApiVersion"
if [ $? -ne 0 ]; then
	echo "Error: 02_create_cu_template_audio.py failed."
	exit 1
fi

# Run 04_cu_process_custom_data.py
echo "✓ Processing custom data"
sql_server_fqdn="$sqlServerName.database.windows.net"
python infra/scripts/index_scripts/04_cu_process_custom_data.py \
    --search_endpoint "$searchEndpoint" \
    --openai_endpoint "$openaiEndpoint" \
    --ai_project_endpoint "$aiAgentEndpoint" \
    --deployment_model "$deploymentModel" \
    --embedding_model "$embeddingModel" \
    --storage_account_name "$storageAccountName" \
    --sql_server "$sql_server_fqdn" \
    --sql_database "$SqlDatabaseName" \
    --cu_endpoint "$cuEndpoint" \
    --cu_api_version "$cuApiVersion"

if [ $? -ne 0 ]; then
	echo "Error: 04_cu_process_custom_data.py failed."
	exit 1
fi
