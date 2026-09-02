# Service connection & variable group setup (Azure DevOps)

The deploy pipeline needs one **Azure Resource Manager service connection** (the only credential)
and one **variable group** (non-secret configuration). Both are manual, one-time prerequisites.

> Creating the underlying app registration / service principal may be gated by your tenant. If you
> cannot create it, ask an admin — this is a known blocker being handled by management. The pipeline
> itself does not create credentials.

## 1. Service connection (pick ONE auth style)

### A. Workload identity federation (recommended, no secret)
1. Project → **Project settings → Service connections → New → Azure Resource Manager**.
2. Choose **Workload identity federation (automatic)**, select the subscription, name it
   (e.g. `azure-service-connection`), and grant access to the pipelines that need it.
3. The wizard creates the app registration + federated credential automatically (needs permission
   to create app registrations). Assign the SP the roles below.

The reusable deploy step uses the Azure CLI already authenticated by the `AzureCLI@2` task via the
service connection — no `azd auth login` and no extra sign-in step is needed. Workload identity
federation works out of the box: the task authenticates the CLI with the federated credential, and
`az deployment` / `az group create` run under that identity.

### B. Service principal + secret (simplest)
1. Create the service connection with **Service principal (manual)** or let the wizard create one.
2. The `AzureCLI@2` task authenticates the Azure CLI with this service principal automatically; the
   `infra-bicep.yml` step then runs `az group create` + `az deployment` under that identity. No
   explicit login command is required in the template.

### Roles the service principal needs
- **Contributor** on the target subscription (create/delete the resource group + all resources).
- **User Access Administrator** *only if* the Bicep assigns RBAC roles (many accelerators do — e.g.
  granting the app access to Key Vault / Storage / AI Services). Without it, role-assignment
  resources in the template fail.

## 2. Variable group

Create a variable group (default name `bicep-deploy`) and link it in the deploy pipeline
(`- group: bicep-deploy`). Add:

| Variable | Example | Notes |
| --- | --- | --- |
| `AZURE_SUBSCRIPTION_ID` | `0ff2547f-...` | target subscription |
| `AZURE_LOCATION` | `eastus2` | region for the resource group |
| `ENV_PREFIX` | `aaudf` | short prefix for unique naming (≤ 8 chars) |
| _required `${VAR}`s_ | — | every token from `main.parameters.json` **without** a `=default` |

The discovery script (`inspect-repo.sh`) lists the exact required variable names under
`deployment.required_variables` and optional overrides under `optional_variables`. Provide a
value for each required one. Keep them **non-secret**; if a single parameter is truly sensitive,
mark just that variable as secret in the group.

## 3. Register the pipelines
Pipelines → **New pipeline → Azure Repos/GitHub → Existing Azure Pipelines YAML file**, and point
at `.azuredevops/pipelines/azure-pipelines-bicep-ci.yml` and `...-bicep-deploy.yml`.
