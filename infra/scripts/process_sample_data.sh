#!/bin/bash

# Variables
resourceGroupName="${1}"

storageAccount="${2}"
fileSystem="${3}"
keyvaultName="${4}"
sqlServerName="${5}"
SqlDatabaseName="${6}"
sqlManagedIdentityClientId="${7}"
sqlManagedIdentityDisplayName="${8}"
aiSearchName="${9}"
aif_resource_id="${10}"
cu_foundry_resource_id="${11}"
azSubscriptionId="${12}"

# Global variables to track original network access states
original_storage_public_access=""
original_storage_default_action=""
original_foundry_public_access=""
original_cu_foundry_public_access=""
original_keyvault_public_access=""
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
	echo "=== Temporarily enabling public network access for services ==="
	
	# Enable public access for Storage Account
	echo "Enabling public access for Storage Account: $storageAccount"
	original_storage_public_access=$(az storage account show \
		--name "$storageAccount" \
		--resource-group "$resourceGroupName" \
		--query "publicNetworkAccess" \
		-o tsv)
	original_storage_default_action=$(az storage account show \
		--name "$storageAccount" \
		--resource-group "$resourceGroupName" \
		--query "networkRuleSet.defaultAction" \
		-o tsv)
	
	if [ "$original_storage_public_access" != "Enabled" ]; then
		az storage account update \
			--name "$storageAccount" \
			--resource-group "$resourceGroupName" \
			--public-network-access Enabled \
			--output none
		if [ $? -eq 0 ]; then
			echo "✓ Storage Account public access enabled"
		else
			echo "✗ Failed to enable Storage Account public access"
			return 1
		fi
	else
		echo "✓ Storage Account public access already enabled"
	fi
	
	# Also ensure the default network action allows access
	if [ "$original_storage_default_action" != "Allow" ]; then
		echo "Setting Storage Account network default action to Allow"
		az storage account update \
			--name "$storageAccount" \
			--resource-group "$resourceGroupName" \
			--default-action Allow \
			--output none
		if [ $? -eq 0 ]; then
			echo "✓ Storage Account network default action set to Allow"
		else
			echo "✗ Failed to set Storage Account network default action"
			return 1
		fi
	else
		echo "✓ Storage Account network default action already set to Allow"
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
			echo "⚠ Info: Could not retrieve AI Foundry network access status."
		elif [ "$original_foundry_public_access" != "Enabled" ]; then
			echo "Current AI Foundry public access: $original_foundry_public_access"
			echo "Enabling public access for AI Foundry resource: $aif_resource_name (Resource Group: $aif_resource_group)"
			if MSYS_NO_PATHCONV=1 az resource update \
				--ids "$aif_account_resource_id" \
				--api-version 2024-10-01 \
				--set properties.publicNetworkAccess=Enabled properties.apiProperties="{}" \
				--output none; then
				echo "✓ AI Foundry public access enabled"
			else
				echo "⚠ Warning: Failed to enable AI Foundry public access automatically."
			fi
		else
			echo "✓ AI Foundry public access already enabled"
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
			echo "⚠ Info: Could not retrieve CU Foundry network access status."
		elif [ "$original_cu_foundry_public_access" != "Enabled" ]; then
			echo "Current CU Foundry public access: $original_cu_foundry_public_access"
			echo "Enabling public access for CU Foundry resource: $cu_resource_name (Resource Group: $cu_resource_group)"
			if MSYS_NO_PATHCONV=1 az resource update \
				--ids "$cu_account_resource_id" \
				--api-version 2024-10-01 \
				--set properties.publicNetworkAccess=Enabled properties.apiProperties="{}" \
				--output none; then
				echo "✓ CU Foundry public access enabled"
			else
				echo "⚠ Warning: Failed to enable CU Foundry public access automatically."
			fi
		else
			echo "✓ CU Foundry public access already enabled"
		fi
	fi
	
	# Enable public access for Key Vault
	echo "Enabling public access for Key Vault: $keyvaultName"
	original_keyvault_public_access=$(az keyvault show \
		--name "$keyvaultName" \
		--resource-group "$resourceGroupName" \
		--query "properties.publicNetworkAccess" \
		-o tsv)
	
	if [ "$original_keyvault_public_access" != "Enabled" ]; then
		az keyvault update \
			--name "$keyvaultName" \
			--resource-group "$resourceGroupName" \
			--public-network-access "Enabled" \
			--output none
		echo "✓ Key Vault public access enabled"
	else
		echo "✓ Key Vault public access already enabled"
	fi
	
	# Enable public access for SQL Server
	echo "Checking SQL Server public access: $sqlServerName"
	original_sql_public_access=$(az sql server show \
		--name "$sqlServerName" \
		--resource-group "$resourceGroupName" \
		--query "publicNetworkAccess" \
		-o tsv)
	
	if [ "$original_sql_public_access" != "Enabled" ]; then
		echo "Enabling public access for SQL Server"
		az sql server update \
			--name "$sqlServerName" \
			--resource-group "$resourceGroupName" \
			--enable-public-network true \
			--output none
		echo "✓ SQL Server public access enabled"
	else
		echo "✓ SQL Server public access already enabled"
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
	
	if [ -z "$existing_allow_all_rule" ]; then
	    if [ -n "$pre_existing_full_range_rule" ]; then
	        echo "✓ Existing rule ($pre_existing_full_range_rule) already allows full IP range."
	    else
	        echo "Creating temporary allow-all firewall rule ($sql_allow_all_rule_name)..."
	        if az sql server firewall-rule create \
	            --resource-group "$resourceGroupName" \
	            --server "$sqlServerName" \
	            --name "$sql_allow_all_rule_name" \
	            --start-ip-address 0.0.0.0 \
	            --end-ip-address 255.255.255.255 \
	            --output none; then
	            created_sql_allow_all_firewall_rule="true"
	            echo "✓ Temporary allow-all firewall rule created"
	        else
	            echo "⚠ Warning: Failed to create allow-all firewall rule"
	        fi
	    fi
	else
	    echo "✓ Temporary allow-all firewall rule already present"
	    original_full_range_rule_present="true"
	fi
		
	# Wait a bit for changes to take effect
	echo "Waiting for network access changes to propagate..."
	sleep 10
	echo "=== Public network access enabled successfully ==="
	return 0
}

