## [Optional]: Customizing resource names 

By default this template will use the environment name as the prefix to prevent naming collisions within Azure. The parameters below show the default values. You only need to run the statements below if you need to change the values. 


> To override any of the parameters, run `azd env set <key> <value>` before running `azd up`. On the first azd command, it will prompt you for the environment name. Be sure to choose 3-20 charaters alphanumeric unique name. 

Change the Content Understanding Location (allowed values: Sweden Central, Australia East)

```shell
azd env set AZURE_ENV_CU_LOCATION 'swedencentral'
```

Change the Secondary Location (example: eastus2, westus2, etc.)

```shell
azd env set AZURE_ENV_SECONDARY_LOCATION eastus2
```

Change the Model Deployment Type (allowed values: Standard, GlobalStandard)

```shell
azd env set AZURE_ENV_MODEL_DEPLOYMENT_TYPE GlobalStandard
```

Set the Model Name (allowed values: gpt-4o-mini, gpt-4o, gpt-4)

```shell
azd env set AZURE_ENV_MODEL_NAME gpt-4o-mini
```

Change the Model Capacity (choose a number based on available GPT model capacity in your subscription)

```shell
azd env set AZURE_ENV_MODEL_CAPACITY 30
```

Change the Embedding Model 

```shell
azd env set AZURE_ENV_EMBEDDING_MODEL_NAME text-embedding-ada-002
```

Change the Embedding Deployment Capacity (choose a number based on available embedding model capacity in your subscription)

```shell
azd env set AZURE_ENV_EMBEDDING_MODEL_CAPACITY 80
```