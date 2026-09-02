# Naming conventions

## Per-run identifiers (set by the deploy pipeline)
- `ENV_PREFIX` — short, lowercase, alphanumeric prefix from the variable group (e.g. `ado`, `aaudf`).
  Keep it **short (≤ 8 chars)**: it is combined with the build id and then with the Terraform
  `solution_unique_text` / random suffix, and many Azure resource names have tight length limits.
- `SOLUTION_NAME` = `$(ENV_PREFIX)$(Build.BuildId)` — unique per run; passed as
  `-var solution_name=` and drives all resource names.
- `AZURE_RESOURCE_GROUP` = `rg-$(SOLUTION_NAME)` — passed as `-var resource_group_name=`; the group
  Terraform creates and the pipeline deletes each run.

## Why unique naming matters
The Terraform root derives a `solution_suffix` from `solution_name` + a random string, so a fresh
run already yields unique resource names. The per-run `SOLUTION_NAME` guarantees the resource group
name is unique too, which makes cleanup deletion exact and avoids collisions between overlapping
scheduled and manual runs.

## Azure DevOps object names (suggested)
- Service connection: `azure-service-connection` (or `<accelerator>-arm`). Referenced via the
  `SERVICE_CONNECTION` variable so you can rename without editing every task.
- Variable group: `terraform-deploy`.
- Pipelines: `azure-pipelines-terraform-ci.yml`, `azure-pipelines-terraform-deploy.yml` under
  `.azuredevops/pipelines/` (or the repo's existing pipeline folder).

## Files this skill writes
Only pipeline YAML under the ADO pipelines folder. It never edits `infra_tf/*.tf`, provider config,
or any post-provision script. The runtime `backend_override.tf` is written by the pipeline on the
agent, not committed.
