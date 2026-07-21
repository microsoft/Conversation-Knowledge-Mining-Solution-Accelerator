# Troubleshooting Guide

This guide covers common issues encountered during deployment and post-deployment of the Conversation Knowledge Mining Solution Accelerator, along with their solutions.

## Deployment Issues

### Insufficient quota for AI models

**Symptom:** `azd up` fails during provisioning with a quota or capacity error for `gpt-5.2` or `text-embedding-3-small`.

**Solution:**
1. Run the [Quota Check](./quota_check.md) to find a region with available capacity.
2. Create a new environment in a different region:
   ```shell
   azd env new kmretry
   azd env set AZURE_LOCATION eastus2
   azd up
   ```
3. Or request a quota increase in the [Azure Portal](https://portal.azure.com/) under your Azure OpenAI resource → **Quotas**.

### Redeployment conflicts

**Symptom:** Errors about existing resources or a stale `.azure` folder when re-running `azd up`.

**Solution:** Create a fresh environment (see [Creating a New Environment](./DeploymentGuide.md#creating-a-new-environment)):
```shell
azd env new <new-name>
azd up
```

### Region capacity constraints

**Symptom:** Deployment times out or fails with a "capacity" or "not available in region" error.

**Solution:** Try a different [recommended region](./DeploymentGuide.md#12-check-service-availability--quota): East US, East US2, Australia East, UK South, France Central.

### PowerShell script execution blocked

**Symptom:** `... cannot be loaded because running scripts is disabled on this system`.

**Solution:**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Post-Deployment Issues

### Container images not updated / app shows placeholder

**Symptom:** The App Service still shows a placeholder or hello-world page after deployment.

**Solution:** Rebuild and push the images manually:
```powershell
./infra/scripts/build/build-images.ps1
```
Then restart the App Services from the Azure Portal if needed.

### `Dockerfile not found`

**Symptom:** The build script reports it cannot find `ApiApp.Dockerfile` or `WebApp.Dockerfile`.

**Solution:** Run the script from the repository root. The Dockerfiles are located at [src/api/ApiApp.Dockerfile](../src/api/ApiApp.Dockerfile) and [src/app/WebApp.Dockerfile](../src/app/WebApp.Dockerfile).

### `scenarios.json` or config file not found

**Symptom:** A post-provision script reports it cannot find `data/config/scenarios.json`.

**Solution:** Run the script from the repository root so relative paths resolve correctly. The data setup script expects the project structure with `data/config/` at the root.

### `ModuleNotFoundError: No module named 'src'`

**Symptom:** A Python enrichment or setup script fails to import `src` modules.

**Solution:** Run the script from the repository root, or ensure your virtual environment is activated:
```powershell
.venv\Scripts\activate
```

### Agent not responding in Explore

**Symptom:** The chat returns errors or no grounded answers.

**Solution:**
1. Confirm the data setup script completed and created the agent (check `data/config/agent_ids.json`).
2. Re-run the data setup to recreate the agent:
   ```powershell
   ./infra/scripts/post-provision/setup-data.ps1
   ```
3. Verify the Azure OpenAI and Azure AI Search resources are healthy in the Azure Portal.

### Documents stuck in "Processing"

**Symptom:** Uploaded documents never reach "Ready" status.

**Solution:**
1. Check the Storage account **Queue** for stuck messages.
2. Review the backend App Service **Log stream** in the Azure Portal for errors.
3. Confirm the Azure AI Content Understanding resource is provisioned and reachable.

## Authentication Issues

### Users are not prompted to sign in

**Symptom:** The app is publicly accessible after configuring authentication.

**Solution:** Authentication changes can take up to 10 minutes to take effect. Verify the identity provider is added and **Restrict access** is set to **Require authentication** — see [App Authentication Setup](./AppAuthentication.md).

### `Create new app registration` is disabled

**Solution:** Follow [Create a New App Registration](./create_new_app_registration.md) to create one manually, then reference it in the App Service authentication settings.

## Getting More Help

- 🐛 [Submit a new issue](https://github.com/microsoft/Conversation-Knowledge-Mining-Solution-Accelerator/issues)
- 📖 [Deployment Guide](./DeploymentGuide.md)
