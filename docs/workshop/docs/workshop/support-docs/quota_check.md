## Check Quota Availability Before Deployment

Before deploying the accelerator, **ensure sufficient quota availability** for the required model.  
Use one of the following scripts based on your needs:  

- **`quota_check_params.sh`** → If you **know the model and capacity** required.  
---
## **If using Azure Portal and Cloud Shell**

1. Navigate to the [Azure Portal](https://portal.azure.com).
2. Click on **Azure Cloud Shell** in the top right navigation menu.
3. Run the appropriate command based on your requirement:  

   **To check quota for a specific model and capacity:**  

    ```sh
    curl -L -o quota_check_params.sh "https://raw.githubusercontent.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/main/infra/scripts/quota_check_params.sh"
    chmod +x quota_check_params.sh
    ./quota_check_params.sh <model_name:capacity> [<model_region>] (e.g., gpt-4o-mini:30,text-embedding-ada-002:20 eastus)
    ```
    
## **If using VS Code or Codespaces**

1. Run the appropriate script based on your requirement:  

   **To check quota for a specific model and capacity:**  

    ```sh
    ./quota_check_params.sh <model_name:capacity> [<model_region>] (e.g., gpt-4o-mini:30,text-embedding-ada-002:20 eastus)
    ```

2. If you see the error `_bash: az: command not found_`, install Azure CLI:  

    ```sh
    curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
    az login
    ```
3. Rerun the script after installing Azure CLI.
   
    **Parameters**
    - `<model_name:capacity>`: The name and required capacity for each model, in the format model_name:capacity (**e.g., gpt-4o-mini:30,text-embedding-ada-002:20**).
    - `[<model_region>] (optional)`: The Azure region to check first. If not provided, all supported regions will be checked (**e.g., eastus**).
