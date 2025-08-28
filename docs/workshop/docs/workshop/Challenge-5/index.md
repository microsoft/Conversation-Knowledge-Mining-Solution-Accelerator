# Video Processing Using Azure AI Content Understanding and Azure OpenAI

Content Understanding is an innovative solution designed to analyze and interpret diverse media types, including documents, images, audio, and video. It transforms this content into structured, organized, and searchable data. In this sample, we will demonstrate how to extract semantic information from you file, and send these information to Azure OpenAI to achive complex works.


- The samples in this repository default to the latest preview API version: **(2024-12-01-preview)**.


## Samples

| File | Description |
| --- | --- |
| [video_chapter_generation.ipynb](../Challenge-5/notebooks/video_chapter_generation.ipynb) | Extract semantic descriptions using content understanding API, and then leverage OpenAI to group into video chapters. |
| [video_tag_generation.ipynb](../Challenge-5/notebooks/video_tag_generation.ipynb) | Generate video tags based on Azure Content Understanding and Azure OpenAI. |

## Getting started

1. Identify your [Azure AI Services resource](docs/create_azure_ai_service.md), suggest to use ***Sweden Central*** region for the availability of the content understanding API.
1. Go to `Access Control (IAM)` in resource, grant yourself role `Cognitive Services User`
1. Identify your [Azure OpenAI resource](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource?pivots=web-portal)
1. Go to `Access Control (IAM)` in resource, grant yourself role `Cognitive Services OpenAI User`
1. Copy `notebooks/.env.sample` to `notebooks/.env`
   ```shell
   cp notebooks/.env.example notebooks/.env
   ```
1. Fill required information into .env from the resources that you alredy have created, remember that your model is ***gpt-4o-mini***, you should have something like this:
   ```shell
   AZURE_AI_SERVICE_ENDPOINT="https://<azure-ai-service>-aiservices-cu.cognitiveservices.azure.com"
   AZURE_AI_SERVICE_API_VERSION=2024-12-01-preview
   AZURE_OPENAI_ENDPOINT="https://<azure-ai-service>-aiservices.openai.azure.com"
   AZURE_OPENAI_API_VERSION=2024-08-01-preview
   AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=gpt-4o-mini
   AUTHENTICATION_URL="https://cognitiveservices.azure.com/.default"
   ```
1. Login Azure
   ```shell
   az login
   ```

## Open a Jupyter notebook and follow the step-by-step guidance

Navigate to the `notebooks` directory and select the sample notebook you are interested in. Since Codespaces is pre-configured with the necessary environment, you can directly execute each step in the notebook.

## More Samples using Azure Content Understanding
[Azure Content Understanding Basic Usecase](https://github.com/Azure-Samples/azure-ai-content-understanding-python)

[Azure Search with Content Understanding](https://github.com/Azure-Samples/azure-ai-search-with-content-understanding-python)