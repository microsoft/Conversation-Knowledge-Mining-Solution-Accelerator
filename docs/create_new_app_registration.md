# Create a New App Registration

If **Create new app registration** is disabled in the App Service Authentication blade, you (or your Microsoft Entra ID administrator) can create an app registration manually and then reference it during authentication setup.

## Prerequisites

- Permission to create app registrations in **Microsoft Entra ID**
- The **Default domain** URL of your deployed frontend App Service

## Steps

1. Go to the [Azure Portal](https://portal.azure.com/) and navigate to **Microsoft Entra ID**.

2. In the left menu, select **App registrations**, then click **+ New registration**.

3. Configure the registration:
   - **Name:** e.g., `conversation-knowledge-mining`
   - **Supported account types:** Accounts in this organizational directory only (single tenant) — unless you need multi-tenant access
   - **Redirect URI:** Select **Web** and enter:
     ```
     https://<your-frontend-app>.azurewebsites.net/.auth/login/aad/callback
     ```

4. Click **Register**.

5. From the app registration **Overview** page, copy the **Application (client) ID** and **Directory (tenant) ID** — you will need these values.

6. Create a client secret:
   - Go to **Certificates & secrets** → **+ New client secret**
   - Add a description and expiration
   - Click **Add** and **copy the secret value immediately** (it is only shown once)

7. Configure API permissions if required:
   - Go to **API permissions** → **+ Add a permission** → **Microsoft Graph** → **Delegated permissions**
   - Add `User.Read` (usually added by default) and click **Grant admin consent**

## Reference the App Registration

Return to [Set Up Authentication in Azure App Service](./AppAuthentication.md) and, when adding the Microsoft identity provider, select **Provide the details of an existing app registration** and enter the **Client ID**, **Client secret**, and **Issuer URL** (`https://login.microsoftonline.com/<tenant-id>/v2.0`).

## Next Steps

Return to the [Deployment Guide](./DeploymentGuide.md#54-configure-authentication-optional) to continue.
