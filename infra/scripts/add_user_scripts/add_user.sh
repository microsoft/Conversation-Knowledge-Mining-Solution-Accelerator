#!/bin/bash

# Set variables
resource_group=$1
server_name="$2-sql-server"
database_name="$2-sql-db"
chartJsFuncAppName="$2-charts-fn"
ragFuncAppName="$2-rag-fn"

# Ensure that Azure CLI is logged in
echo "Logging in to Azure..."
az login

# Fetch the logged-in user email from Azure CLI
logged_in_user=$(az account show --query "user.name" -o tsv)

echo "Logged-in user: $logged_in_user"

# Check if the logged-in user was successfully fetched
if [ -z "$logged_in_user" ]; then
    echo "No user is logged in to Azure. Please login first."
    exit 1
fi

# Retrieve Object ID for the specified Entra ID user
admin_object_id=$(az ad user show --id "$logged_in_user" --query "id" -o tsv)

echo "Setting Logged In user as ADMIN for SQL Server"

# Set the Entra ID user as the SQL Server Admin
az sql server ad-admin create \
    --resource-group "$resource_group" \
    --server-name "$server_name" \
    --display-name "$logged_in_user" \
    --object-id "$admin_object_id"

echo "Installing dependencies"
pip install -r requirements.txt > /dev/null

python script.py --server "$server_name" --database "$database_name" --chartJsFuncAppName "$chartJsFuncAppName" --ragFuncAppName "$ragFuncAppName"

