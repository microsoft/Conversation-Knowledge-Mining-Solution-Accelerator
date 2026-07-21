# Conversation Knowledge Mining Solution Accelerator

Welcome to the *Conversation Knowledge Mining* solution accelerator, designed to help organizations derive actionable insights from large volumes of conversational data using generative AI. This accelerator provides a foundation for building AI-driven analysis systems that extract key phrases, model topics, and enable interactive natural language exploration across conversations, documents, and recordings.

When working with high volumes of unstructured conversational data, analysts often face significant challenges, including surfacing meaningful patterns, maintaining consistency in analysis, and asking the right follow-up questions without extensive manual exploration.

The Conversation Knowledge Mining solution accelerator allows users to upload or connect data and have it automatically processed through an AI extraction pipeline, then explore it through an interactive chat experience and auto-generated insights dashboards. This automation not only saves time but also ensures accuracy and consistency in surfacing operational intelligence.

<br/>

<div align="center">
  
[**SOLUTION OVERVIEW**](#solution-overview) \| [**QUICK DEPLOY**](#quick-deploy) \| [**BUSINESS SCENARIO**](#business-scenario) \| [**SUPPORTING DOCUMENTATION**](#supporting-documentation)

</div>
<br/>

**Note:** With any AI solutions you create using these templates, you are responsible for assessing all associated risks and for complying with all applicable laws and safety standards. Learn more in the transparency documents for [Agent Service](https://learn.microsoft.com/en-us/azure/ai-foundry/responsible-ai/agents/transparency-note) and [Agent Framework](https://github.com/microsoft/agent-framework/blob/main/TRANSPARENCY_FAQ.md).
<br/>

<h2><img src="./docs/images/solution-overview.png" width="48" />
Solution overview
</h2>

The solution leverages Microsoft Foundry, Azure Content Understanding, Azure OpenAI Service, Azure AI Search, Azure SQL Database, and Azure App Service to create an intelligent conversation analysis pipeline. It uses a Foundry-hosted agent approach where a specialized ChatAgent reasons across both semantic search and structured analytics to answer questions grounded in your data.

### Solution architecture
|![image](./docs/images/architecture.svg)|
|---|

### How it works

The platform turns any conversational or enterprise dataset into an interactive, insight-driven experience through three integrated surfaces:

- **Home** — Upload files (PDF, DOCX, JSON, CSV, WAV, images) or load a built-in sample scenario pack. Uploads are acknowledged instantly; processing runs in the background.
- **Explore** — Converse with your data. Questions are routed to a Microsoft Foundry ChatAgent with two tools: Azure AI Search (semantic retrieval) and SQL (structured analytics). The agent reasons across both and returns grounded, structured answers.
- **Insights** — The LLM reads your dataset's schema and generates a plan for KPIs and charts. The result is an adaptive dashboard where layouts, filters, and metrics are all data-driven, not hard-coded.

<br/>

### Additional resources

[Azure Content Understanding Documentation](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/)

[Azure AI Foundry Documentation](https://learn.microsoft.com/en-us/azure/ai-foundry/)

[Azure AI Search Documentation](https://learn.microsoft.com/en-us/azure/search/)

<br/>

### Key features
<details open>
  <summary>Click to learn more about the key features this solution enables</summary>

  - **Mined entities and relationships** <br/>
  Azure Content Understanding and Azure OpenAI extract entities, topics, and relationships from unstructured conversations to build a richer knowledge base.

  - **Processed data at scale** <br/>
  The pipeline processes high-volume conversation data, generates embeddings, and indexes results for fast hybrid retrieval using RAG patterns.

  - **Visualized insights** <br/>
  An interactive dashboard surfaces trends, distributions, and outliers so teams can quickly move from raw conversation logs to actionable understanding.

  - **Natural language interaction** <br/>
  Users can ask contextual questions, follow up on findings, and get grounded responses with citations through an intuitive chat experience.

  - **LLM-planned insights dashboard** <br/>
  The system analyzes your data schema, then plans and computes relevant KPIs and charts automatically for each dataset.

  - **Bring Your Own Index / Data** <br/>
  Connect an existing Azure AI Search index or external database (Microsoft Fabric, SQL) without uploading data again.

</details>

<br /><br />
<h2><img src="./docs/images/quick-deploy.png" width="48" />
Quick deploy
</h2>

### How to install or deploy
Follow the quick deploy steps on the deployment guide to deploy this solution to your own Azure subscription.

> **Note:** This solution accelerator requires **Azure Developer CLI (azd) version 1.18.0 or higher**. Please ensure you have the latest version installed before proceeding with deployment. [Download azd here](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd).

> **Note:** Container images are built **remotely in Azure Container Registry** using `az acr build`. For local deployment (Option D in the deployment guide), install the [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli).

[Click here to launch the deployment guide](./docs/DeploymentGuide.md)
<br/><br/>

| [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator) | [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator) | [![Open in Visual Studio Code Web](https://img.shields.io/static/v1?style=for-the-badge&label=Visual%20Studio%20Code%20(Web)&message=Open&color=blue&logo=visualstudiocode&logoColor=white)](https://vscode.dev/azure/?vscode-azure-exp=foundry&agentPayload=eyJiYXNlVXJsIjogImh0dHBzOi8vcmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbS9taWNyb3NvZnQvQ29udmVyc2F0aW9uLUtub3dsZWRnZS1NaW5pbmctU29sdXRpb24tQWNjZWxlcmF0b3IvcmVmcy9oZWFkcy9tYWluL2luZnJhL3ZzY29kZV93ZWIiLCAiaW5kZXhVcmwiOiAiL2luZGV4Lmpzb24iLCAidmFyaWFibGVzIjogeyJhZ2VudElkIjogIiIsICJjb25uZWN0aW9uU3RyaW5nIjogIiIsICJ0aHJlYWRJZCI6ICIiLCAidXNlck1lc3NhZ2UiOiAiIiwgInBsYXlncm91bmROYW1lIjogIiIsICJsb2NhdGlvbiI6ICIiLCAic3Vic2NyaXB0aW9uSWQiOiAiIiwgInJlc291cmNlSWQiOiAiIiwgInByb2plY3RSZXNvdXJjZUlkIjogIiIsICJlbmRwb2ludCI6ICIifSwgImNvZGVSb3V0ZSI6IFsiYWktcHJvamVjdHMtc2RrIiwgInB5dGhvbiIsICJkZWZhdWx0LWF6dXJlLWF1dGgiLCAiZW5kcG9pbnQiXX0=) | 
|---|---|---|
 
<br/>

> **Note**: Some tenants may have additional security restrictions that run periodically and could impact the application (e.g., blocking public network access). If you experience issues or the application stops working, check if these restrictions are the cause.

> ⚠️ **Important: Check Azure OpenAI Quota Availability**
 <br/>To ensure sufficient quota is available in your subscription, please follow the [quota check instructions guide](./docs/quota_check.md) before you deploy the solution.

<br/>

### Prerequisites and Costs

To deploy this solution accelerator, ensure you have access to an [Azure subscription](https://azure.microsoft.com/free/) with the necessary permissions to create **resource groups and resources**. Follow the steps in [Azure Account Set Up](./docs/AzureAccountSetUp.md).

Check the [Azure Products by Region](https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/table) page and select a **region** where the following services are available: Azure OpenAI Service, Azure AI Content Understanding, Azure AI Search, and Search Semantic Ranker.

Here are some example regions where the services are available: Australia East, Sweden Central, Southeast Asia.

Pricing varies per region and usage, so it isn't possible to predict exact costs for your usage. The majority of the Azure resources used in this infrastructure are on usage-based pricing tiers. However, Azure Container Registry has a fixed cost per registry per day.

Use the [Azure pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator) to calculate the cost of this solution in your subscription.

| Product | Description | Cost |
|---|---|---|
| [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-services/openai/) | Powers chat (gpt-5.2), embeddings (text-embedding-3-small), and summarization | [Pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/) |
| [Azure AI Content Understanding](https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/) | Extracts text, summaries, topics, and key phrases from content | [Pricing](https://azure.microsoft.com/en-us/pricing/details/content-understanding/) |
| [Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/) | Agent orchestration, governance, tracing, and quotas | [Pricing](https://azure.microsoft.com/en-us/pricing/details/ai-studio/) |
| [Azure AI Search](https://learn.microsoft.com/en-us/azure/search/) | Powers hybrid (BM25 + vector) data search | [Pricing](https://azure.microsoft.com/en-us/pricing/details/search/) |
| [Azure App Service](https://learn.microsoft.com/azure/app-service/) | Hosts the backend API and frontend web application | [Pricing](https://azure.microsoft.com/pricing/details/app-service/linux/) |
| [Azure SQL Database](https://learn.microsoft.com/azure/azure-sql/database/) | Stores metadata, chat history, and enrichment cache | [Pricing](https://azure.microsoft.com/pricing/details/azure-sql-database/single/) |
| [Azure Storage Account](https://learn.microsoft.com/azure/storage/) | Blob storage for documents, Queue storage for async processing | [Pricing](https://azure.microsoft.com/pricing/details/storage/blobs/) |
| [Azure Container Registry](https://learn.microsoft.com/azure/container-registry/) | Stores container images for deployment | [Pricing](https://azure.microsoft.com/pricing/details/container-registry/) |

<br/>

>⚠️ **Important:** To avoid unnecessary costs, remember to take down your app if it's no longer in use,
either by deleting the resource group in the Portal or running `azd down`.

<br /><br />
<h2><img src="./docs/images/business-scenario.png" width="48" />
Business Scenario
</h2>

|![image](./docs/images/homepage-ui.png)|
|---|

<br/>

Analysts often work with large volumes of unstructured conversational data, making it difficult to extract actionable insights quickly and accurately. Traditional tools limit interaction with data, making it hard to surface patterns or ask the right follow-up questions without extensive manual exploration. Some of the challenges they face include:

- Difficulty surfacing meaningful patterns across high volumes of conversations
- Time-consuming manual review of transcripts, documents, and recordings
- High risk of inconsistency and missed signals from manual analysis
- Limited ability to ask contextual, natural language questions of the data

By using the *Conversation Knowledge Mining* solution accelerator, users can automate extraction, explore data conversationally, and surface adaptive dashboards that reduce manual analysis effort.

### Business value
<details>
  <summary>Click to learn more about what value this solution provides</summary>

  - **Better decision-making** <br/>
  Summarized, contextualized data helps organizations make informed strategic decisions that drive operational improvements at scale.

  - **Time saved** <br/>
  Automated insight extraction and scalable data exploration reduce manual analysis efforts.

  - **Interactive data insights** <br/>
  Employees can engage directly with conversational data using natural language.

  - **Actionable insights** <br/>
  Clear, contextual insights empower employees to take meaningful action based on data-driven evidence.

  - **Scalability** <br/>
  Enables organizations to handle increasing volumes of conversational data without proportional resource increases.

</details>

### Use Case
<details>
  <summary>Click to learn more about what use cases this solution provides</summary>

The solution ships with three built-in sample scenario packs and two bring-your-own-data connectors, all selectable from the post-deployment data setup menu:

| Use Case | Persona | Challenges | Summary/Approach |
|----------|---------|------------|------------------|
| Contact Center (IT Helpdesk) | Helpdesk Analyst | High volumes of IT helpdesk call transcripts make it hard to mine sentiment, cluster recurring topics, and measure agent performance. | Sentiment analysis, topic clustering, and agent performance insights over JSON call transcripts. Ships with a pre-built search index for instant exploration. |
| Mortgage Application | Loan Analyst | Reviewing lengthy housing reports and purchase contracts (PDF) manually is slow and error-prone. | Document summarization, clause extraction, and risk analysis across housing reports and purchase contracts. |
| Telecom Analysis | Operations Analyst | Call transcripts and audio recordings are difficult to transcribe, cluster, and act on at scale. | Transcription, sentiment breakdowns, and topic clustering across JSON transcripts and WAV recordings. |
| Bring Your Own Data (Azure AI Search) | Data Analyst | Existing data already lives in an Azure AI Search index and should not be re-uploaded. | Connect an existing Azure AI Search index for conversational AI access — no re-ingestion required. |
| Bring Your Own Data (Microsoft Fabric) | Data Analyst | Data resides in a Microsoft Fabric Lakehouse or Warehouse and needs conversational access. | Connect a Fabric Lakehouse or Warehouse for conversational AI access over your existing data. |

</details>

<br /><br />

<h2><img src="./docs/images/supporting-documentation.png" width="48" />
Supporting documentation
</h2>

### Security guidelines

This template uses [Managed Identity](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/overview) for secure access between Azure resources, eliminating the need for hard-coded credentials. All Azure service communication uses RBAC.

To ensure continued best practices in your own repository, we recommend that anyone creating solutions based on our templates ensure that the [GitHub secret scanning](https://docs.github.com/code-security/secret-scanning/about-secret-scanning) setting is enabled.

You may want to consider additional security measures, such as:

* Enabling Microsoft Defender for Cloud to [secure your Azure resources](https://learn.microsoft.com/en-us/azure/defender-for-cloud/).
* Protecting the Azure App Service instance with a [Virtual Network](https://learn.microsoft.com/azure/app-service/overview-vnet-integration).
* Configuring [App Service authentication](./docs/AppAuthentication.md) to require users to sign in.

<br/>

### Additional documentation

- [Deployment Guide](./docs/DeploymentGuide.md)
- [Quota Check](./docs/quota_check.md)
- [Azure Account Set Up](./docs/AzureAccountSetUp.md)
- [App Authentication Setup](./docs/AppAuthentication.md)
- [Customizing azd Parameters](./docs/CustomizingAzdParameters.md)
- [Sample Questions](./docs/SampleQuestions.md)
- [Troubleshooting Guide](./docs/TroubleShootingSteps.md)

<br/>

### Cross references
Check out similar solution accelerators

| Solution Accelerator | Description |
|---|---|
| [Document Knowledge Mining](https://github.com/microsoft/Document-Knowledge-Mining-Solution-Accelerator) | Extract structured information from unstructured documents using AI |
| [Content Processing](https://github.com/microsoft/content-processing-solution-accelerator) | Extract data from multi-modal content and map it to schemas with confidence scoring |
| [Multi-Agent Custom Automation Engine](https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator) | Coordinate multiple specialized AI agents to accomplish business processes |

<br/>

💡 Want to get familiar with Microsoft's AI and Data Engineering best practices? Check out our playbooks to learn more

| Playbook | Description |
|:---|:---|
| [AI&nbsp;playbook](https://learn.microsoft.com/en-us/ai/playbook/) | The Artificial Intelligence (AI) Playbook provides enterprise software engineers with solutions, capabilities, and code developed to solve real-world AI problems. |
| [Data&nbsp;playbook](https://learn.microsoft.com/en-us/data-engineering/playbook/understanding-data-playbook) | The data playbook provides enterprise software engineers with solutions which contain code developed to solve real-world problems. |

<br/> 

## Provide feedback

Have questions, find a bug, or want to request a feature? [Submit a new issue](https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/issues) on this repo and we'll connect.

<br/>

## Responsible AI Transparency FAQ 
Please refer to the transparency documents for [Agent Service](https://learn.microsoft.com/en-us/azure/ai-foundry/responsible-ai/agents/transparency-note) and [Agent Framework](https://github.com/microsoft/agent-framework/blob/main/TRANSPARENCY_FAQ.md) for responsible AI transparency details of this solution accelerator.

<br/>

## Disclaimers
This release is an artificial intelligence (AI) system that generates text based on user input. The text generated by this system may include ungrounded content, meaning that it is not verified by any reliable source or based on any factual data. The data included in this release is synthetic, meaning that it is artificially created by the system and may contain factual errors or inconsistencies. Users of this release are responsible for determining the accuracy, validity, and suitability of any content generated by the system for their intended purposes. Users should not rely on the system output as a source of truth or as a substitute for human judgment or expertise.

This release only supports English language input and output. Users should not attempt to use the system with any other language or format. The system output may not be compatible with any translation tools or services, and may lose its meaning or coherence if translated.

This release does not reflect the opinions, views, or values of Microsoft Corporation or any of its affiliates, subsidiaries, or partners. The system output is solely based on the system's own logic and algorithms, and does not represent any endorsement, recommendation, or advice from Microsoft or any other entity. Microsoft disclaims any liability or responsibility for any damages, losses, or harms arising from the use of this release or its output by any user or third party.

This release does not provide any financial advice, legal advice and is not designed to replace the role of qualified client advisors in appropriately advising clients. Users should not use the system output for any financial decisions, legal guidance or transactions, and should consult with a professional financial advisor and or legal advisor as appropriate before taking any action based on the system output. Microsoft is not a financial institution or a fiduciary, and does not offer any financial products or services through this release or its output.

This release is intended as a proof of concept only, and is not a finished or polished product. It is not intended for commercial use or distribution, and is subject to change or discontinuation without notice. Any planned deployment of this release or its output should include comprehensive testing and evaluation to ensure it is fit for purpose and meets the user's requirements and expectations. Microsoft does not guarantee the quality, performance, reliability, or availability of this release or its output, and does not provide any warranty or support for it.

This Software requires the use of third-party components which are governed by separate proprietary or open-source licenses as identified below, and you must comply with the terms of each applicable license in order to use the Software. You acknowledge and agree that this license does not grant you a license or other right to use any such third-party proprietary or open-source components.

To the extent that the Software includes components or code used in or derived from Microsoft products or services, including without limitation Microsoft Azure Services (collectively, "Microsoft Products and Services"), you must also comply with the Product Terms applicable to such Microsoft Products and Services. You acknowledge and agree that the license governing the Software does not grant you a license or other right to use Microsoft Products and Services. Nothing in the license or this ReadMe file will serve to supersede, amend, terminate or modify any terms in the Product Terms for any Microsoft Products and Services.

You must also comply with all domestic and international export laws and regulations that apply to the Software, which include restrictions on destinations, end users, and end use. For further information on export restrictions, visit https://aka.ms/exporting.

You acknowledge that the Software and Microsoft Products and Services (1) are not designed, intended or made available as a medical device(s), and (2) are not designed or intended to be a substitute for professional medical advice, diagnosis, treatment, or judgment and should not be used to replace or as a substitute for professional medical advice, diagnosis, treatment, or judgment. Customer is solely responsible for displaying and/or obtaining appropriate consents, warnings, disclaimers, and acknowledgements to end users of Customer's implementation of the Online Services.

You acknowledge the Software is not subject to SOC 1 and SOC 2 compliance audits. No Microsoft technology, nor any of its component technologies, including the Software, is intended or made available as a substitute for the professional advice, opinion, or judgment of a certified financial services professional. Do not use the Software to replace, substitute, or provide professional financial advice or judgment.

BY ACCESSING OR USING THE SOFTWARE, YOU ACKNOWLEDGE THAT THE SOFTWARE IS NOT DESIGNED OR INTENDED TO SUPPORT ANY USE IN WHICH A SERVICE INTERRUPTION, DEFECT, ERROR, OR OTHER FAILURE OF THE SOFTWARE COULD RESULT IN THE DEATH OR SERIOUS BODILY INJURY OF ANY PERSON OR IN PHYSICAL OR ENVIRONMENTAL DAMAGE (COLLECTIVELY, "HIGH-RISK USE"), AND THAT YOU WILL ENSURE THAT, IN THE EVENT OF ANY INTERRUPTION, DEFECT, ERROR, OR OTHER FAILURE OF THE SOFTWARE, THE SAFETY OF PEOPLE, PROPERTY, AND THE ENVIRONMENT ARE NOT REDUCED BELOW A LEVEL THAT IS REASONABLY, APPROPRIATE, AND LEGAL, WHETHER IN GENERAL OR IN A SPECIFIC INDUSTRY. BY ACCESSING THE SOFTWARE, YOU FURTHER ACKNOWLEDGE THAT YOUR HIGH-RISK USE OF THE SOFTWARE IS AT YOUR OWN RISK.