# Function to restore original network access settings
restore_network_access() {
	echo "=== Restoring original network access settings ==="
	
	# Restore Storage Account access
	if [ -n "$original_storage_public_access" ] && [ "$original_storage_public_access" != "Enabled" ]; then
		echo "Restoring Storage Account public access to: $original_storage_public_access"
		case "$original_storage_public_access" in
			"enabled"|"Enabled") restore_value="Enabled" ;;
			"disabled"|"Disabled") restore_value="Disabled" ;;
			*) restore_value="$original_storage_public_access" ;;
		esac
		az storage account update \
			--name "$storageAccount" \
			--resource-group "$resourceGroupName" \
			--public-network-access "$restore_value" \
			--output none
		if [ $? -eq 0 ]; then
			echo "✓ Storage Account access restored"
		else
			echo "✗ Failed to restore Storage Account access"
		fi
	else
		echo "Storage Account access unchanged (already at desired state)"
	fi
		
	# Restore Storage Account network default action
	if [ -n "$original_storage_default_action" ] && [ "$original_storage_default_action" != "Allow" ]; then
		echo "Restoring Storage Account network default action to: $original_storage_default_action"
		az storage account update \
			--name "$storageAccount" \
			--resource-group "$resourceGroupName" \
			--default-action "$original_storage_default_action" \
			--output none
		if [ $? -eq 0 ]; then
			echo "✓ Storage Account network default action restored"
		else
			echo "✗ Failed to restore Storage Account network default action"
		fi
	else
		echo "Storage Account network default action unchanged (already at desired state)"
	fi
		
	# Restore AI Foundry access
	if [ -n "$original_foundry_public_access" ] && [ "$original_foundry_public_access" != "Enabled" ]; then
		echo "Restoring AI Foundry public access to: $original_foundry_public_access"
		if MSYS_NO_PATHCONV=1 az resource update \
			--ids "$aif_account_resource_id" \
			--api-version 2024-10-01 \
			--set properties.publicNetworkAccess="$original_foundry_public_access" \
        	--set properties.apiProperties.qnaAzureSearchEndpointKey="" \
        	--set properties.networkAcls.bypass="AzureServices" \
			--output none 2>/dev/null; then
			echo "✓ AI Foundry access restored"
		else
			echo "⚠ Warning: Failed to restore AI Foundry access automatically."
			echo "  Please manually restore network access in the Azure portal if needed."
		fi
	else
		echo "AI Foundry access unchanged (already at desired state)"
	fi
	
	# Restore CU Foundry access
	if [ -n "$original_cu_foundry_public_access" ] && [ "$original_cu_foundry_public_access" != "Enabled" ]; then
		echo "Restoring CU Foundry public access to: $original_cu_foundry_public_access"
		if MSYS_NO_PATHCONV=1 az resource update \
			--ids "$cu_account_resource_id" \
			--api-version 2024-10-01 \
			--set properties.publicNetworkAccess="$original_cu_foundry_public_access" \
        	--set properties.apiProperties.qnaAzureSearchEndpointKey="" \
        	--set properties.networkAcls.bypass="AzureServices" \
			--output none 2>/dev/null; then
			echo "✓ CU Foundry access restored"
		else
			echo "⚠ Warning: Failed to restore CU Foundry access automatically."
			echo "  Please manually restore network access in the Azure portal if needed."
		fi
	else
		echo "CU Foundry access unchanged (already at desired state)"
	fi
		
	# Restore Key Vault access
	if [ -n "$original_keyvault_public_access" ] && [ "$original_keyvault_public_access" != "Enabled" ]; then
		echo "Restoring Key Vault public access to: $original_keyvault_public_access"
		case "$original_keyvault_public_access" in
			"enabled"|"Enabled") restore_value="Enabled" ;;
			"disabled"|"Disabled") restore_value="Disabled" ;;
			*) restore_value="$original_keyvault_public_access" ;;
		esac
		az keyvault update \
			--name "$keyvaultName" \
			--resource-group "$resourceGroupName" \
			--public-network-access "$restore_value" \
			--output none
		if [ $? -eq 0 ]; then
			echo "✓ Key Vault access restored"
		else
			echo "✗ Failed to restore Key Vault access"
		fi
	else
		echo "Key Vault access unchanged (already at desired state)"
	fi
	
	# Restore SQL Server public access
	if [ -n "$original_sql_public_access" ] && [ "$original_sql_public_access" != "Enabled" ]; then
		echo "Restoring SQL Server public access to: $original_sql_public_access"
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
		if [ $? -eq 0 ]; then
			echo "✓ SQL Server access restored"
		else
			echo "✗ Failed to restore SQL Server access"
		fi
	else
		echo "SQL Server access unchanged (already at desired state)"
	fi
	
	# Remove temporary allow-all firewall rule if we created it
	if [ "$created_sql_allow_all_firewall_rule" = "true" ] && [ "$original_full_range_rule_present" != "true" ]; then
		echo "Removing temporary allow-all firewall rule..."
		az sql server firewall-rule delete \
			--resource-group "$resourceGroupName" \
			--server "$sqlServerName" \
			--name "TempAllowAll" \
			--output none 2>/dev/null
		echo "✓ Temporary firewall rule removed"
	fi
	
	echo "=== Network access restoration completed ==="
}

