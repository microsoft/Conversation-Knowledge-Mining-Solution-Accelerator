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
3. The wizard creates the app registration + federated credential (needs permission to create app
   registrations). Assign the SP the roles below.

The reusable apply step detects federation automatically: when no client secret is present it sets
`ARM_USE_OIDC=true` and `ARM_OIDC_TOKEN` from the task's `idToken`.

### B. Service principal + secret (simplest)
1. Create the service connection with **Service principal (manual)** or let the wizard create one.
2. The apply step sets `ARM_CLIENT_SECRET` from the exposed `servicePrincipalKey`.

### Roles the service principal needs
- **Contributor** on the target subscription (create/delete the resource group + all resources).
- **User Access Administrator** *only if* the Terraform assigns RBAC roles (many accelerators do —
  granting the app access to Key Vault / Storage / AI Services). Without it, `azurerm_role_assignment`
  resources fail.

## 2. Variable group

Create a variable group (default name `terraform-deploy`) and link it in the deploy pipeline
(`- group: terraform-deploy`). Add:

| Variable | Example | Notes |
| --- | --- | --- |
| `AZURE_SUBSCRIPTION_ID` | `0ff2547f-...` | target subscription (also used for `ARM_SUBSCRIPTION_ID`) |
| `AZURE_LOCATION` | `eastus2` | region, passed as `-var location=` |
| `ENV_PREFIX` | `aaudf` | short prefix for unique naming (≤ 8 chars) |
| `TF_VAR_<name>` | — | one per required Terraform variable (no default) |

The discovery script (`inspect-repo-tf.sh`) lists the required Terraform variable names under
`deployment.required_variables` (add each as `TF_VAR_<name>`, e.g. `TF_VAR_azure_ai_service_location`)
and optional overrides under `optional_variables`. `resource_group_name` and `solution_name` are
generated per run — do **not** add them to the group. Keep variables **non-secret**; if one is truly
sensitive, mark just that variable as secret.

## 3. Register the pipelines
Pipelines → **New pipeline → Azure Repos/GitHub → Existing Azure Pipelines YAML file**, and point
at `.azuredevops/pipelines/azure-pipelines-terraform-ci.yml` and `...-terraform-deploy.yml`.
