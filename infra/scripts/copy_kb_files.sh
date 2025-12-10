#!/bin/bash

# Variables
storageAccount="$1"
baseUrl="$2"
managedIdentityClientId="$3"

zipFileName1="infra/data/call_transcripts.zip"
extractedFolder1="call_transcripts"
zipUrl1=${baseUrl}"infra/data/call_transcripts.zip"

zipFileName2="infra/data/audio_data.zip"
extractedFolder2="audio_data"
zipUrl2=${baseUrl}"infra/data/audio_data.zip"

# Extract the zip file
unzip "$zipFileName1" -d "$extractedFolder1"
unzip "$zipFileName2" -d "$extractedFolder2"

echo "Script Started"

# Authenticate with Azure using managed identity
az login
# Using az storage blob upload-batch to upload files with managed identity authentication, as the az storage fs directory upload command is not working with managed identity authentication.
az storage blob upload-batch --account-name "$storageAccount" --destination data/"$extractedFolder1" --source "$extractedFolder1" --auth-mode login --pattern '*' --overwrite
az storage blob upload-batch --account-name "$storageAccount" --destination data/"$extractedFolder2" --source "$extractedFolder2" --auth-mode login --pattern '*' --overwrite
az storage fs directory create --account-name "$storageAccount" --file-system data --name custom_audiodata --auth-mode login
az storage fs directory create --account-name "$storageAccount" --file-system data --name custom_transcripts --auth-mode login