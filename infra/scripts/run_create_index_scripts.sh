#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Variables
resourceGroupName="$1"
aiSearchName="$2"
search_endpoint="${3}"
sqlServerName="$4"
sqlDatabaseName="$5"
backendManagedIdentityDisplayName="${6}"
backendManagedIdentityClientId="${7}"
storageAccountName="${8}"
openai_endpoint="${9}"
deployment_model="${10}"
embedding_model="${11}"
cu_endpoint="${12}"
cu_api_version="${13}"
aif_resource_id="${14}"
cu_foundry_resource_id="${15}"
ai_agent_endpoint="${16}"
usecase="${17}"

pythonScriptPath="$SCRIPT_DIR/index_scripts/"

# Authenticate with Azure
if ! az account show &> /dev/null; then
    echo "Authenticating with Azure CLI..."
	az login --use-device-code
fi

# Get signed in user and store the output
signed_user=$(az ad signed-in-user show --query "{id:id, displayName:displayName}" -o json 2>&1)
if [[ "$signed_user" == *"ERROR"* ]] || [[ "$signed_user" == *"InteractionRequired"* ]] || [[ "$signed_user" == *"AADSTS"* ]]; then
    echo "✗ Failed to get signed-in user. Token may have expired. Re-authenticating..."
    az login --use-device-code
    signed_user=$(az ad signed-in-user show --query "{id:id, displayName:displayName}" -o json)
fi

signed_user_id=$(echo "$signed_user" | grep -o '"id": *"[^"]*"' | head -1 | sed 's/"id": *"\([^"]*\)"/\1/')
signed_user_display_name=$(echo "$signed_user" | grep -o '"displayName": *"[^"]*"' | sed 's/"displayName": *"\([^"]*\)"/\1/')

if [ -z "$signed_user_id" ] || [ -z "$signed_user_display_name" ]; then
    echo "✗ Failed to extract user information after authentication"
    exit 1
fi

# Note: Environment variables are now passed as parameters from process_sample_data.sh

### Assign Azure AI User role to the signed in user for AI Foundry ###
role_assignment=$(MSYS_NO_PATHCONV=1 az role assignment list --role 53ca6127-db72-4b80-b1b0-d745d6d5456d --scope $aif_resource_id --assignee $signed_user_id --query "[].roleDefinitionId" -o tsv)
if [ -z "$role_assignment" ]; then
    echo "✓ Assigning Azure AI User role for AI Foundry"
    MSYS_NO_PATHCONV=1 az role assignment create --assignee $signed_user_id --role 53ca6127-db72-4b80-b1b0-d745d6d5456d --scope $aif_resource_id --output none
    if [ $? -ne 0 ]; then
        echo "✗ Failed to assign Azure AI User role for AI Foundry"
        exit 1
    fi
fi

### Assign Azure AI User role to the signed in user for CU Foundry ###
if [ -n "$cu_foundry_resource_id" ] && [ "$cu_foundry_resource_id" != "null" ]; then
    role_assignment=$(MSYS_NO_PATHCONV=1 az role assignment list --role 53ca6127-db72-4b80-b1b0-d745d6d5456d --scope $cu_foundry_resource_id --assignee $signed_user_id --query "[].roleDefinitionId" -o tsv)
    if [ -z "$role_assignment" ]; then
        echo "✓ Assigning Azure AI User role for CU Foundry"
        MSYS_NO_PATHCONV=1 az role assignment create --assignee $signed_user_id --role 53ca6127-db72-4b80-b1b0-d745d6d5456d --scope $cu_foundry_resource_id --output none
        if [ $? -ne 0 ]; then
            echo "✗ Failed to assign Azure AI User role for CU Foundry"
            exit 1
        fi
    fi
fi

### Assign Search Index Data Contributor role to the signed in user ###
search_resource_id=$(az search service show --name $aiSearchName --resource-group $resourceGroupName --query id --output tsv)

role_assignment=$(MSYS_NO_PATHCONV=1 az role assignment list --assignee $signed_user_id --role "Search Index Data Contributor" --scope $search_resource_id --query "[].roleDefinitionId" -o tsv)
if [ -z "$role_assignment" ]; then
    echo "✓ Assigning Search Index Data Contributor role"
    MSYS_NO_PATHCONV=1 az role assignment create --assignee $signed_user_id --role "Search Index Data Contributor" --scope $search_resource_id --output none
    if [ $? -ne 0 ]; then
        echo "✗ Failed to assign Search Index Data Contributor role"
        exit 1
    fi
