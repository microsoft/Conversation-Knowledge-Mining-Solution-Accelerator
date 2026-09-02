# ado-cicd-bicep-workflows

Generates **Azure DevOps** CI/CD pipelines for **Bicep** infrastructure. It runs existing Bicep —
it does not author Bicep or deploy app code.

The deploy pipeline creates a fresh resource group, deploys the Bicep entrypoint with `az deployment`
(no azd/`azure.yaml` dependency), tests it, and deletes it every run — no stages, no params folder,
no environments.

## Files

```
ado-cicd-bicep-workflows/
├── SKILL.md
├── README.md
├── scripts/
│   ├── check-prereqs.sh        # jq/git/grep/find required; az/az-devops recommended
│   ├── inspect-repo.sh         # discover bicep entrypoint, params file, scope, required ${VAR}s, pipelines
│   └── validate-pipelines.sh   # offline YAML + placeholder + template-ref checks
├── templates/
│   ├── azure-pipelines-bicep-ci.yml     # PR: static lint/build/format/param-validate (no Azure)
│   ├── azure-pipelines-bicep-deploy.yml # schedule+manual: create RG + deploy -> post-deploy+test -> cleanup
│   └── infra-bicep.yml                  # reusable step template: az group create + az deployment
└── references/
    ├── best-practices.md
    ├── naming-conventions.md
    └── service-connection-setup.md
```

## Quick start (for the agent)

1. `bash scripts/check-prereqs.sh`
2. `bash scripts/inspect-repo.sh > .agent/tmp/repo-facts.json`
3. Confirm `infra.bicep_entrypoint` is non-null (there is Bicep to deploy). `azure.yaml` is not
   required.
4. Build the variable-group list from `deployment.required_variables`.
5. Get approval, render templates into `.azuredevops/pipelines/`, set the service-connection and
   variable-group names, replace `__DEFAULT_BRANCH__` / `__INFRA_DIR__` / `__BICEP_ENTRYPOINT__` /
   `__BICEP_PARAMS__` / `__BICEP_SCOPE__`.
6. `bash scripts/validate-pipelines.sh <rendered files>`
7. Remove `.agent/tmp/`.

## What the pipelines do

- **CI** (`azure-pipelines-bicep-ci.yml`) — runs on PRs. `az bicep lint`/`build`/`format` +
  JSON-parameter structure check. No Azure credentials required.
- **Deploy** (`azure-pipelines-bicep-deploy.yml`) — runs on push to the default branch, daily at
  **00:00 IST** (`cron 30 18 * * *`), and on manual runs. Generates a unique `AZURE_ENV_NAME`
  (`ENV_PREFIX` + build id) and RG name, creates the RG, deploys the solution with `az deployment`,
  runs the post-deploy + test stage, then **always** deletes the RG.

## Prerequisites (manual, one-time)

- An **Azure Resource Manager service connection** (service principal or workload-identity
  federation). See `references/service-connection-setup.md`.
- A **variable group** (default name `bicep-deploy`) with `AZURE_SUBSCRIPTION_ID`, `AZURE_LOCATION`,
  `ENV_PREFIX`, and every required `${VAR}` reported by discovery.

The post-deploy + test stage is provided by the **ado-cicd-post-deploy** skill.
