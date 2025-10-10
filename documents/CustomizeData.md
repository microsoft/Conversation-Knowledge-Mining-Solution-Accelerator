## Customize the solution with your own data 

If you would like to update the solution to leverage your own data please follow the steps below. 
> Note: you will need to complete the deployment steps [here](./DeploymentGuide.md) before proceeding. 

## Prerequisites: 
1. Your data will need to be in JSON or wav format with the file name formated prefixed with "convo" then a GUID followed by a timestamp. For more examples of the data format, please review the sample transcripts and audio data included [here](/infra/data/)
    * Example: convo_32e38683-bbf7-407e-a541-09b37b77921d_2024-12-07 04%3A00%3A00 


1. Navigate to the storage account in the resource group you are using for this solution. 
2. Open the `data` container

> **Note for WAF-aligned deployments:** If your deployment uses private networking, you'll need to log into a VM within the virtual network to upload files. See [VM login instructions](#how-to-login-to-vm-using-azure-bastion) below.

3. If you have audio files, upload them to `custom_audiodata` folder. If you have call transcript files, upload them to `custom_transcripts` folder.
4. Navigate to the terminal and run the `run_process_data_scripts.sh` to process the new data into the solution with the following commands. 
    ```shell
    cd infra/scripts

    az login

    bash run_process_data_scripts.sh resourcegroupname_param
    ```
    a. resourcegroupname_param - the name of the resource group.

## How to Login to VM Using Azure Bastion

For WAF-aligned deployments with private networking:

1. Navigate to your VM in the Azure portal
2. Click **Connect** → **Bastion**
3. Enter your VM credentials and click **Connect**
4. Once connected, use Azure CLI commands to upload files to the storage account


