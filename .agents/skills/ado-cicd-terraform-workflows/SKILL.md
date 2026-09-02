---
name: ado-cicd-terraform-workflows
description: >-
  Generate Azure DevOps CI/CD pipelines for Terraform infrastructure (azurerm provider). Ships a
  static Terraform CI pipeline (fmt / init -backend=false / validate, no Azure needed) and a deploy
  pipeline that, on push to the default branch, on a daily schedule, and on manual runs, generates a unique resource-group /
  solution name, applies the Terraform against an ephemeral local backend, hands off to the
  post-deploy + test stage, and ALWAYS deletes the resource group afterward. Use when the user asks
  to create, add, set up, or scaffold Azure DevOps (ADO) pipelines, YAML pipelines, or deployment
  pipelines for Terraform infrastructure. It generates pipelines that run existing Terraform; it
  does not author `.tf` files and does not deploy application code. Coexists with a Bicep pipeline.
  Always asks before changing anything in the repo or Azure DevOps.
---

# ADO CI/CD Workflow Generator (Terraform)

Generates the **Azure DevOps** pipelines that run **existing** Terraform infrastructure (azurerm
provider). It does not author `.tf` files and does not deploy application code. It **coexists** with
a Bicep pipeline — path filters (`<bicep_dir>/**` vs `<infra_tf_dir>/**`, each from discovery) keep them independent.

## Deployment model

- **No stages / no promotion**, **no per-environment `<env>.tfvars`**, **no persistent resource
  group**, **no remote state backend to bootstrap**.
- The deploy pipeline applies the Terraform with a **runtime local backend**
  (`backend_override.tf`, ephemeral state on the agent), then **deletes the resource group** after
  tests. **Terraform itself creates the resource group.**
- **The pipeline adapts to whatever the root module declares — it never assumes a fixed variable
  contract.** It injects the per-run generated values (`resource_group_name`, `solution_name`,
  `location`) **only for the variables the root actually declares** (detected at apply time by their
  `variable "<name>"` block). A solution that self-manages naming (e.g. a `project_name` var + a
  random suffix, with no `resource_group_name`/`solution_name`) is fully supported: nothing is
  injected and the real group name is **captured from Terraform state** for cleanup. **Never ask the
  user to add variables to their Terraform or to reconcile variable names — this is handled
  automatically; never treat a differing variable contract as a blocking compatibility choice.**
- Configuration comes from a single **Azure DevOps variable group** (required TF variables as
  `TF_VAR_<name>`).
- Because there is no remote state or long-lived group, **CI cannot run `plan` against real
  state**; CI is **static validation plus unit tests** (`fmt` / `validate` + the repo's hermetic
  unit tests). CI runs on **every PR to the default branch** (no path filter). The full create →
  apply → post-deploy → e2e → cleanup cycle (including Playwright/e2e, which needs a live app) runs
  in the **deploy** pipeline on **push to the default branch**, a **daily schedule (00:00 IST)**,
  and on manual runs.

## Use when

The user wants to create, scaffold, or set up **Azure DevOps** CI/CD or YAML pipelines for
Terraform infrastructure.

## What this skill ships

- **`templates/`**
  - `azure-pipelines-terraform-ci.yml` — PR CI (every PR, no path filter): an `infra_validation`
    job (`terraform fmt -check` + `init -backend=false` + `validate`) plus the discovered `unit_*`
    jobs. Credential-free, no Azure.
  - `azure-pipelines-terraform-deploy.yml` — push to default branch / schedule / manual: generate unique names →
    `terraform apply` (ephemeral local backend) → post-deploy + e2e stage → **cleanup that always
    deletes the RG** (the exact group is captured from Terraform state, so solutions that name their
    own group are still torn down).
  - `infra-terraform.yml` — reusable step template that installs Terraform, authenticates the
    azurerm provider from the service connection, writes the local backend override, and applies.
- **`scripts/`** — `check-prereqs.sh`, `inspect-repo-tf.sh`, `validate-pipelines.sh`.
- **`references/`** — `best-practices.md`, `naming-conventions.md`, `service-connection-setup.md`.

## Hard constraints

- **Ask before any mutation.** Confirm with the user (via an interactive input tool when
  available) before writing repo files, or creating/changing Azure DevOps service connections,
  variable groups, pipelines, or Azure resources. Read-only discovery needs no approval.
- **Always Terraform; coexist, never replace.** Only generate Terraform pipelines. Locate the root
  from discovery, never hardcode paths. If a Bicep pipeline exists, leave it untouched.
- **Never author or edit `.tf` sources.** Only pipeline YAML is authored. The runtime
  `backend_override.tf` is written by the *pipeline* on the agent (already git-ignored by these
  repos) — never commit it and never edit the repo's committed `.tf`.
- **Use the bundled scripts.** Run `scripts/*.sh` in place by absolute path; never copy them into
  the target repo or replace them with inline Python/`node -e`/ad-hoc one-offs. They are portable
  Bash (macOS Bash 3.2 + Windows Git Bash/WSL). Extend a script if a capability is missing.
