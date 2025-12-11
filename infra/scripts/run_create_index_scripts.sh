#!/bin/bash

# Variables
keyvaultName="$1"
baseUrl="$2"
managedIdentityClientId="$3"
resourceGroupName="$4"
sqlServerName="$5"
aiSearchName="$6"
aif_resource_id="$7"
sqlDatabaseName="$8"
sqlManagedIdentityDisplayName="${9}"
sqlManagedIdentityClientId="${10}"
cu_foundry_resource_id="${11}"

echo "Script Started"

# Authenticate with Azure
if az account show &> /dev/null; then
    echo "Already authenticated with Azure."
else
    echo "Not authenticated with Azure. Attempting to authenticate..."
    if [ -n "$managedIdentityClientId" ]; then
        # Use managed identity if running in Azure
        echo "Authenticating with Managed Identity..."
        az login --identity --client-id ${managedIdentityClientId}
    else
        # Use Azure CLI login if running locally
        echo "Authenticating with Azure CLI..."
        az login
    fi
fi

# Get signed in user and store the output
echo "Getting signed in user id and display name"
signed_user=$(az ad signed-in-user show --query "{id:id, displayName:displayName}" -o json)
signed_user_id=$(echo "$signed_user" | grep -o '"id": *"[^"]*"' | head -1 | sed 's/"id": *"\([^"]*\)"/\1/')
signed_user_display_name=$(echo "$signed_user" | grep -o '"displayName": *"[^"]*"' | sed 's/"displayName": *"\([^"]*\)"/\1/')

### Assign Key Vault Administrator role to the signed in user ###

echo "Getting key vault resource id"
key_vault_resource_id=$(az keyvault show --name $keyvaultName --query id --output tsv)

echo "Checking if user has the Key Vault Administrator role"
role_assignment=$(MSYS_NO_PATHCONV=1 az role assignment list --assignee $signed_user_id --role "Key Vault Administrator" --scope $key_vault_resource_id --query "[].roleDefinitionId" -o tsv)
if [ -z "$role_assignment" ]; then
    echo "User does not have the Key Vault Administrator role. Assigning the role."
    MSYS_NO_PATHCONV=1 az role assignment create --assignee $signed_user_id --role "Key Vault Administrator" --scope $key_vault_resource_id --output none
    if [ $? -eq 0 ]; then
        echo "Key Vault Administrator role assigned successfully."
    else
        echo "Failed to assign Key Vault Administrator role."
        exit 1
    fi
else
    echo "User already has the Key Vault Administrator role."
fi

### Assign Azure AI User role to the signed in user for AI Foundry ###

# Check if the user has the Azure AI User role
echo "Checking if user has the Azure AI User role for AI Foundry"
role_assignment=$(MSYS_NO_PATHCONV=1 az role assignment list --role 53ca6127-db72-4b80-b1b0-d745d6d5456d --scope $aif_resource_id --assignee $signed_user_id --query "[].roleDefinitionId" -o tsv)
if [ -z "$role_assignment" ]; then
    echo "User does not have the Azure AI User role for AI Foundry. Assigning the role."
    MSYS_NO_PATHCONV=1 az role assignment create --assignee $signed_user_id --role 53ca6127-db72-4b80-b1b0-d745d6d5456d --scope $aif_resource_id --output none
    if [ $? -eq 0 ]; then
        echo "Azure AI User role for AI Foundry assigned successfully."
    else
        echo "Failed to assign Azure AI User role for AI Foundry."
        exit 1
    fi
else
    echo "User already has the Azure AI User role for AI Foundry."
fi

### Assign Azure AI User role to the signed in user for CU Foundry ###

if [ -n "$cu_foundry_resource_id" ] && [ "$cu_foundry_resource_id" != "null" ]; then
    echo "Checking if user has the Azure AI User role for CU Foundry"
    role_assignment=$(MSYS_NO_PATHCONV=1 az role assignment list --role 53ca6127-db72-4b80-b1b0-d745d6d5456d --scope $cu_foundry_resource_id --assignee $signed_user_id --query "[].roleDefinitionId" -o tsv)
    if [ -z "$role_assignment" ]; then
        echo "User does not have the Azure AI User role for CU Foundry. Assigning the role."
        MSYS_NO_PATHCONV=1 az role assignment create --assignee $signed_user_id --role 53ca6127-db72-4b80-b1b0-d745d6d5456d --scope $cu_foundry_resource_id --output none
        if [ $? -eq 0 ]; then
            echo "Azure AI User role for CU Foundry assigned successfully."
        else
            echo "Failed to assign Azure AI User role for CU Foundry."
            exit 1
        fi
    else
        echo "User already has the Azure AI User role for CU Foundry."
    fi
fi

### Assign Search Index Data Contributor role to the signed in user ###

echo "Getting Azure Search resource id"
search_resource_id=$(az search service show --name $aiSearchName --resource-group $resourceGroupName --query id --output tsv)

echo "Checking if user has the Search Index Data Contributor role"
role_assignment=$(MSYS_NO_PATHCONV=1 az role assignment list --assignee $signed_user_id --role "Search Index Data Contributor" --scope $search_resource_id --query "[].roleDefinitionId" -o tsv)
if [ -z "$role_assignment" ]; then
    echo "User does not have the Search Index Data Contributor role. Assigning the role."
    MSYS_NO_PATHCONV=1 az role assignment create --assignee $signed_user_id --role "Search Index Data Contributor" --scope $search_resource_id --output none
    if [ $? -eq 0 ]; then
        echo "Search Index Data Contributor role assigned successfully."
    else
        echo "Failed to assign Search Index Data Contributor role."
        exit 1
    fi
