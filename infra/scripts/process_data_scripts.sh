#!/bin/bash

# === Configuration Parameters ===
storageAccountName="$1"
containerName="$2"
managedIdentityClientId="$3"
keyvaultName="$4"
sqlServerName="$5"
sqlDbName="$6"
resourceGroupName="$7"
apiAppManagedIdentityClientId="$8"
apiAppManagedIdentityName="$9"

# Get parameters from azd env, if not provided
if [ -z "$storageAccountName" ]; then
    storageAccountName=$(azd env get-value STORAGE_ACCOUNT_NAME)
fi

if [ -z "$containerName" ]; then
    containerName=$(azd env get-value STORAGE_CONTAINER_NAME)
fi

if [ -z "$managedIdentityClientId" ]; then
    managedIdentityClientId=$(azd env get-value MANAGED_IDENTITY_CLIENT_ID)
fi

if [ -z "$keyvaultName" ]; then
    keyvaultName=$(azd env get-value KEY_VAULT_NAME)
fi

if [ -z "$sqlServerName" ]; then
    sqlServerName=$(azd env get-value SQLDB_SERVER)
fi

if [ -z "$sqlDbName" ]; then
    sqlDbName=$(azd env get-value SQLDB_DATABASE)
fi

if [ -z "$resourceGroupName" ]; then
    resourceGroupName=$(azd env get-value RESOURCE_GROUP_NAME)
fi

if [ -z "$apiAppManagedIdentityClientId" ]; then
    apiAppManagedIdentityClientId=$(azd env get-value API_APP_MANAGED_IDENTITY_CLIENT_ID)
fi

if [ -z "$apiAppManagedIdentityName" ]; then
    apiAppManagedIdentityName=$(azd env get-value API_APP_MANAGED_IDENTITY_NAME)
fi

# Check if all required arguments are provided
if [ -z "$storageAccountName" ] || [ -z "$containerName" ] || [ -z "$managedIdentityClientId" ] || [ -z "$keyvaultName" ] || [ -z "$sqlServerName" ] || [ -z "$sqlDbName" ] || [ -z "$resourceGroupName" ] || [ -z "$apiAppManagedIdentityClientId" ] || [ -z "$apiAppManagedIdentityName" ]; then
    echo "Usage: $0 <storageAccountName> <containerName> <managedIdentityClientId> <keyvaultName> <sqlServerName> <sqlDbName> <resourceGroupName> <apiAppManagedIdentityClientId> <apiAppManagedIdentityName>"
    exit 1
fi

# Extract the SQL server name without the domain
sqlServerName=$(echo "$sqlServerName" | cut -d'.' -f1)

# === Functions ===
log() {
    echo -e "\033[1;32m[INFO]\033[0m $1"
}

error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1" >&2
    exit 1
}

trap 'error "An unexpected error occurred. Please check the logs."' ERR

# === Step 1: Copy KB files ===
log "Running copy_kb_files.sh"
bash infra/scripts/copy_kb_files.sh "$storageAccountName" "$containerName" "$managedIdentityClientId" "$keyvaultName"
if [ $? -ne 0 ]; then
    error "copy_kb_files.sh failed."
fi
log "copy_kb_files.sh completed successfully."

# === Step 2: Run create index scripts ===
log "Creating indexes..."
log "Running run_create_index_scripts.sh"
bash infra/scripts/run_create_index_scripts.sh "$keyvaultName" "$managedIdentityClientId" "$sqlServerName" "$resourceGroupName"
if [ $? -ne 0 ]; then
    error "run_create_index_scripts.sh failed."
fi
log "run_create_index_scripts.sh completed successfully."

# === Step 3: SQL User & Role Setup ===
log "Setting up SQL users and roles..."
bash infra/scripts/add_user_scripts/create_sql_user_and_role.sh "$sqlServerName" "$sqlDbName" "$apiAppManagedIdentityClientId" "$apiAppManagedIdentityName" "$apiAppManagedIdentityClientId" "db_datareader, db_datawriter"

log "Sample data processing completed successfully!"