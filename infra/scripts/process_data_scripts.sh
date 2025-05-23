#!/bin/bash
echo "started the script"

# Variables
baseUrl="$1"
keyvaultName="$2"
requirementFile="requirements.txt"
requirementFileUrl=${baseUrl}"infra/scripts/index_scripts/requirements.txt"

echo "Script Started"

# Download the create_index and create table python files
# curl --output "01_create_search_index.py" ${baseUrl}"infra/scripts/index_scripts/01_create_search_index.py"
# curl --output "02_create_cu_template_text.py" ${baseUrl}"infra/scripts/index_scripts/02_create_cu_template_text.py"
# curl --output "02_create_cu_template_audio.py" ${baseUrl}"infra/scripts/index_scripts/02_create_cu_template_audio.py"
# curl --output "03_cu_process_data_text.py" ${baseUrl}"infra/scripts/index_scripts/03_cu_process_data_text.py"
curl --output "04_cu_process_data_new_data.py" ${baseUrl}"infra/scripts/index_scripts/04_cu_process_data_new_data.py"
curl --output "content_understanding_client.py" ${baseUrl}"infra/scripts/index_scripts/content_understanding_client.py"
curl --output "ckm-analyzer_config_text.json" ${baseUrl}"infra/data/ckm-analyzer_config_text.json"
curl --output "ckm-analyzer_config_audio.json" ${baseUrl}"infra/data/ckm-analyzer_config_audio.json"

# curl --output "sample_processed_data.json" ${baseUrl}"infra/data/sample_processed_data.json"
# curl --output "sample_processed_data_key_phrases.json" ${baseUrl}"infra/data/sample_processed_data_key_phrases.json"
# curl --output "sample_search_index_data.json" ${baseUrl}"infra/data/sample_search_index_data.json"

# RUN apt-get update
# RUN apt-get install python3 python3-dev g++ unixodbc-dev unixodbc libpq-dev
# apk add python3 python3-dev g++ unixodbc-dev unixodbc libpq-dev
 
# # RUN apt-get install python3 python3-dev g++ unixodbc-dev unixodbc libpq-dev
# pip install pyodbc

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

#Replace key vault name 
# sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "01_create_search_index.py"
# sed -i "s/mici_to-be-replaced/${managedIdentityClientId}/g" "01_create_search_index.py"
# sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "02_create_cu_template_text.py"
# sed -i "s/mici_to-be-replaced/${managedIdentityClientId}/g" "02_create_cu_template_text.py"
# sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "02_create_cu_template_audio.py"
# sed -i "s/mici_to-be-replaced/${managedIdentityClientId}/g" "02_create_cu_template_audio.py"
# sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "03_cu_process_data_text.py"
# sed -i "s/mici_to-be-replaced/${managedIdentityClientId}/g" "03_cu_process_data_text.py"

sed -i "s/kv_to-be-replaced/${keyvaultName}/g" "04_cu_process_data_new_data.py"

pip install -r requirements.txt

# python 01_create_search_index.py
# python 02_create_cu_template_text.py
# python 02_create_cu_template_audio.py
# python 03_cu_process_data_text.py
python 04_cu_process_data_new_data.py