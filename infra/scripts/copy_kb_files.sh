#!/bin/bash

# Variables
storageAccount="$1"
fileSystem="$2"
baseUrl="$3"

zipFileName1="call_transcripts.zip"
extractedFolder1="call_transcripts"
zipUrl1=${baseUrl}"infra/data/call_transcripts.zip"

zipFileName2="audio_data.zip"
extractedFolder2="audiodata"
zipUrl2=${baseUrl}"infra/data/audio_data.zip"

# Download the zip file
curl --output "$zipFileName1" "$zipUrl1"
curl --output "$zipFileName2" "$zipUrl2"

# Extract the zip file
unzip /mnt/azscripts/azscriptinput/"$zipFileName1" -d /mnt/azscripts/azscriptinput/"$extractedFolder1"
unzip /mnt/azscripts/azscriptinput/"$zipFileName2" -d /mnt/azscripts/azscriptinput/"$extractedFolder2"


echo "Script Started"

# Authenticate with Azure using managed identity
az login --identity
# Using az storage blob upload-batch to upload files with managed identity authentication, as the az storage fs directory upload command is not working with managed identity authentication.
az storage blob upload-batch --account-name "$storageAccount" --destination data/"$extractedFolder1" --source /mnt/azscripts/azscriptinput/"$extractedFolder1" --auth-mode login --pattern '*'
az storage blob upload-batch --account-name "$storageAccount" --destination data/"$extractedFolder2" --source /mnt/azscripts/azscriptinput/"$extractedFolder2" --auth-mode login --pattern '*'
