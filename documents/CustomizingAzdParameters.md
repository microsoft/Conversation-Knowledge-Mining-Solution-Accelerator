## [Optional]: Customizing resource names 

By default this template will use the environment name as the prefix to prevent naming collisions within Azure. The parameters below show the default values. You only need to run the statements below if you need to change the values. 


> To override any of the parameters, run `azd env set <PARAMETER_NAME> <VALUE>` before running `azd up`. On the first azd command, it will prompt you for the environment name. Be sure to choose 3-20 charaters alphanumeric unique name. 

## Parameters

| Name                                      | Type    | Default Value            | Purpose                                                                    |
| ----------------------------------------- | ------- | ------------------------ | -------------------------------------------------------------------------- |
| `AZURE_LOCATION`                          | string  | ` ` *(empty)*            | Sets the Azure region for resource deployment.                             |
| `AZURE_ENV_NAME`                          | string  | `env_name`               | Sets the environment name prefix for all Azure resources.                  |
| `AZURE_CONTENT_UNDERSTANDING_LOCATION`    | string  | `swedencentral`          | Specifies the region for content understanding resources.                  |
| `AZURE_SECONDARY_LOCATION`                | string  | `eastus2`                | Specifies a secondary Azure region.                                        |
| `AZURE_OPEN_AI_MODEL_DEPLOYMENT_TYPE`     | string  | `GlobalStandard`         | Defines the model deployment type (allowed: `Standard`, `GlobalStandard`). |
| `AZURE_OPEN_AI_DEPLOYMENT_MODEL`          | string  | `gpt-4o-mini`            | Specifies the GPT model name (e.g., `gpt-4`, `gpt-4o-mini`).               |
| `AZURE_ENV_MODEL_VERSION`                 | string  | `2024-07-18`             | Sets the Azure model version (allowed: `2024-08-06`, etc.).                |
| `AZURE_OPENAI_API_VERSION`            | string  | `2025-01-01-preview`     | Specifies the API version for Azure OpenAI.                                |
| `AZURE_OPEN_AI_DEPLOYMENT_MODEL_CAPACITY` | integer | `30`                     | Sets the GPT model capacity.                                               |
| `AZURE_OPENAI_EMBEDDING_MODEL`            | string  | `text-embedding-ada-002` | Sets the name of the embedding model to use.                               |
| `AZURE_ENV_IMAGETAG`                      | string  | `latest`        | Sets the image tag (`latest`, `dev`, `hotfix`, etc.).   |
| `AZURE_OPENAI_EMBEDDING_MODEL_CAPACITY`   | integer | `80`                     | Sets the capacity for the embedding model deployment.                      |
| `AZURE_ENV_LOG_ANALYTICS_WORKSPACE_ID`    | string  | ` ` *(empty)*            | Reuses an existing Log Analytics Workspace instead of creating a new one.  |



## How to Set a Parameter

To customize any of the above values, run the following command **before** `azd up`:

```bash
azd env set <PARAMETER_NAME> <VALUE>
```

**Example:**

```bash
azd env set AZURE_LOCATION westus2
```