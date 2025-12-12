#!/bin/bash

# Variables
storageAccountName="$1"
containerName="$2"
resourceGroupName="$3"

zipFileName1="infra/data/call_transcripts.zip"
extractedFolder1="call_transcripts"

zipFileName2="infra/data/audio_data.zip"
extractedFolder2="audio_data"

echo "Script Started"
echo "Storage Account: $storageAccountName"
echo "Container Name: $containerName"
echo "Resource Group: $resourceGroupName"

# Validate required parameters
if [ -z "$storageAccountName" ] || [ -z "$containerName" ] || [ -z "$resourceGroupName" ]; then
    echo "Error: Missing required parameters."
    echo "Usage: $0 <storageAccountName> <containerName> <resourceGroupName>"
    exit 1
fi

# Extract zip files if they exist
if [ -f "$zipFileName1" ]; then
	echo "Extracting $zipFileName1..."
	unzip -o "$zipFileName1" -d "$extractedFolder1"
else
	echo "Warning: $zipFileName1 not found. Skipping extraction."
fi

if [ -f "$zipFileName2" ]; then
	echo "Extracting $zipFileName2..."
	unzip -o "$zipFileName2" -d "$extractedFolder2"
else
	echo "Warning: $zipFileName2 not found. Skipping extraction."
fi

# Authenticate with Azure
if az account show &> /dev/null; then
	echo "Already authenticated with Azure."
else
    echo "Authenticating with Azure CLI..."
	az login
fi

# Check and assign Storage Blob Data Contributor role to current user
echo "Checking Storage Blob Data Contributor role assignment..."
signed_user_id=$(az ad signed-in-user show --query id --output tsv)
storage_resource_id=$(az storage account show --name "$storageAccountName" --resource-group "$resourceGroupName" --query id --output tsv)

role_assignment=$(MSYS_NO_PATHCONV=1 az role assignment list --assignee $signed_user_id --role "Storage Blob Data Contributor" --scope $storage_resource_id --query "[].roleDefinitionId" -o tsv)
if [ -z "$role_assignment" ]; then
    echo "Assigning Storage Blob Data Contributor role to current user..."
    MSYS_NO_PATHCONV=1 az role assignment create --assignee $signed_user_id --role "Storage Blob Data Contributor" --scope $storage_resource_id --output none
    if [ $? -eq 0 ]; then
        echo "Storage Blob Data Contributor role assigned successfully."
        # Wait a bit for role assignment to propagate
        echo "Waiting for role assignment to propagate..."
        sleep 10
    else
        echo "Failed to assign Storage Blob Data Contributor role."
        exit 1
    fi
else
    echo "User already has Storage Blob Data Contributor role."
fi

# Upload files to storage account
# Using az storage blob upload-batch to upload files with Azure CLI authentication
echo "Uploading call transcripts to storage account..."
if [ -d "$extractedFolder1" ]; then
	az storage blob upload-batch \
		--account-name "$storageAccountName" \
		--destination "$containerName/$extractedFolder1" \
		--source "$extractedFolder1" \
		--auth-mode login \
		--pattern '*' \
		--overwrite
	if [ $? -eq 0 ]; then
		echo "✓ Call transcripts uploaded successfully"
	else
		echo "✗ Failed to upload call transcripts"
		exit 1
	fi
else
	echo "Warning: $extractedFolder1 directory not found. Skipping upload."
fi

echo "Uploading audio data to storage account..."
if [ -d "$extractedFolder2" ]; then
	az storage blob upload-batch \
		--account-name "$storageAccountName" \
		--destination "$containerName/$extractedFolder2" \
		--source "$extractedFolder2" \
		--auth-mode login \
		--pattern '*' \
		--overwrite
	if [ $? -eq 0 ]; then
		echo "✓ Audio data uploaded successfully"
	else
		echo "✗ Failed to upload audio data"
		exit 1
	fi
else
	echo "Warning: $extractedFolder2 directory not found. Skipping upload."
fi

# Create custom data directories for user uploads
echo "Creating custom data directories..."
az storage fs directory create \
	--account-name "$storageAccountName" \
	--file-system "$containerName" \
	--name custom_audiodata \
	--auth-mode login 2>/dev/null || echo "custom_audiodata directory may already exist"

az storage fs directory create \
	--account-name "$storageAccountName" \
	--file-system "$containerName" \
	--name custom_transcripts \
	--auth-mode login 2>/dev/null || echo "custom_transcripts directory may already exist"

echo "✓ Custom data directories created successfully"
echo "Script completed successfully"