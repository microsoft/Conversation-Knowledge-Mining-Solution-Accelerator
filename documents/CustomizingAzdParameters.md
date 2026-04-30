## [Optional]: Customizing resource names 

By default this template will use the environment name as the prefix to prevent naming collisions within Azure. The parameters below show the default values. You only need to run the statements below if you need to change the values. 


> To override any of the parameters, run `azd env set <PARAMETER_NAME> <VALUE>` before running `azd up`. On the first azd command, it will prompt you for the environment name. Be sure to choose 3-20 charaters alphanumeric unique name. 

## Parameters

| Name                                      | Type    | Default Value            | Purpose                                                                    |
| ----------------------------------------- | ------- | ------------------------ | -------------------------------------------------------------------------- |
| `AZURE_LOCATION`                          | string  | ` `            | Sets the Azure region for resource deployment.                             |
| `AZURE_ENV_NAME`                          | string  | `env_name`               | Sets the environment name prefix for all Azure resources.                  |
| `AZURE_ENV_AI_SERVICE_LOCATION`                | string  | `eastus2`                | Specifies the Azure AI service location.                                        |
| `AZURE_ENV_SECONDARY_LOCATION`                | string  | `eastus2`                | Specifies a secondary Azure region.                                        |
| `AZURE_ENV_MODEL_DEPLOYMENT_TYPE`     | string  | `GlobalStandard`         | Defines the model deployment type (allowed: `Standard`, `GlobalStandard`). |
| `AZURE_ENV_GPT_MODEL_NAME`          | string  | `gpt-4.1`            | Specifies the GPT model name (e.g., `gpt-4.1`, `gpt-4o-mini`, etc.).               |
| `AZURE_ENV_GPT_MODEL_VERSION`                 | string  | `2025-04-14`             | Sets the Azure model version (e.g., `2025-04-14`, etc.).                |
| `AZURE_ENV_GPT_MODEL_CAPACITY` | integer | `30`                     | Sets the GPT model capacity.                                               |
| `AZURE_ENV_EMBEDDING_MODEL_NAME`            | string  | `text-embedding-3-small` | Sets the name of the embedding model to use.                               |
| `AZURE_ENV_IMAGE_TAG`                      | string  | `latest_afv2`        | Sets the image tag (`latest_afv2`, `dev`, `hotfix`, etc.).   |
| `AZURE_ENV_EMBEDDING_DEPLOYMENT_CAPACITY`   | integer | `80`                     | Sets the capacity for the embedding model deployment.                      |
| `AZURE_ENV_EXISTING_LOG_ANALYTICS_WORKSPACE_RID`    | string  | Guide to get your [Existing Workspace ID](/documents/re-use-log-analytics.md)            | Reuses an existing Log Analytics Workspace instead of creating a new one.  |
| `USE_LOCAL_BUILD`    | string  | `false`           | Indicates whether to use a local container build for deployment.  |
| `AZURE_EXISTING_AIPROJECT_RESOURCE_ID`    | string  | `<Existing AI Project resource Id>`            | Reuses an existing AIFoundry and AIFoundryProject instead of creating a new one.  |
| `AZURE_ENV_VM_ADMIN_USERNAME`  | string | `take(newGuid(), 20)`               | The administrator username for the virtual machine.         |
| `AZURE_ENV_VM_ADMIN_PASSWORD`  | string | `newGuid()`               | The administrator password for the virtual machine.         |
| `AZURE_ENV_VM_SIZE`  | string | `Standard_D2s_v5`               | The size/SKU of the Jumpbox Virtual Machine (e.g., `Standard_D2s_v5`, `Standard_DS2_v2`).         |
| `AZURE_ENV_CONTAINER_REGISTRY_ENDPOINT`  | string | `<Container Registry Endpoint>`               | The hostname/endpoint for the container registry used by both backend and frontend containers.         |


## How to Set a Parameter

To customize any of the above values, run the following command **before** `azd up`:

```bash
azd env set <PARAMETER_NAME> <VALUE>
```

**Example:**

```bash
azd env set AZURE_LOCATION westus2
```
