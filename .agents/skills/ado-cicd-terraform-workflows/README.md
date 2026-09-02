# ado-cicd-terraform-workflows

Generates **Azure DevOps** CI/CD pipelines for **Terraform** infrastructure (azurerm provider). It
runs existing Terraform — it does not author `.tf` or deploy app code. Coexists with a Bicep
pipeline via path filters.

The deploy pipeline applies the Terraform against an **ephemeral local backend** (no remote state
to bootstrap), tests it, and deletes the resource group every run — no stages, no per-env tfvars.

## Files

```
ado-cicd-terraform-workflows/
├── SKILL.md
├── README.md
├── scripts/
│   ├── check-prereqs.sh          # jq/git/grep/find required; az/az-devops/terraform recommended
│   ├── inspect-repo-tf.sh        # discover tf root, backend, required TF_VARs, version, pipelines
│   └── validate-pipelines.sh     # offline YAML + placeholder + template-ref checks
├── templates/
│   ├── azure-pipelines-terraform-ci.yml     # PR: fmt / init -backend=false / validate (no Azure)
│   ├── azure-pipelines-terraform-deploy.yml # schedule+manual: apply -> post-deploy+test -> cleanup
│   └── infra-terraform.yml                  # reusable step template: terraform apply (local backend)
└── references/
    ├── best-practices.md
    ├── naming-conventions.md
    └── service-connection-setup.md
```

## Quick start (for the agent)

1. `bash scripts/check-prereqs.sh`
2. `bash scripts/inspect-repo-tf.sh > .agent/tmp/repo-facts-tf.json`
3. Build the variable-group list from `deployment.required_variables` (each as `TF_VAR_<name>`).
4. Ask for the Terraform version (`__TF_VERSION__`).
5. Get approval, render templates into `.azuredevops/pipelines/`, set the service-connection and
   variable-group names, replace `__DEFAULT_BRANCH__` / `__INFRA_TF_DIR__` / `__TF_VERSION__`.
6. `bash scripts/validate-pipelines.sh <rendered files>`
7. Remove `.agent/tmp/`.

## What the pipelines do

- **CI** (`azure-pipelines-terraform-ci.yml`) — runs on PRs. `terraform fmt -check`,
  `init -backend=false`, `validate`. No Azure credentials required.
- **Deploy** (`azure-pipelines-terraform-deploy.yml`) — runs daily at **00:00 IST**
  (`cron 30 18 * * *`) and on manual runs. Generates a unique `solution_name` (`ENV_PREFIX` + build
  id) and `resource_group_name`, `terraform apply`s with an ephemeral local backend, runs the
  post-deploy + test stage, then **always** deletes the RG.

## Prerequisites (manual, one-time)

- An **Azure Resource Manager service connection** (service principal or workload-identity
  federation). See `references/service-connection-setup.md`.
- A **variable group** (default name `terraform-deploy`) with `AZURE_SUBSCRIPTION_ID`,
  `AZURE_LOCATION`, `ENV_PREFIX`, and every required Terraform variable as `TF_VAR_<name>`.

The post-deploy + test stage is provided by the **ado-cicd-post-deploy** skill.
