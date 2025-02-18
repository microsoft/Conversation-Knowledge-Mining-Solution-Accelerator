from azure.identity import DefaultAzureCredential
import base64
import json
import requests
import pandas as pd
import os
from glob import iglob
import zipfile
import time


# credential = DefaultAzureCredential()
from azure.identity import AzureCliCredential
credential = AzureCliCredential()

cred = credential.get_token('https://api.fabric.microsoft.com/.default')
token = cred.token

fabric_headers = {"Authorization": "Bearer " + token.strip()}

key_vault_name = 'kv_to-be-replaced'
workspaceId = "workspaceId_to-be-replaced"
solutionname = "solutionName_to-be-replaced"
create_workspace = False

# pipeline_notebook_name = 'pipeline_notebook'
pipeline_notebook_name = 'cu_pipeline_notebook'
pipeline_name = 'data_pipeline'
lakehouse_name = 'lakehouse_' + solutionname

print("workspace id: " ,workspaceId)

if create_workspace == True:
  workspace_name = 'workspace_' + solutionname

  # create workspace
  ws_url = 'https://api.fabric.microsoft.com/v1/workspaces'

  ws_data = {
    "displayName": workspace_name
  }
  ws_res = requests.post(ws_url, headers=fabric_headers, json=ws_data)
  ws_details = ws_res.json()
  # print(ws_details['id'])
  workspaceId = ws_details['id']

fabric_base_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/"
fabric_items_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/items/"

fabric_create_workspace_url = f"https://api.fabric.microsoft.com/v1/workspaces"

#get workspace name
ws_res = requests.get(fabric_base_url, headers=fabric_headers)
workspace_name = ws_res.json()['displayName']

#create lakehouse
lakehouse_data = {
  "displayName": lakehouse_name,
  "type": "Lakehouse"
}
lakehouse_res = requests.post(fabric_items_url, headers=fabric_headers, json=lakehouse_data)

# print("lakehouse name: ", lakehouse_name)

# copy local files to lakehouse
from azure.storage.filedatalake import (
    DataLakeServiceClient
)

account_name = "onelake" #always onelake
data_path = f"{lakehouse_name}.Lakehouse/Files/"
folder_path = "/"

account_url = f"https://{account_name}.dfs.fabric.microsoft.com"
service_client = DataLakeServiceClient(account_url, credential=credential)

#Create a file system client for the workspace
file_system_client = service_client.get_file_system_client(workspace_name)

directory_client = file_system_client.get_directory_client(f"{data_path}/{folder_path}")

print('uploading files')
# upload audio files
data_folder_path = os.path.join("..", "..", "data", "audio_data")
file_names = zip_files = list(iglob(os.path.join(data_folder_path, "audio*.zip")))
for file_name in file_names:
    # Check if the file is a zip file
    if file_name.endswith('.zip'):
        # print('checking if filename ends in zip')
        # Extract files from the zip folder
        with zipfile.ZipFile(file_name, 'r') as zip_ref:
            # print('zip file')
            extract_dir = f"{file_name}_extracted"
            zip_ref.extractall(extract_dir)
        
        local_path = extract_dir
        # print('ex dir', extract_dir)
        # upload extracted folder
        file_names = [f for f in iglob(os.path.join(local_path, "**", "*"), recursive=True) if os.path.isfile(f)]
        # print('file_names ex', file_names)
        for file_name in file_names:
            upload_file_name = os.path.basename(file_name)
            file_client = directory_client.get_file_client("cu_audio_files_all/" + upload_file_name)
            # with open(file=os.path.join(extract_dir, file_name), mode="rb") as data:
            with open(file=file_name, mode="rb") as data:
                # print('data', data)
                file_client.upload_data(data, overwrite=True)


# upload content understanding json file
folder_path = '/cu_analyzer_file'
local_path = os.path.join("..", "cu_scripts", "*.json")

file_names = [f for f in iglob(local_path) if os.path.isfile(f)]

for file_name in file_names:
  base_name = os.path.basename(file_name)
  path = f"{folder_path}/{base_name}"

  file_client = directory_client.get_file_client(path)
  with open(file=file_name, mode="rb") as data:
    file_client.upload_data(data, overwrite=True)

