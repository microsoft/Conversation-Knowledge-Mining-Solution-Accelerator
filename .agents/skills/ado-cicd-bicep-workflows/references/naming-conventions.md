# Naming conventions

## Per-run identifiers (set by the deploy pipeline)
- `ENV_PREFIX` — short, lowercase, alphanumeric prefix from the variable group (e.g. `ado`, `aaudf`).
  Keep it **short (≤ 8 chars)**: it is combined with the build id and then with the accelerator's
  own `uniqueString(...)` suffix inside `main.bicep`, and many Azure resource names have tight
  length limits.
- `AZURE_ENV_NAME` = `$(ENV_PREFIX)$(Build.BuildId)` — unique per run; drives the accelerator's
  `solutionName` and therefore all resource names.
- `AZURE_RESOURCE_GROUP` = `rg-$(AZURE_ENV_NAME)` — the group created and deleted each run.

## Why unique naming matters
`main.bicep` derives a `solutionUniqueText` (e.g. `substring(uniqueString(...),0,5)`) from the
resource group id / subscription, so a fresh RG per run already yields unique resource names. The
per-run `AZURE_ENV_NAME` guarantees the RG itself is unique, which makes cleanup deletion exact and
avoids collisions between overlapping scheduled and manual runs.

## Azure DevOps object names (suggested)
- Service connection: `azure-service-connection` (or `<accelerator>-arm`). Referenced via the
  `SERVICE_CONNECTION` variable so you can rename without editing every task.
- Variable group: `bicep-deploy`.
- Pipelines: `azure-pipelines-bicep-ci.yml`, `azure-pipelines-bicep-deploy.yml` under
  `.azuredevops/pipelines/` (or the repo's existing pipeline folder).

## Files this skill writes
Only pipeline YAML under the ADO pipelines folder. It never edits `infra/*.bicep`,
`main.parameters.json`, `azure.yaml`, or any post-provision script.
