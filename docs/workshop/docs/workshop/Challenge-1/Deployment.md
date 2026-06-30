
We will set up the initial environment for you to build on top of during your Microhack. This comprehensive setup includes configuring essential Azure services and ensuring access to all necessary resources. Participants will familiarize themselves with the architecture, gaining insights into how various components interact to create a cohesive solution. With the foundational environment in place, the focus will shift seamlessly to the first Microhack Challenge endeavor. 

### **Prerequisites**

- To deploy this solution accelerator, ensure you have access to an [Azure subscription](https://azure.microsoft.com/free/) with the necessary permissions to create **resource groups and resources**. Follow the steps in  [Azure Account Set Up](../../../../../documents/AzureAccountSetUp.md)
- [VS Code](https://code.visualstudio.com/download) installed locally


Check the [Azure Products by Region](https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/?products=all&regions=all) page and select a **region** where the following services are available:  

- Azure AI Foundry 
- Azure OpenAI Service 
- Azure AI Search
- Azure AI Content Understanding
- Embedding Deployment Capacity  
- GPT Model Capacity
- [Azure Semantic Search](../../../../../documents/AzureSemanticSearchRegion.md)  

Here are some example regions where the services are available: East US2

### ⚠️ Important: Check Azure OpenAI Quota Availability  

➡️ To ensure sufficient quota is available in your subscription, please follow **[Quota check instructions guide](../../../../../documents/QuotaCheck.md)** before you deploy the solution.


### Quota Recommendations  
By default, the **GPT model capacity** in deployment is set to **30k tokens**.  
> **We recommend increasing the capacity to 120k tokens for optimal performance.** 

To adjust quota settings, follow these [steps](../../../../../documents/AzureGPTQuotaSettings.md)  



### Deploying

#### 1. Clone the Repository

    bash

    git clone <REPO-URL>
    cd <REPO-FOLDER> 

---

#### 2. Create and Activate a Virtual Environment
        python -m venv .venv
        # Windows
        .venv\Scripts\activate
        
        # macOS/Linux
        source .venv/bin/activate

---

#### 3. Authenticate with Azure
     azd auth login

---

#### 4.  Deploy the solution
    azd up


- You will be prompted to: 

    - Provide an `azd` environment name (like "ckmapp")
    - Select a subscription from your Azure account, and select a location which has quota for all the resources. 
    - This deployment will take *7-10 minutes* to provision the resources in your account and set up the solution with sample data. 
    - If you get an error or timeout with deployment, changing the location can help, as there may be availability constraints for the resources.
---

### 5. Verify Deployment
Once deployment completes:

1. Once the deployment has completed successfully, open the [Azure Portal](https://portal.azure.com/). 
2. Go to the deployed resource group, find the App Service and get the app URL from `Default domain`.

---

<h2>
Additional Steps
</h2>

1. **Optional**: Add App Authentication
   
    Follow steps in [App Authentication](../../../../../documents/AppAuthentication.md) to configure authenitcation in app service.

    Note: Authentication changes can take up to 10 minutes 