else
    echo "User already has the Search Index Data Contributor role."
fi


### Assign signed in user as SQL Server Admin ###

echo "Getting Azure SQL Server resource id"
sql_server_resource_id=$(az sql server show --name $sqlServerName --resource-group $resourceGroupName --query id --output tsv)

# Check if the user is Azure SQL Server Admin
echo "Checking if user is Azure SQL Server Admin"
admin=$(MSYS_NO_PATHCONV=1 az sql server ad-admin list --ids $sql_server_resource_id --query "[?sid == '$signed_user_id']" -o tsv)

# Check if the role exists
if [ -n "$admin" ]; then
    echo "User is already Azure SQL Server Admin"
else
    echo "User is not Azure SQL Server Admin. Assigning the role."
    MSYS_NO_PATHCONV=1 az sql server ad-admin create --display-name "$signed_user_display_name" --object-id $signed_user_id --resource-group $resourceGroupName --server $sqlServerName --output none
    if [ $? -eq 0 ]; then
        echo "Assigned user as Azure SQL Server Admin."
    else
        echo "Failed to assign Azure SQL Server Admin role."
        exit 1
    fi
fi


# create virtual environment
# Check if the virtual environment already exists
if [ -d "infra/scripts/scriptenv" ]; then
    echo "Virtual environment already exists. Skipping creation."
else
    echo "Creating virtual environment"
    python -m venv infra/scripts/scriptenv
fi

# handling virtual environment activation for different OS
activate_env_output=$(source infra/scripts/scriptenv/bin/activate 2>&1)
if [ -n "$activate_env_output" ]; then
    source infra/scripts/scriptenv/Scripts/activate
    echo "Activated virtual environment for Windows"
else
    echo "Activated virtual environment for Unix/Linux"
fi

# Install the requirements
echo "Installing requirements"
pip install --quiet -r infra/scripts/index_scripts/requirements.txt
echo "Requirements installed"

error_flag=false

echo "Running the python scripts"
echo "Creating the search index"
python infra/scripts/index_scripts/01_create_search_index.py "$keyvaultName"
if [ $? -ne 0 ]; then
    echo "Error: 01_create_search_index.py failed."
    error_flag=true
fi

echo "Creating CU template for text"
python infra/scripts/index_scripts/02_create_cu_template_text.py "$keyvaultName"
if [ $? -ne 0 ]; then
    echo "Error: 02_create_cu_template_text.py failed."
    error_flag=true
fi

echo "Creating CU template for audio"
python infra/scripts/index_scripts/02_create_cu_template_audio.py "$keyvaultName"
if [ $? -ne 0 ]; then
    echo "Error: 02_create_cu_template_audio.py failed."
    error_flag=true
fi

echo "Processing data with CU"
python infra/scripts/index_scripts/03_cu_process_data_text.py "$keyvaultName"
if [ $? -ne 0 ]; then
    echo "Error: 03_cu_process_data_text.py failed."
    error_flag=true
fi

# Create SQL tables if script exists
if [ -f "infra/scripts/index_scripts/create_sql_tables.py" ]; then
    echo "Creating SQL tables..."
    python infra/scripts/index_scripts/create_sql_tables.py "$keyvaultName"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to create SQL tables."
        error_flag=true
    fi
fi

# Assign SQL roles to managed identity using Python (pyodbc + azure-identity)
if [ -n "$sqlManagedIdentityClientId" ] && [ -n "$sqlManagedIdentityDisplayName" ] && [ -n "$sqlDatabaseName" ]; then
    mi_display_name="$sqlManagedIdentityDisplayName"
    server_fqdn="$sqlServerName.database.windows.net"
    roles_json="[{\"clientId\":\"$sqlManagedIdentityClientId\",\"displayName\":\"$mi_display_name\",\"role\":\"db_datareader\"},{\"clientId\":\"$sqlManagedIdentityClientId\",\"displayName\":\"$mi_display_name\",\"role\":\"db_datawriter\"}]"
    echo "[RoleAssign] Invoking assign_sql_roles.py for roles: db_datareader, db_datawriter"

    if [ -f "infra/scripts/add_user_scripts/assign_sql_roles.py" ]; then
        python infra/scripts/add_user_scripts/assign_sql_roles.py --server "$server_fqdn" --database "$sqlDatabaseName" --roles-json "$roles_json"
        if [ $? -ne 0 ]; then
            echo "[RoleAssign] Warning: SQL role assignment failed."
            error_flag=true
        else
            echo "[RoleAssign] SQL roles assignment completed successfully."
        fi
    else
        echo "[RoleAssign] assign_sql_roles.py not found. Skipping SQL role assignment."
    fi
else
    echo "[RoleAssign] Skipped SQL role assignment due to missing required values."
fi

# Check for any errors and exit if any occurred
if [ "$error_flag" = true ]; then
    echo "One or more scripts failed. Please check the logs above."
    exit 1
fi

echo "Scripts completed successfully"