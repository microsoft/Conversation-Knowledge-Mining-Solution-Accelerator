# Conversation knowledge mining solution accelerator

Gain actionable insights from large volumes of conversational data by identifying key themes, patterns, and relationships. Using Azure AI Foundry, Azure AI Content Understanding, Azure OpenAI Service, and Azure AI Search, this solution analyzes unstructured dialogue and maps it to meaningful, structured insights.

Capabilities such as topic modeling, key phrase extraction, speech-to-text transcription, and interactive chat enable users to explore data naturally and make faster, more informed decisions.

Analysts working with large volumes of conversational data can use this solution to extract insights through natural language interaction. It supports tasks like identifying customer support trends, improving contact center quality, and uncovering operational intelligence—enabling teams to spot patterns, act on feedback, and make informed decisions faster.

<br/>

<div align="center">
  
[**SOLUTION OVERVIEW**](#solution-overview)  \| [**QUICK DEPLOY**](#quick-deploy)  \| [**BUSINESS SCENARIO**](#business-scenario)  \| [**SUPPORTING DOCUMENTATION**](#supporting-documentation)

</div>
<br/>

<h2><img src="./documents/Images/ReadMe/solution-overview.png" width="48" />
Solution overview
</h2>

Leverages Azure AI Content Understanding, Azure AI Search, Azure OpenAI Service, Semantic Kernel, Azure SQL Database, and Cosmos DB to process large volumes of conversational data. Audio and text inputs are analyzed through event-driven pipelines to extract and vectorize key information, orchestrate intelligent responses, and power an interactive web front-end for exploring insights using natural language.

### Solution architecture
|![image](./documents/Images/ReadMe/solution-architecture.png)|
|---|

### Additional resources

[Technical Architecture](./documents/TechnicalArchitecture.md)

<br/>

### Key features
<details open>  
<summary>Click to learn more about the key features this solution enables</summary>  

- **Mined entities and relationships** <br/>  
Azure AI Content Understanding and Azure OpenAI Service extract entities and relationships from unstructured data to create a knowledge base.

- **Processed data at scale** <br/>  
Microsoft Fabric processes conversation data at scale, generating vector embeddings for efficient retrieval using the RAG (Retrieval-Augmented Generation) pattern.

- **Visualized insights** <br/>  
An interactive dashboard delivers actionable insights and trends through rich data visualizations.

- **Natural language interaction** <br/>  
Azure OpenAI Service enables contextual question-answering, conversation capabilities, and chart generation, all powered by the RAG pattern.

- **Actionable insights** <br/>  
Summarized conversations, topic generation, and key phrase extraction support faster decision-making and improved productivity.

</details>



<br /><br />
<h2><img src="./documents/Images/ReadMe/quick-deploy.png" width="48" />
Quick deploy
</h2>

### How to install or deploy
Follow the quick deploy steps on the deployment guide to deploy this solution to your own Azure subscription.

[Click here to launch the deployment guide](./documents/DeploymentGuide.md)
<br/><br/>


| [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator) | [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator) | 
|---|---|

<br/>

> ⚠️ **Important: Check Azure OpenAI Quota Availability**
 <br/>To ensure sufficient quota is available in your subscription, please follow [quota check instructions guide](./documents/QuotaCheck.md) before you deploy the solution.

<br/>

### Prerequisites and costs
To deploy this solution accelerator, ensure you have access to an [Azure subscription](https://azure.microsoft.com/free/) with the necessary permissions to create **resource groups, resources, app registrations, and assign roles at the resource group level**. This should include Contributor role at the subscription level and  Role Based Access Control role on the subscription and/or resource group level. Follow the steps in [Azure Account Set Up](./documents/AzureAccountSetUp.md).

Here are some example regions where the services are available: East US, East US2, Australia East, UK South, France Central.

Check the [Azure Products by Region](https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/?products=all&regions=all) page and select a **region** where the following services are available.

Pricing varies by region and usage, so it isn't possible to predict exact costs for your usage. The majority of Azure resources used in this infrastructure are on usage-based pricing tiers. However, some services—such as Azure Container Registry, which has a fixed cost per registry per day, and others like Cosmos DB or SQL Database when provisioned—may incur baseline charges regardless of actual usage.

Use the [Azure pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator) to calculate the cost of this solution in your subscription. 

Review a [sample pricing sheet](https://azure.com/e/67c83432524440d98ccb8c92ebd3e2f7) in the event you want to customize and scale usage.

_Note: This is not meant to outline all costs as selected SKUs, scaled use, customizations, and integrations into your own tenant can affect the total consumption of this sample solution. The sample pricing sheet is meant to give you a starting point to customize the estimate for your specific needs._

<br/>

| Product | Description | Tier / Expected Usage Notes | Cost |
|---|---|---|---|
| [Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry) | Used to orchestrate and build AI workflows that combine Azure AI services. | Free Tier | [Pricing](https://azure.microsoft.com/pricing/details/ai-studio/) |
| [Azure AI Search](https://learn.microsoft.com/en-us/azure/search/search-what-is-azure-search) | Powers vector-based semantic search for retrieving indexed conversation data. | Standard S1; costs scale with document count and replica/partition settings. | [Pricing](https://azure.microsoft.com/pricing/details/search/) |
| [Azure Storage Account](https://learn.microsoft.com/en-us/azure/storage/common/storage-account-overview) | Stores transcripts, intermediate outputs, and application assets. | Standard LRS; usage-based cost by storage/operations. | [Pricing](https://azure.microsoft.com/pricing/details/storage/blobs/) |
| [Azure Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/general/overview) | Secures secrets, credentials, and keys used across the application. | Standard Tier; cost per operation (e.g., secret retrieval). | [Pricing](https://azure.microsoft.com/pricing/details/key-vault/) |
| [Azure AI Services (OpenAI)](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/overview) | Enables language understanding, summarization, entity extraction, and chat capabilities using GPT models. | S0 Tier; pricing depends on token volume and model used (e.g., GPT-4o-mini). | [Pricing](https://azure.microsoft.com/pricing/details/cognitive-services/) |
| [Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/overview) | Hosts microservices and APIs powering the front-end and backend orchestration. | Consumption plan with 0.5 vCPU, 1GiB memory; includes a free usage tier. | [Pricing](https://azure.microsoft.com/pricing/details/container-apps/) |
| [Azure Container Registry](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-intro) | Stores and serves container images used by Azure Container Apps. | Basic Tier; fixed daily cost per registry. | [Pricing](https://azure.microsoft.com/pricing/details/container-registry/) |
| [Azure Monitor / Log Analytics](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/log-analytics-overview) | Collects and analyzes telemetry and logs from services and containers. | Pay-as-you-go; charges based on data ingestion volume. | [Pricing](https://azure.microsoft.com/pricing/details/monitor/) |
| [Azure SQL Database](https://learn.microsoft.com/en-us/azure/azure-sql/database/sql-database-paas-overview) | Stores structured data including insights, metadata, and indexed results. | General Purpose Tier; can be provisioned or serverless. Fixed cost if provisioned. | [Pricing](https://azure.microsoft.com/pricing/details/azure-sql-database/single/) |
| [Azure Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/introduction) | Used for fast, globally distributed NoSQL data storage for chat history and vector metadata. | Autoscale or provisioned throughput; fixed minimum cost if provisioned. | [Pricing](https://azure.microsoft.com/en-us/pricing/details/cosmos-db/autoscale-provisioned/) |
| [Azure Functions](https://learn.microsoft.com/en-us/azure/azure-functions/functions-overview) | Executes lightweight, serverless backend logic and event-driven workflows. | Consumption Tier; billed per execution and duration. | [Pricing](https://azure.microsoft.com/en-us/pricing/details/functions/) |


<br/>

>⚠️ **Important:** To avoid unnecessary costs, remember to take down your app if it's no longer in use,
either by deleting the resource group in the Portal or running `azd down`.

<br /><br />
<h2><img src="./documents/Images/ReadMe/business-scenario.png" width="48" />
Business scenario
</h2>


|![image](./documents/Images/ReadMe/ui.png)|
|---|

<br/>

Analysts often work with large volumes of unstructured conversational data, making it difficult to extract actionable insights quickly and accurately. Traditional tools limit interaction with data, making it hard to surface patterns or ask the right follow-up questions without extensive manual exploration.

This solution addresses those challenges by enabling natural language interaction, dynamic data exploration, and contextual visualization. Analysts can identify key themes, clarify findings, and act with greater confidence—all within a streamlined, insight-driven experience.

⚠️ The sample data used in this repository is synthetic and generated using Azure OpenAI service. The data is intended for use as sample data only.


### Business value
<details>
  <summary>Click to learn more about what value this solution provides</summary>

  - **Better decision-making** 
Summarized, contextualized data helps organizations make informed strategic decisions that drive operational improvements at scale.

- **Time saved**
Automated insight extraction and scalable data exploration reduce manual analysis efforts, leading to improved efficiency and cost savings.

- **Interactive data insights**
Employees can engage directly with conversational data using natural language, enabling quicker understanding and faster resolution of issues.

- **Actionable insights** 
Clear, contextual insights empower employees to take meaningful action based on data-driven evidence.

     
</details>

<br /><br />

<h2><img src="./documents/Images/ReadMe/supporting-documentation.png" width="48" />
Supporting documentation
</h2>

### Security guidelines

This solution uses [Azure Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/general/overview) to securely store secrets, connection strings, and API keys required by application components.

It also leverages [Managed Identity](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/overview) for secure access to Azure resources during local development and production deployment, eliminating the need for hard-coded credentials.

To maintain strong security practices, it is recommended that GitHub repositories built on this solution enable [GitHub secret scanning](https://docs.github.com/code-security/secret-scanning/about-secret-scanning) to detect accidental secret exposure.

Additional security considerations include:

- Enabling [Microsoft Defender for Cloud](https://learn.microsoft.com/en-us/azure/defender-for-cloud) to monitor and secure Azure resources.
- Using [Virtual Networks](https://learn.microsoft.com/en-us/azure/container-apps/networking?tabs=workload-profiles-env%2Cazure-cli) or [firewall rules](https://learn.microsoft.com/en-us/azure/container-apps/waf-app-gateway) to protect Azure Container Apps from unauthorized access.

<br/>

### Cross references
Check out similar solution accelerators

| Solution Accelerator | Description |
|---|---|
| [Document&nbsp;knowledge&nbsp;mining](https://github.com/microsoft/Document-Knowledge-Mining-Solution-Accelerator) | 	Identify relevant documents, summarize unstructured information, and generate document templates. |
| [Content&nbsp;processing](https://github.com/microsoft/document-generation-solution-accelerator) | Extracts data from multi-modal content, maps it to schemas with confidence scoring and user validation, and enables accurate processing of documents like contracts, claims, and invoices. |


<br/>


## Provide feedback

Have questions, find a bug, or want to request a feature? [Submit a new issue](https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/issues) on this repo and we'll connect.

<br/>

## Responsible AI Transparency FAQ 
Please refer to [Transparency FAQ](./TRANSPARENCY_FAQ.md) for responsible AI transparency details of this solution accelerator.

<br/>

## Disclaimers

To the extent that the Software includes components or code used in or derived from Microsoft products or services, including without limitation Microsoft Azure Services (collectively, “Microsoft Products and Services”), you must also comply with the Product Terms applicable to such Microsoft Products and Services. You acknowledge and agree that the license governing the Software does not grant you a license or other right to use Microsoft Products and Services. Nothing in the license or this ReadMe file will serve to supersede, amend, terminate or modify any terms in the Product Terms for any Microsoft Products and Services. 

You must also comply with all domestic and international export laws and regulations that apply to the Software, which include restrictions on destinations, end users, and end use. For further information on export restrictions, visit https://aka.ms/exporting. 

You acknowledge that the Software and Microsoft Products and Services (1) are not designed, intended or made available as a medical device(s), and (2) are not designed or intended to be a substitute for professional medical advice, diagnosis, treatment, or judgment and should not be used to replace or as a substitute for professional medical advice, diagnosis, treatment, or judgment. Customer is solely responsible for displaying and/or obtaining appropriate consents, warnings, disclaimers, and acknowledgements to end users of Customer’s implementation of the Online Services. 

You acknowledge the Software is not subject to SOC 1 and SOC 2 compliance audits. No Microsoft technology, nor any of its component technologies, including the Software, is intended or made available as a substitute for the professional advice, opinion, or judgement of a certified financial services professional. Do not use the Software to replace, substitute, or provide professional financial advice or judgment.  

BY ACCESSING OR USING THE SOFTWARE, YOU ACKNOWLEDGE THAT THE SOFTWARE IS NOT DESIGNED OR INTENDED TO SUPPORT ANY USE IN WHICH A SERVICE INTERRUPTION, DEFECT, ERROR, OR OTHER FAILURE OF THE SOFTWARE COULD RESULT IN THE DEATH OR SERIOUS BODILY INJURY OF ANY PERSON OR IN PHYSICAL OR ENVIRONMENTAL DAMAGE (COLLECTIVELY, “HIGH-RISK USE”), AND THAT YOU WILL ENSURE THAT, IN THE EVENT OF ANY INTERRUPTION, DEFECT, ERROR, OR OTHER FAILURE OF THE SOFTWARE, THE SAFETY OF PEOPLE, PROPERTY, AND THE ENVIRONMENT ARE NOT REDUCED BELOW A LEVEL THAT IS REASONABLY, APPROPRIATE, AND LEGAL, WHETHER IN GENERAL OR IN A SPECIFIC INDUSTRY. BY ACCESSING THE SOFTWARE, YOU FURTHER ACKNOWLEDGE THAT YOUR HIGH-RISK USE OF THE SOFTWARE IS AT YOUR OWN RISK.
