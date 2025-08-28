## [Optional]: Customizing resource names 

By default this template will use the environment name as the prefix to prevent naming collisions within Azure. The parameters below show the default values. You only need to run the statements below if you need to change the values. 


> To override any of the parameters, run `azd env set <PARAMETER_NAME> <VALUE>` before running `azd up`. On the first azd command, it will prompt you for the environment name. Be sure to choose 3-20 charaters alphanumeric unique name. 

## Parameters

| Name                                      | Type    | Default Value            | Purpose                                                                    |
| ----------------------------------------- | ------- | ------------------------ | -------------------------------------------------------------------------- |
| `AZURE_LOCATION`                          | string  | ` `            | Sets the Azure region for resource deployment.                             |
| `AZURE_ENV_NAME`                          | string  | `env_name`               | Sets the environment name prefix for all Azure resources.                  |
| `AZURE_CONTENT_UNDERSTANDING_LOCATION`    | string  | `swedencentral`          | Specifies the region for content understanding resources.                  |
| `AZURE_SECONDARY_LOCATION`                | string  | `eastus2`                | Specifies a secondary Azure region.                                        |
| `AZURE_OPENAI_MODEL_DEPLOYMENT_TYPE`     | string  | `GlobalStandard`         | Defines the model deployment type (allowed: `Standard`, `GlobalStandard`). |
| `AZURE_OPENAI_DEPLOYMENT_MODEL`          | string  | `gpt-4o-mini`            | Specifies the GPT model name (e.g., `gpt-4`, `gpt-4o-mini`).               |
| `AZURE_ENV_MODEL_VERSION`                 | string  | `2024-07-18`             | Sets the Azure model version (allowed: `2024-08-06`, etc.).                |
| `AZURE_OPENAI_API_VERSION`            | string  | `2025-01-01-preview`     | Specifies the API version for Azure OpenAI.                                |
| `AZURE_OPENAI_DEPLOYMENT_MODEL_CAPACITY` | integer | `30`                     | Sets the GPT model capacity.                                               |
| `AZURE_OPENAI_EMBEDDING_MODEL`            | string  | `text-embedding-ada-002` | Sets the name of the embedding model to use.                               |
| `AZURE_ENV_IMAGETAG`                      | string  | `latest`        | Sets the image tag (`latest`, `dev`, `hotfix`, etc.).   |
| `AZURE_OPENAI_EMBEDDING_MODEL_CAPACITY`   | integer | `80`                     | Sets the capacity for the embedding model deployment.                      |
| `AZURE_ENV_LOG_ANALYTICS_WORKSPACE_ID`    | string  | Guide to get your [Existing Workspace ID](/documents/re-use-log-analytics.md)            | Reuses an existing Log Analytics Workspace instead of creating a new one.  |
| `USE_LOCAL_BUILD`    | string  | `false`           | Indicates whether to use a local container build for deployment.  |
| `AZURE_EXISTING_AI_PROJECT_RESOURCE_ID`    | string  | `<Existing AI Project resource Id>`            | Reuses an existing AIFoundry and AIFoundryProject instead of creating a new one.  |



## How to Set a Parameter

To customize any of the above values, run the following command **before** `azd up`:

```bash
azd env set <PARAMETER_NAME> <VALUE>
```

**Example:**

```bash
azd env set AZURE_LOCATION westus2
```
