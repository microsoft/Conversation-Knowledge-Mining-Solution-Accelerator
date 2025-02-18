#!/bin/bash
echo "starting script"

# Variables
keyvaultName="$1"
fabricWorkspaceId="$2"
solutionName="$3"

# get signed user
echo "Getting signed in user id"
signed_user_id=$(az ad signed-in-user show --query id -o tsv)

# Check if the user_id is empty
if [ -z "$signed_user_id" ]; then
    echo "Error: User ID not found. Please check the user principal name or email address."
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