#get environments
try:
  fabric_env_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/environments/"
  env_res = requests.get(fabric_env_url, headers=fabric_headers)
  env_res_id = env_res.json()['value'][0]['id']
  # print(env_res.json())
except:
  env_res_id = ''

#create notebook items
# notebook_names =['pipeline_notebook','01_process_data','02_create_calendar_data']
notebook_names = ['cu_pipeline_notebook', 'create_cu_template', 'process_cu_data']
# notebook_names =['process_data_new']

# add sleep timer
time.sleep(120)  # 1 minute

for notebook_name in notebook_names:
    with open('notebooks/cu/'+ notebook_name +'.ipynb', 'r') as f:
        notebook_json = json.load(f)

    print("lakehouse_res")
    print(lakehouse_res)
    print(lakehouse_res.json())
    
    try:
        notebook_json['metadata']['dependencies']['lakehouse']['default_lakehouse'] = lakehouse_res.json()['id']
        notebook_json['metadata']['dependencies']['lakehouse']['default_lakehouse_name'] = lakehouse_res.json()['displayName']
        notebook_json['metadata']['dependencies']['lakehouse']['default_lakehouse_workspace_id'] = lakehouse_res.json()['workspaceId']
    except:
        pass
    
    if env_res_id != '':
        try:
            notebook_json['metadata']['dependencies']['environment']['environmentId'] = env_res_id
            notebook_json['metadata']['dependencies']['environment']['workspaceId'] = lakehouse_res.json()['workspaceId']
        except:
            pass


    notebook_base64 = base64.b64encode(json.dumps(notebook_json).encode('utf-8'))
    
    notebook_data = {
        "displayName":notebook_name,
        "type":"Notebook",
        "definition" : {
            "format": "ipynb",
            "parts": [
                {
                    "path": "notebook-content.ipynb",
                    "payload": notebook_base64.decode('utf-8'),
                    "payloadType": "InlineBase64"
                }
            ]
        }
    }
    
    fabric_response = requests.post(fabric_items_url, headers=fabric_headers, json=notebook_data)
    #print(fabric_response.json())

time.sleep(120)

# get wrapper notebook id
fabric_notebooks_url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspaceId}/notebooks"
notebooks_res = requests.get(fabric_notebooks_url, headers=fabric_headers)
notebooks_res.json()

pipeline_notebook_id = ''
print("notebook_res.json.values: ", notebooks_res.json().values())
for n in notebooks_res.json().values():
    for notebook in n:
        print("notebook displayname", notebook['displayName'])
        if notebook['displayName'] == pipeline_notebook_name:
            pipeline_notebook_id = notebook['id']
            break
print("pipeline_notebook_id: ", pipeline_notebook_id)


# create pipeline item
pipeline_json = {
    "name": pipeline_name,
    "properties": {
        "activities": [
            {
                "name": "process_data",
                "type": "TridentNotebook",
                "dependsOn": [],
                "policy": {
                    "timeout": "0.12:00:00",
                    "retry": 0,
                    "retryIntervalInSeconds": 30,
                    "secureOutput": "false",
                    "secureInput": "false"
                },
                "typeProperties": {
                    "notebookId": pipeline_notebook_id,
                    "workspaceId": workspaceId
                }
            }
        ]
    }
}

pipeline_base64 = base64.b64encode(json.dumps(pipeline_json).encode('utf-8'))

pipeline_data = {
        "displayName":pipeline_name,
        "type":"DataPipeline",
        "definition" : {
            # "format": "json",
            "parts": [
                {
                    "path": "pipeline-content.json",
                    "payload": pipeline_base64.decode('utf-8'),
                    "payloadType": "InlineBase64"
                }
            ]
        }
    }

pipeline_response = requests.post(fabric_items_url, headers=fabric_headers, json=pipeline_data)
pipeline_response.json()

# run the pipeline once
job_url = fabric_base_url + f"items/{pipeline_response.json()['id']}/jobs/instances?jobType=Pipeline"
job_response = requests.post(job_url, headers=fabric_headers)