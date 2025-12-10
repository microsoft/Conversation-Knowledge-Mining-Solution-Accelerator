#!/bin/bash
echo "started the script"

# Variables
keyvaultName="$1"
managedIdentityClientId="$2"
serverName="$3"
resourceGroup="$4"

echo "Script Started"

# Authenticate with Azure
if az account show &> /dev/null; then
    echo "Already authenticated with Azure."
else
    if [ -n "$managedIdentityClientId" ]; then
        echo "Authenticating with Managed Identity..."
        if ! az login --identity --client-id "$managedIdentityClientId" &> /dev/null; then
            echo "Failed to authenticate with Managed Identity. Falling back to Azure CLI login."
            az login
            if [ $? -ne 0 ]; then
                echo "Azure CLI login failed. Please authenticate manually and rerun the script."
                exit 1
            fi
        fi
    else
        echo "No Managed Identity Client ID provided. Attempting Azure CLI login..."
        az login
        if [ $? -ne 0 ]; then
            echo "Azure CLI login failed. Please authenticate manually and rerun the script."
            exit 1
        fi
    fi
fi

echo "Getting signed in user id"
signed_user_id=$(az ad signed-in-user show --query id --output tsv)

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
fi

# Install the requirements
echo "Installing requirements"
pip install --quiet -r infra/scripts/index_scripts/requirements.txt
echo "Requirements installed"

echo "Running the python scripts"
echo "Creating the search index"
python infra/scripts/index_scripts/01_create_search_index_manual.py "$keyvaultName" "$managedIdentityClientId"
if [ $? -ne 0 ]; then
    echo "Error: 01_create_search_index_manual.py failed."
    exit 1
fi

echo "Processing the data"
python infra/scripts/index_scripts/02_create_cu_template_text_manual.py "$keyvaultName" "$managedIdentityClientId"
if [ $? -ne 0 ]; then
    echo "Error: 02_create_cu_template_text_manual.py failed."
    exit 1
fi

echo "Processing the data"
python infra/scripts/index_scripts/02_create_cu_template_audio_manual.py "$keyvaultName" "$managedIdentityClientId"
if [ $? -ne 0 ]; then
    echo "Error: 02_create_cu_template_audio_manual.py failed."
    exit 1
fi

echo "Processing the data"

user=$(az account show --query user.name --output tsv)

# Get the signed-in user's object ID
objectId=$(az ad signed-in-user show --query id --output tsv)

az sql server ad-admin create \
  --resource-group "$resourceGroup" \
  --server "$serverName" \
  --display-name "$user" \
  --object-id "$objectId"
  
echo "✅ Set $user as Azure SQL Server AAD admin."

python infra/scripts/index_scripts/03_cu_process_data_text_manual.py "$keyvaultName" "$managedIdentityClientId"
if [ $? -ne 0 ]; then
    echo "Error: 03_cu_process_data_text_manual.py failed."
    exit 1
fi

echo "Scripts completed"