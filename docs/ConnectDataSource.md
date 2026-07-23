[← Back to *DEPLOYMENT* guide](./DeploymentGuide.md#52-run-post-deployment-data-setup)

# Getting Connection Parameters for BYOD (Bring Your Own Data)

When running the post-deployment data setup menu (`setup-data.ps1`), **Option 4** (Azure AI Search) and **Option 5** (Microsoft Fabric) ask you to provide connection parameters for your existing data source. This guide shows you where to find each value in the Azure Portal.

No data is copied — the app queries your source directly at runtime using Microsoft Entra ID (managed identity). No API keys or secrets are needed.

---

## Option 4: Azure AI Search (BYOD)

You need two values: the **Search endpoint** and (optionally) the **Index name**.

### 1. Go to Azure Portal
Go to https://portal.azure.com

### 2. Search for your Azure AI Search service
In the search bar at the top, type the name of your Search service (or "Search services") and select it.

### 3. Copy the Search endpoint
On the **Overview** page of your Search service:
- Locate the **Url** field (e.g. `https://my-search.search.windows.net`)
- Click the copy icon next to it

This is your **Search endpoint** value.

### 4. (Optional) Find the Index name
In the left-hand menu of the Search service blade:
- Click **Indexes** under **Search management**
- Copy the name of the index you want to connect

    Note: If you leave the index name blank during setup, the script will auto-discover indexes on the service and let you pick one (it auto-selects if only one index exists).

---

## Option 5: Microsoft Fabric (BYOD)

You need four values: **Fabric workspace ID**, **SQL endpoint**, **Lakehouse/Warehouse name**, and **Table name**.

**Prerequisite:** This option requires the **Admin** role on the target Fabric workspace for your `az login` identity, so the setup script can grant the API's managed identity Contributor access there.

### 1. Go to Microsoft Fabric
Go to https://app.fabric.microsoft.com and open the workspace containing your Lakehouse or Warehouse.

### 2. Copy the Workspace ID
- Look at the browser address bar while the workspace is open — the URL contains the workspace GUID:
  `https://app.fabric.microsoft.com/groups/<WORKSPACE_ID>/...`
- Copy the `<WORKSPACE_ID>` GUID segment

This is your **Fabric workspace ID**. See [Identify your workspace ID](https://learn.microsoft.com/en-us/fabric/admin/portal-workspace#identify-your-workspace-id) for more details.

### 3. Open your Lakehouse or Warehouse item
From the workspace, click on the Lakehouse or Warehouse you want to connect. See [Navigate the Fabric Lakehouse explorer](https://learn.microsoft.com/en-us/fabric/data-engineering/navigate-lakehouse-explorer) for a tour of the item's UI.

### 4. Copy the SQL analytics endpoint
- Click **Settings** (gear icon) for the item, or view the item's details pane
- Locate **SQL analytics endpoint** (or **SQL connection string** for a Warehouse)
- Copy the value, e.g. `your-workspace.datawarehouse.fabric.microsoft.com`

This is your **SQL endpoint**. See [Find the Warehouse connection string](https://learn.microsoft.com/en-us/fabric/data-warehouse/how-to-connect#find-the-warehouse-connection-string) for step-by-step instructions.

---

## Continue Deployment
Proceed with the next steps in the [Deployment Guide](./DeploymentGuide.md#52-run-post-deployment-data-setup).
