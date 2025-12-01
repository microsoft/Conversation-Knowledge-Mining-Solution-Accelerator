## How to Check & Update Quota

1. Go to the [Azure Portal](https://portal.azure.com).
2. In the **search bar**, type the name of the **Resource Group** you created during **Challenge 1**.
3. Within the resource group, look for the **Azure AI services** ending in -aiservices.
4. In the AI services, Click on **Go to Azure AI Foundry portal**.  
4. **Navigate** to `Shared resources` in the bottom-left menu.

---

### 🔍 To Check Quota

- Click on the `Quota` tab.
- In the `GlobalStandard` dropdown:
  - Select the desired model (e.g., **GPT-4**, **GPT-4o**, **GPT-4o Mini**, or **text-embedding-ada-002**).
  - Choose the **region** where your deployment is hosted.
- You can:
  **Request more quota**, or **Delete unused deployments** to free up capacity.

---

### ✏️ To Update Quota

- Go to the `Deployments` tab.
- Select the deployment of the desired model.
- Click **Edit**, update the **Tokens per Minute (TPM) Rate Limit**, then **Submit Changes**.
