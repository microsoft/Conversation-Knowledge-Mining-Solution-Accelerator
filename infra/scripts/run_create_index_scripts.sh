#!/bin/bash
set -euo pipefail

echo "Started the index script setup..."

# Variables
baseUrl="${1:-}"
keyvaultName="${2:-}"
managedIdentityClientId="${3:-}"
requirementFile="requirements.txt"
requirementFileUrl="${baseUrl}infra/scripts/index_scripts/requirements.txt"

# Basic validation
if [ -z "$baseUrl" ]; then
  echo "ERROR: baseUrl (argument 1) is required"
  exit 2
fi

curl_opts="-fSL --retry 3 --retry-delay 2 --max-time 60"

echo "Installing system dependencies..."
apk update
apk add --no-cache curl bash jq py3-pip gcc musl-dev libffi-dev openssl-dev python3-dev
apk add --no-cache --virtual .build-deps build-base unixodbc-dev

# Install Microsoft ODBC and SQL tools
echo "Installing MS ODBC drivers and tools..."
curl $curl_opts -o msodbcsql17_17.10.6.1-1_amd64.apk https://download.microsoft.com/download/e/4/e/e4e67866-dffd-428c-aac7-8d28ddafb39b/msodbcsql17_17.10.6.1-1_amd64.apk
curl $curl_opts -o mssql-tools_17.10.1.1-1_amd64.apk https://download.microsoft.com/download/e/4/e/e4e67866-dffd-428c-aac7-8d28ddafb39b/mssql-tools_17.10.1.1-1_amd64.apk
apk add --allow-untrusted msodbcsql17_17.10.6.1-1_amd64.apk
apk add --allow-untrusted mssql-tools_17.10.1.1-1_amd64.apk

# Step 2: Download index scripts (use -f to fail on 404s)
echo "Downloading index scripts..."

# helper to download and validate
_download() {
  local url="$1" dest="$2"
  echo "  -> $url"
  curl $curl_opts -o "$dest" "$url" || { echo "Failed to download $url" >&2; return 1; }
  if [ ! -s "$dest" ]; then
    echo "Downloaded $dest but file is empty" >&2
    return 1
  fi
  echo "Downloaded $dest ($(stat -c%s "$dest") bytes)"
}

# Files to fetch
_download "${baseUrl}infra/scripts/index_scripts/01_create_search_index.py" "01_create_search_index.py"
_download "${baseUrl}infra/scripts/index_scripts/02_create_cu_template_text.py" "02_create_cu_template_text.py"
_download "${baseUrl}infra/scripts/index_scripts/02_create_cu_template_audio.py" "02_create_cu_template_audio.py"
_download "${baseUrl}infra/scripts/index_scripts/03_cu_process_data_text.py" "03_cu_process_data_text.py"
_download "${baseUrl}infra/scripts/index_scripts/content_understanding_client.py" "content_understanding_client.py"
_download "${baseUrl}infra/scripts/index_scripts/azure_credential_utils.py" "azure_credential_utils.py"

_download "${baseUrl}infra/data/ckm-analyzer_config_text.json" "ckm-analyzer_config_text.json"
_download "${baseUrl}infra/data/ckm-analyzer_config_audio.json" "ckm-analyzer_config_audio.json"
_download "${baseUrl}infra/data/sample_processed_data.json" "sample_processed_data.json"
_download "${baseUrl}infra/data/sample_processed_data_key_phrases.json" "sample_processed_data_key_phrases.json"
_download "${baseUrl}infra/data/sample_search_index_data.json" "sample_search_index_data.json"

# Step 3: Download and install Python requirements
echo "Installing Python requirements..."
_download "${requirementFileUrl}" "$requirementFile"

# Use the same interpreter for pip to avoid mismatches
python3 -V || { echo "python3 not found" >&2; exit 3; }
python3 -m pip install --upgrade pip
python3 -m pip install -r "$requirementFile"

# Step 4: Replace placeholder values with actuals
echo "Substituting key vault and identity details..."

# Replace key vault and managed identity placeholders in the downloaded scripts
for f in "01_create_search_index.py" "02_create_cu_template_text.py" "02_create_cu_template_audio.py" "03_cu_process_data_text.py"; do
  if [ -f "$f" ]; then
    sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "$f" || true
    sed -i "s/mici_to-be-replaced/${managedIdentityClientId}/g" "$f" || true
  fi
done

# Step 5: Execute the Python scripts and fail fast if any script errors
echo "Running Python index scripts..."

for s in "01_create_search_index.py" "02_create_cu_template_text.py" "02_create_cu_template_audio.py" "03_cu_process_data_text.py"; do
  if [ ! -f "$s" ]; then
    echo "Expected script $s not found" >&2
    exit 4
  fi
  echo "--- Running $s ---"
  python3 -u "$s"
  echo "--- Completed $s ---"
done

echo "Index script setup completed successfully."