# Function to handle script cleanup on exit
cleanup_on_exit() {
	exit_code=$?
	echo ""
	if [ $exit_code -ne 0 ]; then
		echo "❌ Script failed with exit code $exit_code"
		echo "Restoring network access settings before exit..."
	else
		echo "✅ Script completed successfully"
		echo "Restoring network access settings..."
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
	echo "Getting values from azd environment variables..."
	# Use grep with a regex to ensure we're only capturing sanitized values to avoid command injection
	resourceGroupName=$(azd env get-value RESOURCE_GROUP_NAME 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	storageAccount=$(azd env get-value STORAGE_ACCOUNT_NAME 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	fileSystem=$(azd env get-value STORAGE_CONTAINER_NAME 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	keyvaultName=$(azd env get-value KEY_VAULT_NAME 2>&1 | grep -E '^[a-zA-Z0-9_-]+$')
	sqlServerName=$(azd env get-value SQLDB_SERVER 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	SqlDatabaseName=$(azd env get-value SQLDB_DATABASE 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	sqlManagedIdentityClientId=$(azd env get-value SQLDB_USER_MID 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	sqlManagedIdentityDisplayName=$(azd env get-value SQLDB_USER_MID_NAME 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	aiSearchName=$(azd env get-value AZURE_AI_SEARCH_NAME 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	aif_resource_id=$(azd env get-value AI_FOUNDRY_RESOURCE_ID 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	cu_foundry_resource_id=$(azd env get-value CU_FOUNDRY_RESOURCE_ID 2>&1 | grep -E '^[a-zA-Z0-9._/-]+$')
	
	# Strip FQDN suffix from SQL server name if present (Azure CLI needs just the server name)
	sqlServerName="${sqlServerName%.database.windows.net}"
	
	# Validate that we extracted all required values
	if [ -z "$resourceGroupName" ] || [ -z "$storageAccount" ] || [ -z "$fileSystem" ] || [ -z "$keyvaultName" ] || [ -z "$sqlServerName" ] || [ -z "$SqlDatabaseName" ] || [ -z "$sqlManagedIdentityClientId" ] || [ -z "$sqlManagedIdentityDisplayName" ] || [ -z "$aiSearchName" ] || [ -z "$aif_resource_id" ]; then
		echo "Error: One or more required values could not be retrieved from azd environment."
		return 1
	else
		echo "All values retrieved successfully from azd environment."
		return 0
	fi
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
 
    # Extract each value
    storageAccount=$(echo "$deploymentOutputs" | grep -A 3 '"storagE_ACCOUNT_NAME"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    if [ -z "$storageAccount" ]; then
        storageAccount=$(echo "$deploymentOutputs" | grep -A 3 '"storageAccountName"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    fi
    
    fileSystem=$(echo "$deploymentOutputs" | grep -A 3 '"storagE_CONTAINER_NAME"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    if [ -z "$fileSystem" ]; then
        fileSystem=$(echo "$deploymentOutputs" | grep -A 3 '"storageContainerName"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    fi
    
    keyvaultName=$(echo "$deploymentOutputs" | grep -A 3 '"keY_VAULT_NAME"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    if [ -z "$keyvaultName" ]; then
        keyvaultName=$(echo "$deploymentOutputs" | grep -A 3 '"keyVaultName"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    fi
    
    sqlServerName=$(echo "$deploymentOutputs" | grep -A 3 '"sqlDb_SERVER"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    if [ -z "$sqlServerName" ]; then
        sqlServerName=$(echo "$deploymentOutputs" | grep -A 3 '"sqlDbServer"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    fi
    
    SqlDatabaseName=$(echo "$deploymentOutputs" | grep -A 3 '"sqlDb_DATABASE"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    if [ -z "$SqlDatabaseName" ]; then
        SqlDatabaseName=$(echo "$deploymentOutputs" | grep -A 3 '"sqlDbDatabase"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    fi
    
    sqlManagedIdentityClientId=$(echo "$deploymentOutputs" | grep -A 3 '"sqlDb_USER_MID"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    if [ -z "$sqlManagedIdentityClientId" ]; then
        sqlManagedIdentityClientId=$(echo "$deploymentOutputs" | grep -A 3 '"sqlDbUserMid"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    fi
    
    sqlManagedIdentityDisplayName=$(echo "$deploymentOutputs" | grep -A 3 '"sqlDb_USER_MID_NAME"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    if [ -z "$sqlManagedIdentityDisplayName" ]; then
        sqlManagedIdentityDisplayName=$(echo "$deploymentOutputs" | grep -A 3 '"sqlDbUserMidName"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    fi
    
    aiSearchName=$(echo "$deploymentOutputs" | grep -A 3 '"azurE_AI_SEARCH_NAME"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    if [ -z "$aiSearchName" ]; then
        aiSearchName=$(echo "$deploymentOutputs" | grep -A 3 '"azureAiSearchName"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    fi
    
    aif_resource_id=$(echo "$deploymentOutputs" | grep -A 3 '"aI_FOUNDRY_RESOURCE_ID"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    if [ -z "$aif_resource_id" ]; then
        aif_resource_id=$(echo "$deploymentOutputs" | grep -A 3 '"aiFoundryResourceId"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    fi
    
    cu_foundry_resource_id=$(echo "$deploymentOutputs" | grep -A 3 '"cU_FOUNDRY_RESOURCE_ID"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    if [ -z "$cu_foundry_resource_id" ]; then
        cu_foundry_resource_id=$(echo "$deploymentOutputs" | grep -A 3 '"cuFoundryResourceId"' | grep '"value"' | sed 's/.*"value": *"\([^"]*\)".*/\1/')
    fi
 
    # Strip FQDN suffix from SQL server name if present (Azure CLI needs just the server name)
    sqlServerName="${sqlServerName%.database.windows.net}"
 
    # Validate that we extracted all required values
    if [ -z "$storageAccount" ] || [ -z "$fileSystem" ] || [ -z "$keyvaultName" ] || [ -z "$sqlServerName" ] || [ -z "$SqlDatabaseName" ] || [ -z "$sqlManagedIdentityClientId" ] || [ -z "$sqlManagedIdentityDisplayName" ] || [ -z "$aiSearchName" ] || [ -z "$aif_resource_id" ]; then
        echo "Error: One or more required values could not be retrieved from deployment outputs."
        return 1
    else
        echo "All values retrieved successfully from deployment outputs."
        return 0
    fi
}

get_values_from_user() {
    echo "Please enter required values manually."
	read -rp "Enter Storage Account Name: " storageAccount
	read -rp "Enter Storage Container Name: " fileSystem
	read -rp "Enter Key Vault Name: " keyvaultName
	read -rp "Enter SQL Server Name: " sqlServerName
	read -rp "Enter SQL Database Name: " SqlDatabaseName
	read -rp "Enter SQL Managed Identity Display Name: " sqlManagedIdentityDisplayName
	read -rp "Enter SQL Managed Identity Client ID: " sqlManagedIdentityClientId
	read -rp "Enter AI Search Service Name: " aiSearchName
	read -rp "Enter AI Foundry Resource ID: " aif_resource_id
	read -rp "Enter CU Foundry Resource ID: " cu_foundry_resource_id

	# Validate that all required values are provided
	if [ -z "$storageAccount" ] || [ -z "$fileSystem" ] || [ -z "$keyvaultName" ] || [ -z "$sqlServerName" ] || [ -z "$SqlDatabaseName" ] || [ -z "$sqlManagedIdentityClientId" ] || [ -z "$sqlManagedIdentityDisplayName" ] || [ -z "$aiSearchName" ] || [ -z "$aif_resource_id" ]; then
		echo "Error: All values are required. Please try again."
		return 1
	else
		echo "All values provided successfully."
		return 0
	fi
}

# Authenticate with Azure
echo ""
echo "Attempting to authenticate with Azure..."
echo "Authenticating with Azure CLI..."
az login --use-device-code

echo ""
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
echo "Storage Account Name: $storageAccount"
echo "Storage Container Name: $fileSystem"
echo "Key Vault Name: $keyvaultName"
echo "SQL Server Name: $sqlServerName"
echo "SQL Database Name: $SqlDatabaseName"
echo "SQL Managed Identity Display Name: $sqlManagedIdentityDisplayName"
echo "SQL Managed Identity Client ID: $sqlManagedIdentityClientId"
echo "AI Search Service Name: $aiSearchName"
echo "AI Foundry Resource ID: $aif_resource_id"
echo "CU Foundry Resource ID: $cu_foundry_resource_id"
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
bash infra/scripts/copy_kb_files.sh "$storageAccount" "$fileSystem" "$resourceGroupName"
if [ $? -ne 0 ]; then
	echo "Error: copy_kb_files.sh failed."
	exit 1
fi
echo "copy_kb_files.sh completed successfully."

# Call run_create_index_scripts.sh
echo "Running run_create_index_scripts.sh"
# Pass SQL managed identity client id and display name so index script can perform role assignment centrally
bash infra/scripts/run_create_index_scripts.sh "$keyvaultName" "" "" "$resourceGroupName" "$sqlServerName" "$aiSearchName" "$aif_resource_id" "$SqlDatabaseName" "$sqlManagedIdentityDisplayName" "$sqlManagedIdentityClientId" "$cu_foundry_resource_id"
if [ $? -ne 0 ]; then
	echo "Error: run_create_index_scripts.sh failed."
	exit 1
fi
echo "run_create_index_scripts.sh completed successfully."

## SQL role assignment now centralized in run_create_index_scripts.sh; removed local duplicate block.

echo "All scripts executed successfully."
echo "Network access will be restored to original settings..."
# Note: cleanup_on_exit will be called automatically via the trap
