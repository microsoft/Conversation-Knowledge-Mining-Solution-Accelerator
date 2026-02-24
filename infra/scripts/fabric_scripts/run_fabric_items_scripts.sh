#!/bin/bash
echo "starting script"

# Variables
keyvaultName="$1"
fabricWorkspaceId="$2"
solutionName="$3"

# Determine if we're running as a user or service principal
echo "Getting signed in user/service principal id"
account_type=$(az account show --query user.type --output tsv 2>/dev/null)

if [ "$account_type" == "user" ]; then
    # Running as a user - get signed-in user ID
    signed_user_id=$(az ad signed-in-user show --query id --output tsv 2>&1)
    if [ -z "$signed_user_id" ] || [[ "$signed_user_id" == *"ERROR"* ]] || [[ "$signed_user_id" == *"InteractionRequired"* ]]; then
        echo "✗ Failed to get signed-in user ID. Token may have expired. Re-authenticating..."
        az login --use-device-code
        signed_user_id=$(az ad signed-in-user show --query id --output tsv)
        if [ -z "$signed_user_id" ]; then
            echo "✗ Failed to get signed-in user ID after re-authentication"
            exit 1
        fi
    fi
    echo "✓ Running as user: $signed_user_id"
elif [ "$account_type" == "servicePrincipal" ]; then
    # Running as a service principal - get SP object ID
    client_id=$(az account show --query user.name --output tsv 2>/dev/null)
    if [ -n "$client_id" ]; then
        signed_user_id=$(az ad sp show --id "$client_id" --query id --output tsv 2>&1)
        # Check if the command failed or returned an empty/erroneous ID
        if [ $? -ne 0 ] || [ -z "$signed_user_id" ] || [[ "$signed_user_id" == *"ERROR"* ]]; then
            echo "✗ Failed to get service principal object ID using client ID: $client_id"
            echo "Azure CLI output:"
            echo "$signed_user_id"
            exit 1
        fi
    else
        echo "✗ Failed to get service principal client ID"
        exit 1
    fi
    echo "✓ Running as service principal: $signed_user_id"
else
    echo "✗ Unknown account type: $account_type"
    exit 1
fi

# Define the scope for the Key Vault (replace with your Key Vault resource ID)
echo "Getting key vault resource id"
key_vault_resource_id=$(az keyvault show --name $keyvaultName --query id --output tsv)

# Check if the key_vault_resource_id is empty
if [ -z "$key_vault_resource_id" ]; then
    echo "Error: Key Vault not found. Please check the Key Vault name."
    exit 1
fi

# Assign the Key Vault Administrator role to the user
echo "Assigning the Key Vault Administrator role to the user..."
az role assignment create --assignee $signed_user_id --role "Key Vault Administrator" --scope $key_vault_resource_id


# Check if the role assignment command was successful
if [ $? -ne 0 ]; then
    echo "Error: Role assignment failed. Please check the provided details and your Azure permissions."
    exit 1
fi
echo "Role assignment completed successfully."

#Replace key vault name and workspace id in the python files
sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "create_fabric_items.py"
sed -i "s/solutionName_to-be-replaced/${solutionName}/g" "create_fabric_items.py"
sed -i "s/workspaceId_to-be-replaced/${fabricWorkspaceId}/g" "create_fabric_items.py"

# sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "notebooks/01_process_data.ipynb"
sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "notebooks/cu/create_cu_template.ipynb"
sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "notebooks/cu/process_cu_data.ipynb"

pip install -r requirements.txt --quiet

python create_fabric_items.py