- **Rely on active sessions.** Use the user's existing `az` / `az devops` sessions; never ask for
  credentials.
- **Temp files under `.agent/tmp/`, always cleaned up.** Write all scratch/intermediate files
  (e.g. `repo-facts-tf.json`) only under `.agent/tmp/` — never in the repo root, `infra_tf/`, or the
  skill folder — and remove them before finishing, even on failure.
- **Variables only, never secrets.** The service connection holds the credential; the variable
  group holds only **non-secret** configuration (subscription id, location, env prefix, and the
  required `TF_VAR_<name>` values from discovery). Never read/set secret values, and never print
  variable *values* (names only).
- **Don't overwrite existing pipelines** without confirming when `azure_devops.existing_pipelines`
  is non-empty.
- **Cleanup always runs.** The deploy pipeline's Cleanup stage uses `condition: always()` so the
  resource group is deleted even when apply or tests fail. Do not add a toggle, RG tags, or a
  hold-for-debugging path.
- **Best practices** (`references/best-practices.md`): least-privilege service connection; ephemeral
  local backend (no remote-state prerequisite); OIDC or service-principal auth via ARM_* env vars;
  deterministic per-run naming so cleanup is exact.

## Process

1. **Validate tools.** Run `scripts/check-prereqs.sh` (`jq` required; `az`/`az devops`/`terraform`
   from active sessions/installs, only needed for setup/validation).
2. **Inspect the repo.** Run `scripts/inspect-repo-tf.sh > .agent/tmp/repo-facts-tf.json`. It
   reports the Terraform root/entrypoint, committed backend type, `bicep_present` (coexistence), the
   required and optional variables (from `variable` blocks without a `default`), the required
   Terraform version, the default branch, and any existing ADO pipelines.
3. **Derive the variable group.** From `deployment.required_variables` build the exact list the
   deploy pipeline needs: always `AZURE_SUBSCRIPTION_ID`, `AZURE_LOCATION`, `ENV_PREFIX`, plus every
   required Terraform variable supplied as `TF_VAR_<name>`. The per-run values in
   `deployment.generated_vars` (a subset of `resource_group_name`/`solution_name`, **only those the
   root declares**) are injected at apply time, **not** variable-group entries — the list is empty
   when the solution self-names its group, which is expected and fine. List `optional_variables` as
   overrides. **Never invent values, and never ask the user to add or rename Terraform variables.**
4. **Pin the Terraform version automatically** (`__TF_VERSION__`) — use the repo's
   `required_version` floor when it declares one, otherwise `1.9.8`. Do **not** raise a separate
   question for this; state the chosen version in the single plan (step 5) so the user can override
   it there if they wish.
5. **Confirm the plan once** — Terraform root, service-connection name, variable-group name and its
   variable names, the auto-pinned Terraform version, schedule (`30 18 * * *` = 00:00 IST), and any
   existing-pipeline conflicts. This single confirmation **is** the approval — fold every routine
   decision (version default, test placement, script classification) into it rather than asking a
   series of separate questions. **Get explicit approval before writing files.**
6. **Render templates** into the repo's ADO pipelines folder (default `.azuredevops/pipelines/`;
   honor an existing convention if discovery found one):
   - `azure-pipelines-terraform-ci.yml` / `azure-pipelines-terraform-deploy.yml` — replace
     `__DEFAULT_BRANCH__`, `__INFRA_TF_DIR__`, `__TF_VERSION__`. Set the `SERVICE_CONNECTION` value
     and the `- group:` name to the user's chosen names.
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
   - `infra-terraform.yml` — copy verbatim (reusable apply step template).
   - The deploy pipeline references `azure-pipelines-post-deploy.yml` (rendered by the
     **ado-cicd-post-deploy** skill) for the post-deploy + e2e stage. Render that skill too, or
     remove the reference for infra-only validation.
7. **Guide Azure DevOps setup** (ask before mutating): the ARM **service connection** and the
   **variable group** are manual prerequisites — give the steps from
   `references/service-connection-setup.md`. The service principal + role assignment is a manual
   prerequisite (creation may be gated by your tenant; management is handling that). Point to
   `references/naming-conventions.md`.
8. **Validate.** Run `scripts/validate-pipelines.sh` on the rendered pipelines; report its result.
9. **Clean up** all files created under `.agent/tmp/` (remove the directory if empty), even if an
   earlier step failed.

## Output

Report, in order:
1. **Detected stack** — Terraform root/entrypoint, committed backend type, whether Bicep also
   present (coexistence), default branch, required Terraform version, existing ADO pipelines.
2. **Variable group** — the exact variable names required (as `TF_VAR_<name>`) and optional
   overrides.
3. **Generated files** — the pipelines written and their purpose.
4. **Setup required** — Azure sign-in, the ARM service connection, the variable group and its
   values, the Terraform version, and the schedule. Say plainly if the service principal /
   connection must be created by an admin.
5. **Validation** — `scripts/validate-pipelines.sh` result.
6. **Cleanup** — confirm `.agent/tmp/` files were removed.