fi


### Assign signed in user as SQL Server Admin ###
sql_server_resource_id=$(az sql server show --name $sqlServerName --resource-group $resourceGroupName --query id --output tsv)
admin=$(MSYS_NO_PATHCONV=1 az sql server ad-admin list --ids $sql_server_resource_id --query "[?sid == '$signed_user_id']" -o tsv)

if [ -z "$admin" ]; then
    echo "✓ Assigning user as SQL Server Admin"
    MSYS_NO_PATHCONV=1 az sql server ad-admin create --display-name "$signed_user_display_name" --object-id $signed_user_id --resource-group $resourceGroupName --server $sqlServerName --output none
    if [ $? -ne 0 ]; then
        echo "✗ Failed to assign SQL Server Admin role"
        exit 1
    fi
fi

# Install the requirements
echo "Installing requirements"
pip install --quiet -r ${pythonScriptPath}requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install Python requirements."
    exit 1
fi

error_flag=false

echo "✓ Creating search index"
python ${pythonScriptPath}01_create_search_index.py --search_endpoint="$search_endpoint" --openai_endpoint="$openai_endpoint" --embedding_model="$embedding_model"
if [ $? -ne 0 ]; then
    echo "Error: 01_create_search_index.py failed."
    error_flag=true
fi

echo "✓ Creating CU template for text"
python ${pythonScriptPath}02_create_cu_template_text.py --cu_endpoint="$cu_endpoint" --cu_api_version="$cu_api_version"
if [ $? -ne 0 ]; then
    echo "Error: 02_create_cu_template_text.py failed."
    error_flag=true
fi

if [ "$usecase" == "telecom" ]; then
    echo "✓ Creating CU template for audio"
    python ${pythonScriptPath}02_create_cu_template_audio.py --cu_endpoint="$cu_endpoint" --cu_api_version="$cu_api_version"
    if [ $? -ne 0 ]; then
        echo "Error: 02_create_cu_template_audio.py failed."
        error_flag=true
    fi
fi

echo "✓ Processing data with CU"
sql_server_fqdn="$sqlServerName.database.windows.net"
python ${pythonScriptPath}03_cu_process_data_text.py --search_endpoint="$search_endpoint" --ai_project_endpoint="$ai_agent_endpoint" --deployment_model="$deployment_model" --embedding_model="$embedding_model" --storage_account_name="$storageAccountName" --sql_server="$sql_server_fqdn" --sql_database="$sqlDatabaseName" --cu_endpoint="$cu_endpoint" --cu_api_version="$cu_api_version" --usecase="$usecase"
if [ $? -ne 0 ]; then
    echo "Error: 03_cu_process_data_text.py failed."
    error_flag=true
fi

# Assign SQL roles to managed identity using Python (pyodbc + azure-identity)
if [ -n "$backendManagedIdentityClientId" ] && [ -n "$backendManagedIdentityDisplayName" ] && [ -n "$sqlDatabaseName" ]; then
    mi_display_name="$backendManagedIdentityDisplayName"
    server_fqdn="$sqlServerName.database.windows.net"
    roles_json="[{\"clientId\":\"$backendManagedIdentityClientId\",\"displayName\":\"$mi_display_name\",\"role\":\"db_datareader\"},{\"clientId\":\"$backendManagedIdentityClientId\",\"displayName\":\"$mi_display_name\",\"role\":\"db_datawriter\"}]"

    if [ -f "$SCRIPT_DIR/add_user_scripts/assign_sql_roles.py" ]; then
        echo "✓ Assigning SQL roles to managed identity"
        python "$SCRIPT_DIR/add_user_scripts/assign_sql_roles.py" --server "$server_fqdn" --database "$sqlDatabaseName" --roles-json "$roles_json"
        if [ $? -ne 0 ]; then
            echo "⚠ SQL role assignment failed"
            error_flag=true
        fi
    fi
fi

# Check for any errors and exit if any occurred
if [ "$error_flag" = true ]; then
    echo "One or more scripts failed. Please check the logs above."
    exit 1
fi