---
name: ado-cicd-bicep-workflows
description: >-
  Generate Azure DevOps CI/CD pipelines for Bicep infrastructure. Ships a static Bicep CI pipeline
  (lint / build / format / parameter validation, no Azure needed) and a deploy pipeline that, on
  push to the default branch, on a daily schedule, and on manual runs, creates a uniquely-named resource group, deploys the whole
  solution with `az deployment` (no azd/azure.yaml dependency), hands off to the post-deploy + test stage, and ALWAYS deletes the
  resource group afterward. Use when the user asks to create, add, set up, or scaffold Azure DevOps
  (ADO) pipelines, YAML pipelines, or deployment pipelines for Bicep infrastructure. It generates
  pipelines that run existing Bicep infrastructure; it does not author Bicep and does not deploy
  application code. Always assumes Bicep. Always asks before changing anything in the repo or Azure
  DevOps.
---

# ADO CI/CD Workflow Generator (Bicep)

Generates the **Azure DevOps** pipelines that run **existing** Bicep infrastructure. It does not
author Bicep files and does not deploy application code.

## Deployment model

- **No stages / no promotion**, **no `params/<env>` folder**, **no per-environment parameters
  files**, **no persistent resource group**.
- Deployment is **`az deployment`** (the Azure CLI) against the discovered Bicep entrypoint, into a
  **fresh, uniquely-named resource group** created per run and **deleted after tests** — nothing is
  kept running between validations. **azd / `azure.yaml` are not required**; the pipeline creates
  the resource group itself (resource-group scope) and resolves `${VAR}` parameter tokens from the
  variable group exactly as azd did.
- Configuration comes from a single **Azure DevOps variable group**.
- There is no long-lived resource group, so **CI cannot run `what-if`**; CI is **static validation
  plus unit tests**. CI runs on **every PR to the default branch** (no path filter) so it also runs
  the repo's hermetic unit tests. The full create → deploy → post-deploy → e2e → cleanup cycle
  (including Playwright/e2e, which needs a live app) runs in the **deploy** pipeline on **push to the
  default branch**, a **daily schedule (00:00 IST)**, and on manual runs.

## Use when

The user wants to create, scaffold, or set up **Azure DevOps** CI/CD or YAML pipelines for Bicep
infrastructure.

## What this skill ships

- **`templates/`**
  - `azure-pipelines-bicep-ci.yml` — PR CI (every PR, no path filter): an `infra_validation` job
    (`az bicep lint`/`build`/`format` + JSON-parameter validation) plus the discovered `unit_*`
    jobs. Credential-free, no Azure.
  - `azure-pipelines-bicep-deploy.yml` — push to default branch / schedule / manual: generate unique env/RG names →
    create RG → `az deployment` → post-deploy + e2e stage → **cleanup that always deletes the RG**.
  - `infra-bicep.yml` — reusable step template that creates the resource group and deploys the
    Bicep entrypoint with `az deployment` (resolving `${VAR}` parameter tokens from the environment).
- **`scripts/`** — `check-prereqs.sh`, `inspect-repo.sh`, `validate-pipelines.sh`.
- **`references/`** — `best-practices.md`, `naming-conventions.md`, `service-connection-setup.md`.

## Hard constraints

- **Ask before any mutation.** Confirm with the user (via an interactive input tool when
  available) before writing repo files, or creating/changing Azure DevOps service connections,
  variable groups, pipelines, or Azure resources. Read-only discovery needs no approval.
- **Always Bicep.** Only generate Bicep pipelines; locate the entrypoint from discovery, never
  hardcode repo/resource/path names.
- **Use the bundled scripts.** Run `scripts/*.sh` in place by absolute path; never copy them into
  the target repo or replace them with inline Python/`node -e`/ad-hoc one-offs. They are portable
  Bash (macOS Bash 3.2 + Windows Git Bash/WSL). Extend a script if a capability is missing.
- **Rely on active sessions.** Use the user's existing `az` / `az devops` sessions; never ask for
  credentials.
- **Temp files under `.agent/tmp/`, always cleaned up.** Write all scratch/intermediate files
  (e.g. `repo-facts.json`) only under `.agent/tmp/` — never in the repo root, `infra/`, or the
  skill folder — and remove them before finishing, even on failure.
- **Variables only, never secrets.** The service connection holds the credential; the variable
  group holds only **non-secret** configuration (subscription id, location, env prefix, and the
  required `${VAR}` names from `main.parameters.json`). Never read/set secret values, and never
  print variable *values* (names only).
- **Don't overwrite existing pipelines** without confirming when `azure_devops.existing_pipelines`
  is non-empty.
- **Cleanup always runs.** The deploy pipeline's Cleanup stage uses `condition: always()` so the
  resource group is deleted even when provisioning or tests fail. Do not add a toggle, RG tags, or
  a hold-for-debugging path.
- **Best practices** (`references/best-practices.md`): least-privilege service connection; deploy
  the Bicep entrypoint with `az deployment` (no azd/`azure.yaml` dependency); create the resource
  group in the pipeline so cleanup is exact and deterministic; pin the schedule comment to
  `00:00 IST`.

## Process

