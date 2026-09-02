# Best practices — Azure DevOps pipelines for Terraform infrastructure

## State backend
- **Use an ephemeral local backend.** The deploy pipeline writes `backend_override.tf` with
  `backend "local" {}` at runtime, so no azurerm remote-state storage account has to be provisioned
  or bootstrapped. State lives on the agent for the duration of the run and is discarded with it —
  appropriate because the resource group is deleted after tests. The repo's committed backend is
  untouched (overridden only on the agent).
- `*_override.tf` is Terraform's official override mechanism and is already git-ignored by these
  repos, so the runtime file never lands in source control.

## Deployment
- **Generate names per run.** `SOLUTION_NAME = $(ENV_PREFIX)$(Build.BuildId)` and
  `AZURE_RESOURCE_GROUP = rg-$(SOLUTION_NAME)`. Build id is unique per run, so resource names never
  collide and Cleanup can delete exactly the group this run created — no tags needed.
- **Terraform creates the resource group** (`azurerm_resource_group` with `name =
  var.resource_group_name`), so pass `resource_group_name` and `solution_name` as `-var`. Cleanup
  uses `az group delete` on that name, which is robust even if the ephemeral state is gone.
- **Pass required variables as `TF_VAR_<name>`** from the variable group; Terraform reads them
  automatically. Do not rely on the repo's committed `<env>.tfvars` (it pins names you must
  override).

## Cleanup
- **Always delete.** The Cleanup stage runs with `condition: always()` and `dependsOn` both the
  Provision and PostDeployTest stages, so the group is removed even when apply or tests fail. Prefer
  `az group delete` over `terraform destroy` — it does not need valid state and cannot be defeated
  by a partial apply.
- **Guard the delete** with `az group exists` so a failed apply (RG never created) doesn't turn
  cleanup into a hard error.

## Scheduling
- The deploy pipeline uses `schedules: - cron: "30 18 * * *"` = **00:00 IST** (UTC+5:30). Keep the
  `displayName`/comment saying "00:00 IST". Set `always: true` so it runs even without new commits.

## CI
- CI is **static only** (`fmt` / `init -backend=false` / `validate`). With no remote state, a PR
  cannot run a meaningful `plan` — don't try. The deploy pipeline is where real Azure interaction
  happens.

## Authentication
- Run Terraform inside `AzureCLI@2` with `addSpnToEnvironment: true` and set the azurerm provider's
  `ARM_*` env vars from the exposed principal. Support both connection styles: service principal +
  secret (`ARM_CLIENT_SECRET`) and workload identity federation (`ARM_USE_OIDC` + `ARM_OIDC_TOKEN`).
- `storage_use_azuread` / `use_azuread_auth` in the repo's provider config keep data-plane calls on
  Entra ID auth — no storage account keys.

## Security / least privilege
- The **service connection** holds the only credential. Scope its service principal to the target
  subscription with the least role that still allows creating/deleting a resource group and its
  contents — typically **Contributor** plus **User Access Administrator** only if the Terraform
  assigns RBAC roles.
- Keep the **variable group** free of secrets. If a single Terraform variable is genuinely secret,
  mark just that variable as secret in the group; never inline it in YAML. **Never print values.**

## Coexistence with Bicep
- Path filters (the discovered Bicep infra dir vs the discovered Terraform root dir) keep the two CI pipelines
  independent. Generate both; never replace the Bicep pipeline.
