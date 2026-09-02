---
name: ado-cicd-post-deploy
description: >-
  Generate the Azure DevOps stage that runs a solution's post-deployment steps and tests after the
  infrastructure is provisioned, then hands off to cleanup. It reads the solution's configuration
  back from the provisioned resource group via `az` (the deployment outputs), hydrates an azd
  environment, runs the discovered post-provision/post-deploy scripts, and runs the Playwright/e2e
  tests that are present (unit tests run separately, on every PR, in the flavor CI pipeline). Use
  when the user wants the Azure DevOps deploy pipeline to
  also configure and test the solution after `azd provision` / `terraform apply`. It contains no
  solution-specific knowledge — every step is discovered at generation time from the repo's azd
  hooks, deployment guide, and test tooling. Always asks before changing anything in the repo.
---

# ADO CI/CD Post-Deployment + Tests

Generates the **Azure DevOps stage** that runs a solution's **post-deployment steps and tests**
after the infrastructure is provisioned. The `ado-cicd-bicep-workflows` and
`ado-cicd-terraform-workflows` deploy pipelines provision the infrastructure and reference this
stage between their Provision and Cleanup stages; this stage configures and tests the solution on
top of the provisioned resources, then the deploy pipeline's Cleanup stage tears it down.

The skill contains **no solution-specific knowledge**. Which scripts run, in what order, which
toolchains they need, which steps are manual, and which tests exist are all **discovered at
generation time** from the repo's own azd contract (`azure.yaml` hooks), its deployment guide, and
its test tooling, then substituted into a generic stage template.

## Reading configuration back from the resource group

Instead of passing infrastructure outputs between stages, the post-deploy stage reads them back
**from the provisioned resource group via `az`**: it finds the latest succeeded ARM deployment in
the resource group and reads `properties.outputs`, then hydrates an azd environment and a repo-root
`.env` from those values. The solution's post-deploy scripts then read configuration exactly as
`azd` would have written it — no script edits, no solution-specific mapping. (`azd provision`
creates the ARM deployment whose outputs are read. A raw `terraform apply` leaves no ARM deployment
in the resource group, so the Terraform provision template instead publishes `terraform output
-json` as an `infra-outputs` artifact and the stage hydrates from that — same shape, same result.
See `references/post-deploy-conventions.md`.)

## Use when

The user wants the Azure DevOps deploy pipeline to run the solution's post-provision/post-deploy
scripts (building images, seeding data, assigning roles, etc.) and its tests after the infra
deploy, so one run provisions, configures, tests, and (via the deploy pipeline) cleans up.

## What this skill ships

- **`templates/azure-pipelines-post-deploy.yml`** — a reusable **stage template** defining the
  `PostDeployTest` stage: a `post_deploy` job (hydrate from the RG → run discovered scripts) plus a
  conditional `playwright` job (e2e, needs the live app). Unit tests are NOT in this stage — they
  run on every PR in the flavor CI pipeline. The infra deploy pipeline references this stage and the
  Cleanup stage depends on it.
- **`scripts/`** — `check-prereqs.sh`, `inspect-post-deploy.sh` (discovers azd hooks, guides, and
  the ordered post-deploy plan), `discover-tests.sh` (discovers unit + Playwright tests),
  `validate-pipelines.sh`.
- **`references/post-deploy-conventions.md`** — the discovery contract, the RG→azd-env bridge, the
  test-detection rules, and the render mapping.

## The discovery contract (how a repo is read generically)

Every azd solution declares its post-deploy work in `azure.yaml` under `hooks:`
(`preprovision` / `postprovision` / `predeploy` / `postdeploy`). For each hook `inspect-post-deploy.sh`
reads the **POSIX variant** (CI is Linux) and classifies its `run_mode`:
- **`executes`** — the hook invokes a script (`pwsh -File x.ps1`, `bash x.sh`, `./x.sh`). Those
  scripts are the automated post-deploy steps.
- **`prints_only`** — the script name only appears inside `echo`/`printf`/`Write-Host`; the hook is
  telling a human to run it. Still a plan entry, but flagged so you confirm it with the user.