1. **Validate tools.** Run `scripts/check-prereqs.sh` (`jq` required; `az`/`az devops` from
   active sessions, only needed for the setup/validation steps).
2. **Inspect the repo.** Run `scripts/inspect-repo.sh > .agent/tmp/repo-facts.json`. It reports the
   Bicep entrypoint/scope, the parameters file, `azure.yaml` presence (informational only — not
   required), the required and optional variables derived from `main.parameters.json` `${VAR}`
   tokens, the default branch, and any existing ADO pipelines.
3. **Confirm the entrypoint.** Read `infra.bicep_entrypoint`; it is the template the deploy pipeline
   runs. If it is null, stop — there is no Bicep to deploy. `azure.yaml` is **not** required; if
   present it only documents azd hooks a maintainer may optionally port into the pipeline.
4. **Derive the variable group.** From `deployment.required_variables` build the exact list of
   variable names the deploy pipeline needs: always `AZURE_SUBSCRIPTION_ID`, `AZURE_LOCATION`,
   `ENV_PREFIX`, plus every required `${VAR}` from `main.parameters.json`. List
   `optional_variables` as overrides. **Never invent values.**
5. **Confirm the plan** — infra directory, service-connection name, variable-group name and its
   variable names, schedule (`30 18 * * *` = 00:00 IST), and any existing-pipeline conflicts. **Get
   explicit approval before writing files.**
6. **Render templates** into the repo's ADO pipelines folder (default `.azuredevops/pipelines/`;
   honor an existing convention if discovery found one):
   - `azure-pipelines-bicep-ci.yml` / `azure-pipelines-bicep-deploy.yml` — replace
     `__DEFAULT_BRANCH__`, `__INFRA_DIR__`, `__BICEP_ENTRYPOINT__` (from `infra.bicep_entrypoint`),
     `__BICEP_PARAMS__` (from `infra.bicep_parameters`, or empty if none), and `__BICEP_SCOPE__`
     (from `infra.bicep_scope`: `resourceGroup` or `subscription`). Set the `SERVICE_CONNECTION`
     value and the `- group:` name to the user's chosen names. For **subscription scope** the
     `infra-bicep.yml` step deploys with `az deployment sub create` and the template creates its own
     group; for **resource-group scope** the step creates the RG then runs `az deployment group
     create`.
   - **Unit-test jobs in the CI pipeline.** The CI template ships an `infra_validation` job plus
     `unit_frontend` / `unit_backend_pytest` / `unit_backend_dotnet` jobs (running on every PR, no
     path filter — unit tests are hermetic and need no Azure). Get the unit-test facts from the
     ado-cicd-post-deploy skill's `scripts/discover-tests.sh` (run it now — by absolute path — if
     `.agent/tmp/test-facts.json` doesn't already exist; the same file also drives that skill's
     Playwright job). **Keep only the `unit_*` jobs whose category is present** and delete the rest;
     fill `__FE_DIR__`/`__FE_INSTALL__`/`__FE_TEST__` (e.g. `npm ci` / `npm test`),
     `__PYTEST_DIR__`/`__PYTEST_REQS__`, `__DOTNET_DIR__`, and `__PY_VERSION__`. If no unit category
     is present, delete all three and keep just `infra_validation`. (A "unit" suite that actually
     hits live endpoints is integration — leave it to the post-deploy e2e stage instead.) Render a
     `unit_*` job **only** for a category `discover-tests.sh` reports `present: true`; never infer a
     suite from compiled artifacts (`__pycache__`/`*.pyc`), coverage caches, or test paths named in
     a pre-existing CI workflow — those may reference sources absent from the checkout.
   - `infra-bicep.yml` — copy verbatim (reusable deploy step template).
   - The deploy pipeline references `azure-pipelines-post-deploy.yml` (rendered by the
     **ado-cicd-post-deploy** skill) for the post-deploy + e2e stage. Render that skill too, or
     remove the reference for infra-only validation.
7. **Guide Azure DevOps setup** (ask before mutating): the ARM **service connection** (service
   principal or workload-identity federation) and the **variable group** are manual prerequisites —
   give the steps from `references/service-connection-setup.md`. The Azure app registration + role
   assignment for the service connection is a manual prerequisite (the service-principal creation
   may be gated by your tenant; management is handling that). Point to
   `references/naming-conventions.md`.
8. **Validate.** Run `scripts/validate-pipelines.sh` on the rendered pipelines; report its result.
   Full schema validation requires the Azure DevOps "Validate" preview in the project.
9. **Clean up** all files created under `.agent/tmp/` (remove the directory if empty), even if an
   earlier step failed.

## Output

Report, in order:
1. **Detected stack** — Bicep entrypoint/scope, parameters file, `azure.yaml` presence
   (informational), default branch, existing ADO pipelines.
2. **Variable group** — the exact variable names required (and optional overrides).
3. **Generated files** — the pipelines written and their purpose.
4. **Setup required** — Azure sign-in, the ARM service connection, the variable group and its
   values, and the schedule. Say plainly if the service principal / connection must be created by
   an admin.
5. **Validation** — `scripts/validate-pipelines.sh` result.
6. **Cleanup** — confirm `.agent/tmp/` files were removed.
