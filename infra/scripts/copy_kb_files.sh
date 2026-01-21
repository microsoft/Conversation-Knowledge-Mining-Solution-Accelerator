#!/bin/bash

# Variables
storageAccountName="$1"
containerName="$2"
resourceGroupName="$3"
usecase="$4"

if [ -z "$usecase" ]; then
	usecase="telecom"
fi

if [ "$usecase" == "telecom" ]; then
	zipFileName1="infra/data/telecom/call_transcripts.zip"
	zipFileName2="infra/data/telecom/audio_data.zip"
	extractedFolder2="audio_data"
elif [ "$usecase" == "IT_helpdesk" ]; then
	zipFileName1="infra/data/IT_helpdesk/call_transcripts.zip"
fi

extractedFolder1="call_transcripts"



# Validate required parameters
if [ -z "$storageAccountName" ] || [ -z "$containerName" ] || [ -z "$resourceGroupName" ] || [ -z "$usecase" ]; then
    echo "Error: Missing required parameters."
    echo "Usage: $0 <storageAccountName> <containerName> <resourceGroupName> <usecase>"
    exit 1
fi

# Extract zip files if they exist
if [ -f "$zipFileName1" ]; then
	unzip -q -o "$zipFileName1" -d "$extractedFolder1"
fi

if [ "$usecase" == "telecom" ]; then
	if [ -f "$zipFileName2" ]; then
		unzip -q -o "$zipFileName2" -d "$extractedFolder2"
	fi
fi 
# Authenticate with Azure
if ! az account show &> /dev/null; then
    echo "Authenticating with Azure CLI..."
	az login --use-device-code
fi

# Check and assign Storage Blob Data Contributor role to current identity (user or service principal)
# First, determine if we're running as a user or service principal
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
        signed_user_id=$(az ad sp show --id "$client_id" --query id --output tsv 2>/dev/null)
    fi
    if [ -z "$signed_user_id" ]; then
        echo "✗ Failed to get service principal object ID"
        exit 1
    fi
    echo "✓ Running as service principal: $signed_user_id"
else
    echo "✗ Unknown account type: $account_type"
    exit 1
fi

storage_resource_id=$(az storage account show --name "$storageAccountName" --resource-group "$resourceGroupName" --query id --output tsv)
if [ -z "$storage_resource_id" ]; then
    echo "✗ Failed to get storage account resource ID"
    exit 1
fi

role_assignment=$(MSYS_NO_PATHCONV=1 az role assignment list --assignee $signed_user_id --role "Storage Blob Data Contributor" --scope $storage_resource_id --query "[].roleDefinitionId" -o tsv)
if [ -z "$role_assignment" ]; then
    echo "✓ Assigning Storage Blob Data Contributor role"
    MSYS_NO_PATHCONV=1 az role assignment create --assignee $signed_user_id --role "Storage Blob Data Contributor" --scope $storage_resource_id --output none
    if [ $? -ne 0 ]; then
        echo "✗ Failed to assign Storage Blob Data Contributor role"
        exit 1
    fi
fi

# Wait for role assignment to propagate by testing storage access
echo "⏳ Waiting for role assignment to propagate..."
max_retries=30
retry_count=0
while [ $retry_count -lt $max_retries ]; do
    if az storage container list --account-name "$storageAccountName" --auth-mode login --output none 2>/dev/null; then
        echo "✓ Role assignment propagated successfully"
        break
    fi
    retry_count=$((retry_count + 1))
    echo "  Attempt $retry_count/$max_retries - waiting 10 seconds..."
    sleep 10
done

if [ $retry_count -eq $max_retries ]; then
    echo "✗ Role assignment did not propagate within expected time"
    exit 1
fi

# Upload files to storage account with retry logic
upload_with_retry() {
    local source_folder="$1"
    local dest_path="$2"
    local description="$3"
    local upload_retries=5
    local upload_attempt=0
    
    while [ $upload_attempt -lt $upload_retries ]; do
        if az storage blob upload-batch \
            --account-name "$storageAccountName" \
            --destination "$dest_path" \
            --source "$source_folder" \
            --auth-mode login \
            --pattern '*' \
            --overwrite \
            --output none 2>/dev/null; then
            echo "✓ Uploaded $description successfully"
            return 0
        fi
        upload_attempt=$((upload_attempt + 1))
        echo "  Upload attempt $upload_attempt/$upload_retries failed - waiting 15 seconds..."
        sleep 15
    done
    echo "✗ Failed to upload $description after $upload_retries attempts"
    return 1
}

if [ -d "$extractedFolder1" ]; then
	echo "⏳ Uploading call transcripts..."
	if ! upload_with_retry "$extractedFolder1" "$containerName/$extractedFolder1" "call transcripts"; then
		exit 1
	fi
fi

if [ "$usecase" == "telecom" ]; then
	if [ -d "$extractedFolder2" ]; then
		echo "⏳ Uploading audio data..."
		if ! upload_with_retry "$extractedFolder2" "$containerName/$extractedFolder2" "audio data"; then
			exit 1
		fi
	fi
fi

# Create custom data directories for user uploads
az storage fs directory create \
	--account-name "$storageAccountName" \
	--file-system "$containerName" \
	--name custom_audiodata \
	--auth-mode login --output none 2>/dev/null

az storage fs directory create \
	--account-name "$storageAccountName" \
	--file-system "$containerName" \
	--name custom_transcripts \
	--auth-mode login --output none 2>/dev/null