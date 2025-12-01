# Create your first Content Understanding project in the AI Foundry

## Step 1: Create a Content Understanding Project

- Navigate to the [AI Foundry homepage](https://ai.azure.com) and select Try Content Understanding.
> **Note**: You will need to create a project in one of the following regions: westus, swedencentral, or australiaeast

  ![AI Foundry Homepage](../img/ai-services-landing-page.png)   

- Select + Create to create a new Content Understand project.

  ![CU Landing Page](../img/cu-landing-page.png)

- Provide a name for your project (i.e. call_analyzer), select create a new hub, keep the default Azure AI service connection and select Next
  ![create project](../img/create_project.png)
- Keep the default storage account, select next and select Create project. 

- Select Browse file to upload the sample audio file included in this [workshop](../data/convo_2c703f97-6657-4a15-b8b2-db6b96630b2d_2024-12-06%2006_00_00.wav).

  ![CU upload document](../img/cu-upload-document.png)

- Select the Post call analytics template and select create. 
  ![Template Suggestion](../img/define-schema-template-selection.png)

- Save the default schema 
  ![define schema](../img/define-schema.png)

- Select Run analysis and review the fields on the left side  
  ![Template Suggestion](../img/test-analyzer.png)

- Select the Results to view the JSON output.
  ![test-analyzer-results](../img/test-analyzer-results.png)
 
In this challenge we saw how to process one audio file through Azure AI Foundry. In a later challenge, we will see how to process multiple files for a full AI application and chat with data scenario through a pro-code approach.  

> For more detailed information and advanced configurations, refer to the official [Azure AI Content Understanding documentation](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/quickstart/use-ai-foundry).