The deployment guide is parsed for its **deployment / post-deployment sections** (level-2+ headings
whose text contains "deploy" — e.g. "Deployment Steps", "Deploying with AZD", "Post Deployment
Steps"); script references in those sections merge in, and **relative markdown links** from them
into sibling docs are followed one level so a step that lives in a linked guide (a separate
doc referenced from the section) is still captured. The result is `post_deploy_plan.scripts` — hook scripts (in hook
order) plus guide-only scripts, **deduped by normalized filename stem**. Toolchain needs
(`needs_pwsh`/`needs_bash`/`needs_python`) and `interactive_prompts` / `reads_azd_env` are derived
mechanically — never by domain keywords.

**Read the main README first, then follow it.** The discovery scripts capture azd hooks and script
references, but the authoritative human contract is the repo's top-level `README.md`. Read it first,
then follow its links to whatever deployment doc it redirects to (a `docs/DeploymentGuide.md`, a
component sub-`README.md`, etc.) and read that too — repos put the real steps in different places, so
never assume a fixed filename. From the README and the doc it points to, capture the
**application-deploy step** in addition to the configuration scripts: building/pushing the container
image(s) and deploying the app (`az acr build`/`docker build`+`push`, then
`az containerapp`/`az webapp`/`az functionapp`/`azd deploy`, or a `task deploy`/`make deploy` target
that wraps them). **The application-deploy step ALWAYS runs in the `post_deploy` job, before cleanup
— it is the end-to-end validation the ephemeral pipeline exists to perform, and it is required
whether or not any Playwright/e2e suite exists** (otherwise the pipeline just provisions infra and
tears it down without ever deploying the app). Detect it by the commands it runs — never by a
hardcoded target or filename — and render it into `__POST_DEPLOY_STEPS__`. **Never downgrade it to a
manual reminder merely because the recipe reads live infra state** (`terraform output` /
`terraform show`): by the time this job runs it has already hydrated every infrastructure output into
the azd env, a repo-root `.env`, and pipeline/environment variables under canonical `UPPER_SNAKE`
names, so reconstruct the recipe's underlying commands to read those hydrated values instead of
calling `terraform output`. Surface app-deploy as a reminder **only** when it is genuinely
un-automatable — interactive with no unattended path, or documented in prose with no runnable command
at all. See `references/post-deploy-conventions.md`.

`discover-tests.sh` reports which test categories exist: `unit_frontend` (a `package.json` `test`
script), `unit_backend` (pytest and/or dotnet test projects), and `playwright` (a Playwright config
or Python Playwright usage). **The unit categories (frontend + backend) are rendered into the flavor
CI pipeline(s)** (`ado-cicd-bicep-workflows` / `ado-cicd-terraform-workflows`), which run on every PR
— unit tests are hermetic, so they need no provisioned infra. **Only `playwright`/e2e is rendered
into this post-deploy stage**, because e2e runs against the live deployed app — Playwright is
**never** put in CI. The split is **categorical and is not a question to raise**: unit (frontend +
backend) → CI, Playwright/e2e → the deploy pipeline's post-deploy stage. (If a suite named "unit"
actually requires live endpoints, it is really integration — keep it in this post-deploy stage, not
CI.)

## Hard constraints

- **Ask before any mutation.** Confirm before writing repo files or triggering a deployment.
  Read-only discovery needs no approval.
- **No solution-specific content in the skill.** The skill's own files must never name a scenario,
  domain, auth mode, or specific filename. Anything solution-specific is discovered at runtime and
  injected into the rendered stage only.
- **No source changes.** Never edit the repo's Bicep/Terraform, application code, or post-provision
  **scripts**. Only the pipeline YAML is authored.
- **Read config back from the RG (no script edits).** The post-deploy scripts read configuration
  the way `azd` would have written it. The stage reproduces that from the resource group's
  deployment outputs and hydrates the azd env + a repo-root `.env`. See
  `references/post-deploy-conventions.md`.
