#!/bin/bash
echo "started the script"

# Variables
baseUrl="$1"
keyvaultName="$2"
managedIdentityClientId="$3"
requirementFile="requirements.txt"
requirementFileUrl=${baseUrl}"infra/scripts/index_scripts/requirements.txt"

echo "Script Started"

curl --output "04_cu_process_data_new_data.py" ${baseUrl}"infra/scripts/index_scripts/04_cu_process_data_new_data.py"
curl --output "content_understanding_client.py" ${baseUrl}"infra/scripts/index_scripts/content_understanding_client.py"
curl --output "ckm-analyzer_config_text.json" ${baseUrl}"infra/data/ckm-analyzer_config_text.json"
curl --output "ckm-analyzer_config_audio.json" ${baseUrl}"infra/data/ckm-analyzer_config_audio.json"

############################################
echo "Installing system packages..."    
apk add --no-cache --virtual .build-deps build-base unixodbc-dev
#Download the desired package(s)
curl -O https://download.microsoft.com/download/e/4/e/e4e67866-dffd-428c-aac7-8d28ddafb39b/msodbcsql17_17.10.6.1-1_amd64.apk
curl -O https://download.microsoft.com/download/e/4/e/e4e67866-dffd-428c-aac7-8d28ddafb39b/mssql-tools_17.10.1.1-1_amd64.apk
#Install the package(s)    
apk add --allow-untrusted msodbcsql17_17.10.6.1-1_amd64.apk
apk add --allow-untrusted mssql-tools_17.10.1.1-1_amd64.apk
############################################

# Download the requirement file
curl --output "$requirementFile" "$requirementFileUrl"

echo "Download completed"

sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "04_cu_process_data_new_data.py"
sed -i "s/mici_to-be-replaced/${managedIdentityClientId}/g" "04_cu_process_data_new_data.py"

pip install -r requirements.txt

python 04_cu_process_data_new_data.py