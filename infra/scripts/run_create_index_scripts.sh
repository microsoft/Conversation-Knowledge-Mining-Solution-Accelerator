#!/bin/bash
echo "Started the index script setup..."

# Variables
baseUrl="$1"
keyvaultName="$2"
managedIdentityClientId="$3"
requirementFile="requirements.txt"
requirementFileUrl="${baseUrl}infra/scripts/index_scripts/requirements.txt"

# Step 1: Install system dependencies (Alpine Linux style)
echo "Installing system dependencies..."
apk update
apk add --no-cache curl bash jq py3-pip gcc musl-dev libffi-dev openssl-dev python3-dev
apk add --no-cache --virtual .build-deps build-base unixodbc-dev

# Install Microsoft ODBC Driver 18 and SQL tools
echo "Installing MS ODBC 18 drivers and tools..."
curl -s -o msodbcsql18_18.5.1.1-1_amd64.apk https://download.microsoft.com/download/fae28b9a-d880-42fd-9b98-d779f0fdd77f/msodbcsql18_18.5.1.1-1_amd64.apk
curl -s -o mssql-tools18_18.4.1.1-1_amd64.apk https://download.microsoft.com/download/7/6/d/76de322a-d860-4894-9945-f0cc5d6a45f8/mssql-tools18_18.4.1.1-1_amd64.apk
apk add --allow-untrusted msodbcsql18_18.5.1.1-1_amd64.apk
apk add --allow-untrusted mssql-tools18_18.4.1.1-1_amd64.apk

# Step 2: Download index scripts
echo "Downloading index scripts..."
curl --output "01_create_search_index.py" "${baseUrl}infra/scripts/index_scripts/01_create_search_index.py"
curl --output "02_create_cu_template_text.py" "${baseUrl}infra/scripts/index_scripts/02_create_cu_template_text.py"
curl --output "02_create_cu_template_audio.py" "${baseUrl}infra/scripts/index_scripts/02_create_cu_template_audio.py"
curl --output "03_cu_process_data_text.py" "${baseUrl}infra/scripts/index_scripts/03_cu_process_data_text.py"
curl --output "content_understanding_client.py" "${baseUrl}infra/scripts/index_scripts/content_understanding_client.py"
curl --output "azure_credential_utils.py" "${baseUrl}infra/scripts/index_scripts/azure_credential_utils.py"
curl --output "ckm-analyzer_config_text.json" "${baseUrl}infra/data/ckm-analyzer_config_text.json"
curl --output "ckm-analyzer_config_audio.json" "${baseUrl}infra/data/ckm-analyzer_config_audio.json"
curl --output "sample_processed_data.json" "${baseUrl}infra/data/sample_processed_data.json"
curl --output "sample_processed_data_key_phrases.json" "${baseUrl}infra/data/sample_processed_data_key_phrases.json"
curl --output "sample_search_index_data.json" "${baseUrl}infra/data/sample_search_index_data.json"

# Step 3: Download and install Python requirements
echo "Installing Python requirements..."
curl --output "$requirementFile" "$requirementFileUrl"
pip install --upgrade pip
pip install -r "$requirementFile"

# Step 4: Replace placeholder values with actuals
echo "Substituting key vault and identity details..."
#Replace key vault name 
sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "01_create_search_index.py"
sed -i "s/mici_to-be-replaced/${managedIdentityClientId}/g" "01_create_search_index.py"
sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "02_create_cu_template_text.py"
sed -i "s/mici_to-be-replaced/${managedIdentityClientId}/g" "02_create_cu_template_text.py"
sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "02_create_cu_template_audio.py"
sed -i "s/mici_to-be-replaced/${managedIdentityClientId}/g" "02_create_cu_template_audio.py"
sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "03_cu_process_data_text.py"
sed -i "s/mici_to-be-replaced/${managedIdentityClientId}/g" "03_cu_process_data_text.py"


# Step 5: Execute the Python scripts
echo "Running Python index scripts..."
python 01_create_search_index.py
python 02_create_cu_template_text.py
python 02_create_cu_template_audio.py
python 03_cu_process_data_text.py

echo "Index script setup completed successfully."