- **Confirm the plan once; don't blindly transcribe the guide, and don't multiply questions.**
  Present the discovered `post_deploy_plan.scripts` (with `source` and each hook's `run_mode`), the
  `guides` list, and your **already-decided** classification together as a single plan to approve
  before writing anything — that one confirmation **is** the approval, not a series of separate
  questions. Decide every routine item yourself, by content, and simply state it: which scripts run
  in CI and in what order, test placement (per the categorical unit→CI / e2e→post-deploy rule
  above), and any version
  defaults. Steps flagged `interactive_prompts` or `prints_only` are resolved by supplying the
  non-interactive default and noting it — not by asking. **Escalate a separate keep/skip decision
  only for a genuinely cost-bearing or destructive step**: an *optional* post-deploy validation that
  consumes paid quota on every run (e.g. a live AI/model **evaluation** call or a paid external API)
  or an irreversible action. Default such a step to **skip**, surface it as the one explicit choice,
  and explain its per-run cost; the required application-deploy step is never treated this way — it
  always runs.
- **Every discovered script runs in CI.** If a mandatory post-deploy step has a runnable script
  (`.sh`/`.ps1`/`.py`), it runs in the pipeline **regardless of what the script does**. Do **not**
  downgrade a scripted step to a reminder because of the kind of work it performs; run it and let
  any failure surface in the logs to debug. **This includes privileged directory operations** (e.g.
  granting Entra **admin consent**, creating role assignments): if a script performs them, it still
  runs in the job — even when the repo's docs suggest a human "may" do it by hand. Such scripts are
  written fail-soft (they print a portal link when the pipeline identity lacks the directory role);
  render that only as a manual-reminder **caveat if it fails**, never as a replacement for running
  the script. (Auto-consent succeeds when the pipeline's service connection identity holds a
  privileged Entra role — Cloud Application Administrator / Privileged Role Administrator — or the
  Graph `DelegatedPermissionGrant.ReadWrite.All` permission; otherwise it fails-soft.) Classify three ways: **run in CI** (default — every
  discovered script, using non-interactive defaults), **manual reminder** (only steps the guide
  documents that have **no script** to invoke — actions a person performs by hand that CI cannot
  script), **developer-only** (exclude — genuinely interactive local validation/smoke steps with no
  unattended path and no deployment effect). A step is never developer-only merely because it takes
  a selector or a simple confirmation prompt; supply the default and run it.
- **Cleanup is the deploy pipeline's job.** This stage does not delete the resource group; the
  infra deploy pipeline's Cleanup stage (`condition: always()`, `dependsOn: PostDeployTest`) does,
  so tests run against live infrastructure and it is always torn down afterward.
- **Use the bundled scripts.** Run `scripts/*.sh` in place by absolute path; never copy them into
  the target repo or replace them with inline one-offs. Extend them if a capability is missing.
- **Rely on active sessions.** Use the user's existing `az` / `az devops` sessions; never ask for
  credentials.
- **Temp files under `.agent/tmp/`, always cleaned up.** Write scratch (e.g. `post-deploy-facts.json`,
  `test-facts.json`) only there; remove it before finishing, even on failure.
- **Variables only, never secrets.** The service connection holds the credential; the variable
  group holds non-secret configuration. Never read/set secret values, and never print variable
  *values*.

## Process

1. **Validate tools.** Run `scripts/check-prereqs.sh` (`jq` required; `az`/`azd` from active
   sessions).
2. **Discover post-deploy.** Run `scripts/inspect-post-deploy.sh <repo_root> > .agent/tmp/post-deploy-facts.json`.
   It reports `infra_kind`, the `azd` block (per-hook `run_mode` + `scripts`), the `guides`, and the
   derived `post_deploy_plan` (`scripts:[{path,runner,source}]`, `requirements`, `reads_azd_env`,
   `interactive_prompts`, `needs_*`) plus `notes`.
3. **Discover tests.** Run `scripts/discover-tests.sh <repo_root> > .agent/tmp/test-facts.json`. It
   reports `unit_frontend`, `unit_backend` (pytest + dotnet), and `playwright` presence + directories.
   The **unit** categories are consumed by the flavor CI skill(s) to render their PR unit-test jobs;
   **only** `playwright` is rendered into this post-deploy stage. (Reuse an existing
   `test-facts.json` if the CI skill already produced one; the same file drives both.)
4. **Read the README and guides; confirm the plan with the user.** Start at the repo's top-level
   `README.md`, then follow its links to whatever deployment doc(s) it redirects to and open every
   path in `guides`. Present `post_deploy_plan.scripts` **and the application-deploy step** you found
   in the README/guide (image build+push and app deploy, even when it is inline `az …` commands or a
   `task`/`make` target rather than a standalone script). Agree which steps CI runs (and their
   order), which are interactive/`prints_only`, and which are manual post-steps (reminders only).
   Confirm whether a Playwright/e2e suite runs here (and note that unit tests run in the CI
   pipeline). **Get explicit approval before writing files.**
5. **Render the stage** `azure-pipelines-post-deploy.yml` into the ADO pipelines folder next to the
   infra deploy pipeline, substituting placeholders (no other edits):
   - `__PY_VERSION__` → the repo's Python version (from `.python-version`/pyproject/guide, else a
     sensible default like `3.11`).
   - `__REQUIREMENTS__` → `post_deploy_plan.requirements`. **Keep the Python block** (marked
     `skill: keep … when needs_python`) only when `needs_python` is true; otherwise delete it.
   - `__POST_DEPLOY_STEPS__` → one `run_step <runner> <path> [args]` line per confirmed script, in
     order (`runner` ∈ `bash`|`pwsh`|`python`). Append a non-interactive default selector where a
     step needs one; prefix `printf '\n' | ` for a simple confirmation prompt. **Always include the
     application-deploy step here** (image build+push, then the app roll-out) — a `run_step` line
     when it is a script, or the raw command line(s) when it is a target/command (e.g.
     `azd deploy --all --no-prompt`, or the `az acr build …` + `az containerapp …` a `task deploy`
     wraps). If the recipe reads live state (`terraform output`), do **not** invoke the target
     verbatim: inline its underlying commands and read each value from the hydrated env instead — the
     canonical `UPPER_SNAKE` output name is already exported as an env/pipeline variable and written
     to `.env`, so replace e.g. `$(terraform output -raw acs_connection_string)` with
     `$ACS_CONNECTION_STRING`.
   - `__MANUAL_POST_STEPS__` → the agreed manual steps as markdown bullets, or a "none" note. Only
     genuinely un-automatable steps go here (actions a person performs by hand that CI cannot
     script). **Do not list the application-deploy step here just because it reads live infra
     state** — that is handled by reconstructing it from the hydrated outputs above. List app-deploy
     here only in the rare case it is truly interactive with no unattended path, or documented in
     prose with no runnable command at all; then give the exact commands and the note that e2e will
     hit an undeployed app until it is run.
   - **Playwright/e2e job** — keep the `playwright` job only when `test-facts.json` reports
     `playwright.present`; otherwise delete it (the stage then just runs `post_deploy`). Fill the
     matching Playwright variant (`__PW_DIR__`/`__PW_REQS__`; keep the python **or** node block per
     `playwright.language`). The `playwright` job's `dependsOn: post_deploy` is already correct — no
     unit-test jobs live in this stage. (Unit tests are rendered by the flavor CI skill instead.)
