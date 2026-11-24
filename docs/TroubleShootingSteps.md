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
   azd env set AZURE_LOCATION australiaeast
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

**Solution:** Try a different [recommended region](./DeploymentGuide.md#12-check-service-availability--quota): Australia East, Sweden Central, Southeast Asia.

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
./infra/scripts/build/build_and_push_images.ps1
```
Then restart the App Services from the Azure Portal if needed.

### `Dockerfile not found`

**Symptom:** The build script reports it cannot find `ApiApp.Dockerfile` or `WebApp.Dockerfile`.

**Solution:** Run the script from the repository root. The Dockerfiles are located at [src/api/ApiApp.Dockerfile](../src/api/ApiApp.Dockerfile) and [src/app/WebApp.Dockerfile](../src/app/WebApp.Dockerfile).

### `Local Environment: SQL role assignment fails with an ODBC driver error`

**Symptom:** SQL role setup reports `Unable to connect using ODBC Driver 18 or 17`.

**Solution:** For the Local Environment, install [Microsoft ODBC Driver for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server?view=sql-server-ver16) (Driver 18 or 17) on your local machine.

For WAF/private-networking deployments, `azure.yaml` restores private-only SQL access even if role assignment fails. Retry from a host with access to the SQL private endpoint, or temporarily enable network access and restore the previous settings after the retry.

Before retrying, activate the deployment's `.venv` from the repository root. The post-provision hook installs the required Python packages into this environment, but activation does not persist in your terminal.

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
./infra/scripts/post-provision/setup-sql-roles.ps1
```

**Linux/macOS (bash/zsh, with PowerShell 7+ installed):**
```shell
source .venv/bin/activate
pwsh -File ./infra/scripts/post-provision/setup-sql-roles.ps1
```

### SQL health remains unavailable after role assignment

**Symptom:** Data setup repeatedly reports HTTP 503 with `checks.sql=unavailable`,
even though the API accepts the configured admin key.

API authentication and SQL authentication are separate. The API connects to SQL
as its managed identity, which requires a contained user with `db_datareader`,
`db_datawriter`, and `db_ddladmin`. For a managed identity, the contained user's
SQL SID must encode its **client/application ID**, not its Entra object/principal
ID. Existing role memberships do not repair an incorrect SID.

From the repository root, activate `.venv` and run the role setup against the
explicit deployment target:

```powershell
.\.venv\Scripts\Activate.ps1
.\infra\scripts\post-provision\setup-sql-roles.ps1 -ResourceGroupName <resource-group>
```

The script validates the existing SID and reports failed grants as errors. If
it identifies a mismatched contained user, have the SQL administrator repair
the mapping while preserving existing permissions and ownership; the script
does not automatically drop database users. See Microsoft's
[CREATE USER reference](https://learn.microsoft.com/en-us/sql/t-sql/statements/create-user-transact-sql)
for SID-based managed identity users.

Also inspect backend logs for the original SQL login, firewall/private-endpoint,
or table-creation error. Retry data setup only once `checks.sql` is `ok`.

### Telecom setup stalls during audio upload

**Symptom:** SQL is healthy, but data setup stops reporting progress after listing
the audio files in a multipart upload batch.

The setup script uploads audio files individually and limits each upload request
to 180 seconds. Update to the current script before retrying. Scenario setup
clears existing data and external-source registrations; choose **Skip** to
preserve data instead of reloading a scenario.

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
