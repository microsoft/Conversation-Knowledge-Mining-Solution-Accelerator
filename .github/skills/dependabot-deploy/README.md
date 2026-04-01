# Dependabot Deploy-Test-Cleanup Skill

A **generic**, accelerator-agnostic Python skill for the Agency CLI that orchestrates
deployment validation for dependency update branches (e.g. dependabot).

**No hardcoded values** — ACR names, image names, Dockerfiles, test paths,
post-deploy scripts, and regions are all auto-detected from the repository
or supplied via CLI args / environment variables.

## Workflow Phases

1. **Git Branch Management** — Creates a branch from source, merges target
2. **Docker Build & Push** — Auto-detects Dockerfiles, builds images, pushes to ACR
3. **Azure Deployment** — Deploys infrastructure via `azd up`, runs post-deploy scripts
4. **E2E Testing** — Runs Playwright/pytest tests with retries, generates HTML reports
5. **Error Recovery** — Auto-fixes package version issues and redeploys
6. **Report Generation** — Compiles results into a markdown report
7. **Cleanup** — Deletes the Azure Resource Group and purges soft-deleted resources

## Prerequisites

- Python 3.11+, Azure CLI (`az`), Azure Developer CLI (`azd`) >= 1.18.0
- Docker Desktop running, Git with push access

## Usage

```bash
# Full workflow — everything is auto-detected from the repo
python orchestrator.py --subscription-id <SUB_ID> --acr-name <ACR_NAME>

# Custom branches & region
python orchestrator.py \
  --subscription-id <SUB_ID> \
  --acr-name myacr \
  --source-branch dependabotchanges \
  --merge-branch dev \
  --location australiaeast

# Test against an existing deployment (skip build + deploy)
python orchestrator.py \
  --subscription-id <SUB_ID> \
  --web-url https://myapp.azurewebsites.net \
  --api-url https://myapi.azurewebsites.net \
  --skip-git --skip-docker

# Individual tools
python -m tools.git_branch --repo-root /path/to/repo
python -m tools.docker_build --acr-name myacr --repo-root /path/to/repo
python -m tools.test_runner --web-url https://... --api-url https://...
python -m tools.cleanup --rg-name rg-my-test
```

## Auto-Detection

The skill auto-detects from the repository:
- **ACR name/hostname** — from `infra/main.parameters.json` or `infra/main.bicep`
- **Docker images** — by scanning for `*Dockerfile` / `*.Dockerfile` files
- **Post-deploy scripts** — from `azure.yaml` postprovision hooks
- **Test directory** — by looking for `tests/e2e-test`, `tests/e2e`, etc.
- **Solution prefix** — from `azure.yaml` `name:` field
- **Use case** — from `infra/main.parameters.json` `usecase` parameter

All auto-detected values can be overridden via CLI arguments or environment variables.