6. **Wire it into the deploy pipeline.** The `ado-cicd-bicep-workflows` /
   `ado-cicd-terraform-workflows` deploy pipelines already reference this stage template between
   Provision and Cleanup. Confirm the reference passes `serviceConnection`, `resourceGroup`,
   `azureEnvName`, `subscriptionId`, and `dependsOn`.
7. **Validate.** Run `scripts/validate-pipelines.sh` on the rendered stage; report its result.
8. **Clean up** all files created under `.agent/tmp/` (remove the directory if empty), even on
   failure.

## Output

Report, in order:
1. **Detected post-deploy plan** — infra flavor, azd hooks used and their `run_mode`, the guides,
   the ordered scripts (with runner + source), toolchain needs, and any interactive-prompt flag.
2. **Detected tests** — which categories are present (frontend / pytest / dotnet / Playwright), their
   directories, and where each runs: unit categories in the flavor CI pipeline (on every PR),
   Playwright/e2e in this post-deploy stage.
3. **Confirmed split** — the CI-run steps (and order), the manual/interactive steps, and the tests
   to run, as agreed with the user.
4. **Generated files** — the post-deploy stage and how the deploy pipeline references it.
5. **Setup required** — any non-output values the scripts need that CI cannot reconstruct (surfaced
   as required variables/reminders).
6. **Validation** — `scripts/validate-pipelines.sh` result.
7. **Cleanup** — confirm `.agent/tmp/` files were removed.

## Known limitation (surface to the user; not a code change)

- **Preprovision-generated values are not deployment outputs.** Some solutions generate secrets or
  IDs during a `preprovision` hook (not emitted as outputs). The stage reconstructs config from the
  resource group's deployment **outputs** only, so such values cannot be reproduced automatically.
  Discovery flags the relevant hook; surface these as required variables the user must set, or as a
  manual reminder.
