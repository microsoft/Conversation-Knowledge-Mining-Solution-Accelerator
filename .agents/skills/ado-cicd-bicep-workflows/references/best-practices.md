# Best practices — Azure DevOps pipelines for Bicep infrastructure

## Deployment
- **Deploy with `az deployment`, no azd/`azure.yaml` dependency.** The pipeline deploys the Bicep
  entrypoint directly (`az deployment group create` for resource-group scope, `az deployment sub
  create` for subscription scope). This works on any Bicep repo, including ones that ship no
  `azure.yaml`. `main.parameters.json` `${VAR}` / `${VAR=default}` tokens are resolved from the
  environment (the variable group) with a plain textual substitution — identical to what azd did —
  so no per-parameter `--parameters key=value` plumbing is needed and it stays in sync with the
  accelerator's own parameters file.
- **`azure.yaml` is optional context, not a requirement.** When present it documents azd
  pre/postprovision hooks; a maintainer may port those into the pipeline as extra steps, but the
  deploy does not run azd and does not need the file.
- **Create the resource group in the pipeline** (resource-group scope) with
  `az group create --name $AZURE_RESOURCE_GROUP --location $AZURE_LOCATION` before the deployment,
  so the name is deterministic and cleanup is unambiguous. (Subscription-scoped templates create
  their own group; the deployment runs at subscription scope with `--location`.)
- **Deterministic per-run resource group.** Derive `AZURE_ENV_NAME = $(ENV_PREFIX)$(Build.BuildId)`
  and `AZURE_RESOURCE_GROUP = rg-$(AZURE_ENV_NAME)`. Build id is unique per run, so resource names
  never collide and the Cleanup stage can delete exactly the group this run created — no tags
  needed.

## Cleanup
- **Always delete.** The Cleanup stage runs with `condition: always()` and `dependsOn` both the
  Provision and PostDeployTest stages, so the group is removed even when provisioning or tests
  fail. Never keep resources running between validations.
- **Guard the delete** with `az group exists` so a failed provision (RG never created) doesn't turn
  cleanup into a hard error.

## Scheduling
- The deploy pipeline uses `schedules: - cron: "30 18 * * *"` which is **00:00 IST** (UTC+5:30).
  Keep the `displayName`/comment saying "00:00 IST" so the intent survives. Set `always: true` so
  it runs even without new commits.

## CI
- CI is **static only** (lint / build / format / parameter-structure). There is no persistent
  resource group, so `what-if` cannot run on a PR — don't try. The deploy pipeline is where real
  Azure interaction happens.

## Security / least privilege
- The **service connection** holds the only credential. Scope its service principal to the target
  subscription (or a management group if RG creation must span subscriptions) with the least role
  that still allows creating and deleting a resource group and its contents — typically
  **Contributor** plus **User Access Administrator** only if the Bicep assigns RBAC roles.
- Keep the **variable group** free of secrets. It carries subscription id, location, env prefix and
  the non-secret `${VAR}` configuration. If any accelerator parameter is genuinely secret, mark
  that single variable as secret in the variable group — never inline it in YAML.
- **Never print variable values** in pipeline logs.
