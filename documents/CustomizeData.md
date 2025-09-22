## Customize the solution with your own data 

If you would like to update the solution to leverage your own data please follow the steps below. 
> Note: you will need to complete the deployment steps [here](./DeploymentGuide.md) before proceeding. 

## Prerequisites: 
1. Your data will need to be in JSON or wav format with the file name formated prefixed with "convo" then a GUID followed by a timestamp. For more examples of the data format, please review the sample transcripts and audio data included [here](/infra/data/)
    * Example: convo_32e38683-bbf7-407e-a541-09b37b77921d_2024-12-07 04%3A00%3A00 


1. Navigate to the storage account in the resource group you are using for this solution. 
2. Open the `data` container
3. If you have audio files, upload them to `custom_audiodata` folder. If you have call transcript files, upload them to `custom_transcripts` folder.
4. Navigate to the terminal and run the `run_process_data_scripts.sh` to process the new data into the solution with the following commands. 
    ```shell
    cd infra/scripts

    az login

    bash run_process_data_scripts.sh resourcegroupname_param
    ```
    a. resourcegroupname_param - the name of the resource group.

> Note (WAF‑aligned deployments): If you deployed the solution with the WAF / private networking option enabled, you must run the data processing script **from inside the deployed VM (jumpbox / processing VM)** so it can reach the private endpoints. Follow these steps:
>
> 1. Connect to the VM (Azure Bastion, SSH, or RDP depending on OS).
> 2. Ensure the repo (or the `infra/scripts` folder) is present. If not, clone or pull it.
> 3. Open a Bash-compatible shell (Git Bash on Windows, or native bash on Linux).
> 4. Run `az login` (add `--tenant <tenantId>` if required by your org policy).
> 5. Navigate to `infra/scripts` and execute:
>    ```bash
>    bash run_process_data_scripts.sh <resource-group-name>
>    ```
> 6. Replace `<resource-group-name>` with the name of the resource group you deployed (same value used for `resourcegroupname_param`).
>
> Tip: If Azure CLI is not installed on the VM, install it first (see official docs) before running the script.

