### Fabric deployment is not currently used in this accelerator. The steps below are not applicable and can be ignored, as this functionality is still in development.

### How to customize 

If you'd like to customize the solution accelerator, here are some ways you might do that:
1. Ingest your own [audio conversation files](./ConversationalDataFormat.md) by uploading them into the `cu_audio_files_all` lakehouse folder and run the data pipeline
2. Deploy with Microsoft Fabric by following the steps in [Fabric_deployment.md](./Fabric_deployment.md)


3.  **Create or Use an Existing Microsoft Fabric Workspace**

    > ℹ️ **Note:** If you already have an existing Microsoft Fabric Workspace, you can skip workspace creation and **continue from Point 5 (Environment Creation)**.
    1.  Navigate to ([Fabric Workspace](https://app.fabric.microsoft.com/))
    2.  Click on Data Engineering experience
    3.  Click on Workspaces from left Navigation
    4.  Click on + New Workspace
        1.  Provide Name of Workspace 
        2.  Provide Description of Workspace (optional)
        3.  Click Apply
    5.  Open Workspace
    6.  Create Environment
        1.  Click ` + New Item ` (in Workspace)
        2.  Select Environment from list
        3.  Provide name for Environment and click Create
        4.  Select Public libraries in left panel
        5.  Click Add from .yml
        6.  Upload .yml from [here](.././infra/scripts/fabric_scripts/ckm_cu_env.yml)
        7.  Click Publish
    7.  Retrieve Workspace ID from URL, refer to documentation additional assistance ([here](https://learn.microsoft.com/en-us/fabric/admin/portal-workspace#identify-your-workspace-id))

    ***Note: Wait until the Environment is finished publishing prior to proceeding with the next steps.

4.  **Deploy Fabric resources and artifacts**
    1.   Navigate to ([Azure Portal](https://portal.azure.com/))
    2.   Click on Azure Cloud Shell in the top right of navigation Menu (add image)
    3.   Run the run the following commands:  
         1.   ```az login``` ***Follow instructions in Azure Cloud Shell for login instructions
         2.   ```rm -rf ./Conversation-Knowledge-Mining-Solution-Accelerator```
         3.   ```git clone https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator```
         4.   ```cd ./Conversation-Knowledge-Mining-Solution-Accelerator/Deployment/scripts/fabric_scripts```
         5.   ```sh ./run_fabric_items_scripts.sh keyvault_param workspaceid_param solutionprefix_param```
              1.   keyvault_param - the name of the keyvault that was created in Step 1
              2.   workspaceid_param - Existing workspaceid or workspaceid created in Step 3
              3.   solutionprefix_param - prefix used to append to lakehouse upon creation
5.  **Add App Authentication**
   
    Follow steps in [App Authentication](./AppAuthentication.md) to configure authentication in app service.

### Upload additional files

All files WAV files can be uploaded in the corresponding Lakehouse in the data/Files folder:

- Audio (WAV files):
  Upload Audio files in the *cu_audio_files_all* folder.

### Post-deployment
- To process additional files, manually execute the pipeline_notebook after uploading new files.
- The OpenAI prompt can be modified within the Fabric notebooks.
