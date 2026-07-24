# Check Quota Availability Before Deployment

Before deploying the accelerator, **ensure sufficient quota availability** for the required models.

> **For the GPT chat model — set the capacity to at least 150k tokens for optimal performance. For the embedding model, set at least 80k tokens.**

## Login if you have not done so already

```shell
az login
```

If using VS Code Web:

```shell
az login --use-device-code
```

## 📌 Default Models & Capacities

The quota check script ([infra/scripts/pre-provision/quota_check_params.sh](../infra/scripts/pre-provision/quota_check_params.sh)) checks the following models by default:

```
gpt-5.2:150, gpt-4o-mini:150, gpt-4:150, text-embedding-3-small:80
```

> **Note:** This solution deploys `gpt-5.2` (version `2025-12-11`) for chat/insights and `text-embedding-3-small` for embeddings, both on the `GlobalStandard` SKU. The additional models in the default check are included for convenience when planning capacity.

## 📌 Default Regions

```
australiaeast, swedencentral, southeastasia
```

## Usage Scenarios

- No parameters passed → Default models and capacities will be checked in default regions.
- Only model(s) provided → The script will check for those models in the default regions.
- Only region(s) provided → The script will check default models in the specified regions.
- Both models and regions provided → The script will check those models in the specified regions.
- `--verbose` passed → Enables detailed logging output for debugging and traceability.

## Input Formats

> Use the `--models`, `--regions`, and `--verbose` options for parameter handling:

✔️ Run without parameters to check default models & regions:

```shell
./quota_check_params.sh
```

✔️ Enable verbose logging:

```shell
./quota_check_params.sh --verbose
```

✔️ Check specific model(s) in default regions:

```shell
./quota_check_params.sh --models gpt-5.2:150
```

✔️ Check default models in specific region(s):

```shell
./quota_check_params.sh --regions southeastasia,swedencentral
```

✔️ Passing both models and regions:

```shell
./quota_check_params.sh --models gpt-5.2:150 --regions southeastasia,swedencentral
```

✔️ Multiple models with a single region:

```shell
./quota_check_params.sh --models gpt-5.2:150,text-embedding-3-small:80 --regions swedencentral --verbose
```

## Running the Quota Check

### If using Azure Portal and Cloud Shell

1. Navigate to the [Azure Portal](https://portal.azure.com).
2. Click on **Azure Cloud Shell** in the top right navigation menu.
3. Download and run the quota check script:

    ```sh
    curl -L -o quota_check_params.sh "https://raw.githubusercontent.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/main/infra/scripts/pre-provision/quota_check_params.sh"
    chmod +x quota_check_params.sh
    ./quota_check_params.sh
    ```

### If using VS Code or Codespaces

1. Open the terminal in VS Code or Codespaces.
2. If you're using VS Code, select `Git Bash` / `bash` from the terminal dropdown.
3. Navigate to the script folder and make the script executable:

    ```sh
    cd infra/scripts/pre-provision
    chmod +x quota_check_params.sh
    ```

4. Run the script:

    ```sh
    ./quota_check_params.sh
    ```

5. If you see the error `bash: az: command not found`, install Azure CLI:

    ```sh
    curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
    az login
    ```

    > Note: Use `az login --use-device-code` in VS Code Web.

6. Rerun the script after installing Azure CLI.

The final output lists regions with available quota. You can select any of these regions for deployment.

## Next Steps

Return to the [Deployment Guide](./DeploymentGuide.md) to continue with your deployment.
