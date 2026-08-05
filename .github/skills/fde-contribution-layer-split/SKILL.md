---
name: fde-contribution-layer-split
description: "Use when a user provides or contributes a solution — typically staged under workspace/, but any resolved path is supported — to classify its parts across the stable-core, technical-pattern, and industry-scenario layers, check each part against existing layer content, and stage the split as three separate folders inside workspace/ without touching the live layer folders."
argument-hint: "Path or description of the contributed solution (in workspace/ or elsewhere), and the target vertical if known (energy, fsi, gov, hls, mfg-mobility, physical-ai, rcg, security, telco-medio)."
---

# Contribution Layer Split Skill

Use this skill when a contributed or user-provided solution — at a resolved path that may or may not be under `workspace/` — needs to be decomposed into the three accelerator layers defined in `docs/design/accelerator-framework.md`: Stable Core, Technical Pattern, Industry Scenario. The output is always staged inside `workspace/`, as three separate folders, never written or merged directly into the live `stable-cores/`, `technical-patterns/`, or `industry-scenarios/` folders. A human reviews the staged split and performs the final move.

**Read-on-demand resources** (load when you reach the relevant step):

* `references/layer-structures.md` — authoritative canonical folder shapes for all three layers, the Stable Core IaC rules (both flavors, vanilla-only/no-AVM, WAF), and the valid verticals. Read before staging any layer subfolder.
* `assets/report-templates.md` — the Summary Report, Per-Part Review Detail, and Delta & Coverage templates. Read before producing the report.

## The Three Accelerator Layers

Every accelerator is composed of three layers, defined in `docs/design/accelerator-framework.md`, with a one-to-many dependency: **Industry Scenario → Technical Pattern → Stable Core** (one Scenario can compose multiple Patterns; one Pattern can build on multiple Cores). Understand what each layer *is* before classifying any file into it.

* **Stable Core** — the customer-agnostic **platform/infra baseline**. The reliable, enterprise-ready foundation every solution sits on, with no customer- or domain-specific content. It provides infrastructure-as-code, core cloud/service integrations, security/identity/network defaults, and a standard deployment path. *Example: `ms-iq` (Microsoft IQ baseline, no customer customization).*
* **Technical Pattern** — a reusable, **domain-independent application/agent architecture**: the *shape* of a class of solutions. It defines how the app/agent behaves and how the user interacts with it, but carries **no domain data and no hardcoded domain values**. It must be generic: everything domain- or customer-specific (endpoints, prompts, data bindings, business rules, thresholds) is externalized as **configurable** extension points — settings, parameters, config files, or environment variables — that an Industry Scenario supplies at compose time. If a part only works for one domain or has domain values baked in, it is not a Technical Pattern; the generic skeleton belongs here and the domain values belong in Industry Scenario. *Examples: `chat-with-data`, `call-center`, `document-processing`, `realtime-alerts`.*
* **Industry Scenario** — the **domain/customer-specific data and configuration** that makes a Technical Pattern relevant to a concrete business use case, organized by vertical. It is the datasets, domain prompts, business rules, and evaluations for one scenario. *Example: `energy/welloil-alarms`.*

## Repository Layer Roots

The logical layer names map to these repository-relative live roots:

* `stable-cores/` → `001-wip-repo-structure/stable-cores/`
* `technical-patterns/` → `001-wip-repo-structure/technical-patterns/`
* `industry-scenarios/` → `001-wip-repo-structure/industry-scenarios/`

Resolve and record these physical roots before comparison or promotion; every report must use the full repository-relative live destination for each New or Delta part. Never create a top-level `stable-cores/`, `technical-patterns/`, or `industry-scenarios/` directory by stripping the staging prefix. If the expected roots do not exist on the selected base branch, stop and request a corrected plan rather than inferring a location.

## Layer Classification Framework

Classify every distinct part of the contribution using the signals below, not just its folder name in the source contribution.

| Layer | Purpose | Signals | Destination |
|---|---|---|---|
| Stable Core | Customer-agnostic platform/infra baseline | IaC in **both Bicep and Terraform** (each with reusable `modules/`), landing zone, core service wiring (Foundry, Fabric, MCS, AKS, Firewall, Frontdoor, App Services, databases, observability), identity/network/security baselines, `azd up` entrypoint, engineering guardrails | `stable-cores/<name>/` |
| Technical Pattern | Reusable app/agent architecture, domain-independent and generic | Agent/app orchestration, prompt architecture, tool-calling wiring, UI/frontend scaffolding, resource control-plane wiring, and **configurable** extension points (settings/params/config schema/env vars) that externalize all domain-specific values — no hardcoded domain data. For example, the **system prompt, model/endpoint, and business thresholds are supplied through environment variables or config files**, not baked into code | `technical-patterns/<name>/` |
| Industry Scenario | Domain/customer-specific configuration and data | Scenario datasets, domain prompts, config mappings, business rules, eval datasets/harnesses, POC presets | `industry-scenarios/<vertical>/<name>/` |

Cross-cutting parts (skills/automation, CI/CD, telemetry, governance) are not a fourth layer. Apply them inside whichever layer(s) they support; do not force them into a single layer or leave them unclassified.

A single contribution usually spans more than one layer. Split it into its constituent parts before classifying, and classify each part independently.

## Standard Internal Structure (Expected Layer Shape)

Stage every layer subfolder to the canonical shape mirroring the eventual live layer — **not** the source contribution's arrangement — so a staged folder can later be moved into the live layer unchanged. Create only the subfolders a part needs, and give each a `README.md`.

The full canonical folder trees for all three layers, plus the Stable Core rules (both IaC flavors, vanilla-only/no-AVM, WAF principles, generated-flavor flagging) and the valid verticals list, are the authoritative definition in **`references/layer-structures.md`** — read it before staging any layer subfolder and apply it verbatim. **Vanilla-only is a hard rule even when the source uses AVM:** the staged Stable Core must contain no `avm/` folder and no `br/public:avm/...` references — rewrite any AVM module as a plain vanilla module under `infra/<flavor>/modules/`. In brief: Stable Core → `infra/{bicep,terraform}` (each with `modules/`) · `landing-zone` · `src` · `skills` · `docs` · `README`; Technical Pattern → `src` · `config` · `infra` · `skills` · `evals` · `docs` · `README`; Industry Scenario → `data` · `src` · `evals` · `docs` · `README` under one of the standard verticals (`energy`, `fsi`, `gov`, `hls`, `mfg-mobility`, `physical-ai`, `rcg`, `security`, `telco-medio`).

## Staging Output Convention

Never write or merge directly into the live layer folders. Create one staging folder per run inside `workspace/`, named after the contribution (e.g. `workspace/<contribution-name>-split/`), with exactly three subfolders mirroring the live layer names:

```text
workspace/<contribution-name>-split/
├── stable-cores/
├── technical-patterns/
└── industry-scenarios/
```

Place each classified part under the matching staging subfolder using the same name it will use live (`stable-cores/<name>/`, `technical-patterns/<name>/`, `industry-scenarios/<vertical>/<name>/`), so the staged output can later be moved into place with a simple directory move and no renaming.

## Match and Dedup Rule

Even though nothing is written to the live layers, still check the live layers so the report tells the human whether a part is genuinely new or already covered:

1. For Stable Core parts, search `stable-cores/*` for equivalent service/infra coverage.
2. For Technical Pattern parts, search `technical-patterns/*` for an equivalent interaction pattern (for example, chat-with-data, call-center, document-processing, realtime-alerts).
3. For Industry Scenario parts, search `industry-scenarios/<vertical>/*` first, then other verticals for a transferable equivalent.

Compare on capability and architecture, not filenames: same core service integrations, same agent/app pattern shape, or same scenario data/prompt/eval intent count as a match even if naming differs.

**New-vs-Same decision for Technical Patterns.** A Technical Pattern is the *architecture shape*, so decide on architecture, not customer-facing surface. Classify as **New** only when the architecture is fundamentally different: overall architecture, **data processing model**, **agent orchestration**, or **core API behavior** changes. Treat it as the **same** pattern when only **customer/domain logic**, **prompts**, **number of agents**, **UI**, or **configuration** change — none of these alone justify a new pattern. Purely domain/customer-specific changes route to the **Industry Scenario** layer; a same-pattern change that adds a genuinely reusable, domain-independent capability (new extension point, tool integration, channel) is a **Delta** against the existing pattern.

| Match outcome | Required action |
|---|---|
| Exact or functional match found | Do not stage anything for this part. Record the match in the report and skip it. |
| Match found but the contribution adds real capability (new integration, new extension point, new dataset/eval) | Stage only the delta under the staging folder, using the existing subfolder's name, and note in its README that it is a delta intended to update `stable-cores/<name>/` / `technical-patterns/<name>/` / `industry-scenarios/<vertical>/<name>/` once reviewed. Do not touch the existing live subfolder. |
| No match found | Stage the full part under the staging folder as new. |
| Unclear whether it matches | Ask before staging a duplicate or labeling something as a delta against the wrong existing folder. |

Never delete, overwrite, or write into existing live layer content, under any match outcome.

## Intake and Change Analysis Plan (persisted to markdown, approval-gated — both modes)

Every run — whether triggered by a **folder/path** contribution or by an **FDE opening a pull request** — follows the same mandatory sequence: **analyze → plan (persist to md) → human review/approve → split → human review (staged split + per-part evidence) → promote via PR**. Nothing is classified, staged, or promoted until a human approves the persisted plan.

1. **Analyze the contribution against the live layers.** Read the contribution (resolved files for folder/path mode, or the PR diff for PR mode) and decompose it into parts. Determine *what actually changed* by comparing each part against the live layers with the content/capability-based Match and Dedup Rule — not by folder name or the raw file list. Assign each part the shared outcome vocabulary: **Matched** (exists live), **Delta/Upgrade** (an equivalent exists live and this adds real capability), or **New** (no live equivalent). These outcomes must agree with the `comparison-report.md`'s later `git diff` evidence.
2. **Produce a Change Analysis & Split Plan and persist it** to `workspace/<contribution-name>-split/split-plan.md` (create the staging folder first). This md file is the human review surface and must contain at minimum:
   * **Summary of change** — what the contribution adds or changes, in plain language.
   * **Per-part plan table** — for every part: the part, target layer, outcome (**Matched** / **Delta/Upgrade** / **New**), and action.
   * **For Delta/Upgrade parts, the exact existing live target** it merges into, *why* (capability/architecture match), and the concrete delta (hunks/files). For New parts, the new destination path.
   * **Stable Core IaC completeness** — if a Stable Core part provides only one IaC flavor, list the **generated equivalent flavor** as its own entry, marked *generated, pending human review/validation*.
   * **Target base branch** for the PR (`dev` or as specified) and **Risks / open questions**.
3. **Human review gate.** Present `split-plan.md` and stop. On comments/changes, revise and re-request approval — do not proceed on unaddressed comments. **Do not dispatch classifiers or stage anything before approval.**
4. **On approval, split into the three sections** per the **Workflow** below: stage each approved part (New as full adds, Delta/Upgrade as surgical deltas against the named target), then append the realized split (final destinations + outcomes) back into `split-plan.md`.
5. **Then produce the report + comparison markdown, and promote.** Generate the Summary Report + Per-Part Review Detail and the mandatory `comparison-report.md` (the persisted Promotion Plan). After the human approves the exact report, hand off to the **FDE Split Promoter**, which branches from `dev` (or the specified base) and raises a PR to it. Never commit directly to the base branch.

`split-plan.md` is the persistent record: written before review, updated on comments, finalized with the realized split after approval.

## Workflow

Run this only **after** the `split-plan.md` has been approved by a human (see **Intake and Change Analysis Plan** above). The plan-and-approve gate applies to every contribution, folder/path or PR.

1. Locate the contribution at the resolved path (under `workspace/`, elsewhere in the repo, or a confirmed external path). If no path was given, look in `workspace/`; if nothing is there, ask before proceeding.
2. Decompose the contribution into parts — infra/platform, agent/app pattern, and domain data/config/eval — without assuming the source folder layout maps 1:1 to the three layers.
3. Classify each part using the Layer Classification Framework, noting any cross-cutting part and where it attaches.
4. Run the Match and Dedup Rule for each part against its destination layer folder(s).
5. For matched parts, copy/move nothing; record what is identical and what differs for the summary.
6. Stage new/delta parts under the run's staging folder (never the live layer):
   - Stable Core: `workspace/<contribution-name>-split/stable-cores/<name>/`
   - Technical Pattern: `workspace/<contribution-name>-split/technical-patterns/<name>/`
   - Industry Scenario: `workspace/<contribution-name>-split/industry-scenarios/<vertical>/<name>/` — use an existing vertical (`energy`, `fsi`, `gov`, `hls`, `mfg-mobility`, `physical-ai`, `rcg`, `security`, `telco-medio`) unless the user confirms a new one.
7. Stage each subfolder to the canonical shape from **Standard Internal Structure** above — Stable Core (`infra/{bicep,terraform}/src/skills/docs`), Technical Pattern (`src/config/infra/skills/evals/docs`), Industry Scenario (`data/src/evals/docs`) — regardless of the source arrangement, creating only the subfolders the part needs.
8. Add/update a short `README.md` in each staged subfolder: what it is, which layer(s) it composes with, and — for deltas — which live subfolder it updates.
9. Do not delete the source contribution without explicit user confirmation; if approved, remove only what was fully migrated.
10. Produce the Summary Report, including the required **Per-Part Review Detail** section.
11. Generate the mandatory `comparison-report.md` via the **FDE Split Comparison Reporter** against the staging folder (default `workspace/<contribution-name>-split/comparison-report.md`). A staged split is ready for review only once this report exists; report its path alongside the staging folder.

## Reporting (Summary + Per-Part Detail + Coverage)

Every run must emit three report sections, in order, after the split is staged — the full templates and example tables are in **`assets/report-templates.md`**; read it and follow it verbatim:

1. **Summary Report** — an exhaustive, mutually-exclusive table: every file/component under the resolved solution path appears in exactly one row (staged new/delta, matched-ignored, or an explicit **Unclassified** / **Out of scope** row). Never omit a file.
2. **Per-Part Review Detail (required)** — one entry per in-scope part with enough evidence to approve/reject it **without** opening the source: **New** = staged file inventory + live destination; **Delta** = exact live target + concrete diff/hunks (read-only `git diff --no-index`) + why the delta is real; **Matched** = the live equivalent path + why it matches.
3. **Delta & Coverage Summary** — a quantitative roll-up computed from the outcomes (not estimated), with the headline **% New or Delta** `= (New + Delta) / (Matched + Delta + New) × 100`, per layer and overall, excluding Unclassified/Out-of-scope from the percentage (report their counts separately).

## Promote After Review

Staging and reporting never touch the live layers. A staged split is ready for review only once **both** the enriched Summary Report (with Per-Part Review Detail) **and** the mandatory `comparison-report.md` exist. After a human reviews and approves them, the approved **New** and **Delta** parts are promoted into the live layers by the **FDE Split Promoter** subagent — a distinct, human-gated step that is the *only* one permitted to write to the live layers, and even then only via a pull request, never a direct commit to the base branch.

Promotion follows a strict **report → approve → branch → PR** contract:

1. **Report (read-only).** Use `comparison-report.md` as the Promotion Plan. It enumerates each staged part, outcome, action, live target, risk, target base branch, and proposed branch name. Make no writes to the live layers, create no branch, and make no commit before approval.
2. **Approve (human gate).** Stop and wait for explicit human approval of the exact report. The human may approve the whole report or narrow it to a subset. Nothing is applied until approval is given.
3. **Branch + apply (only after report approval).** Verify the staged content, exact repository-relative live destinations, and base still match the approved report, then create a new `promote/<contribution-name>` branch from the current remote tip of the chosen base (`dev` unless specified). Apply the approved changes without requesting a second promotion approval. Never work on the base branch directly.
4. **Commit verification.** Commit every approved live-layer change, require a clean worktree, and verify that every path in `git diff --name-only origin/<base>...HEAD` is covered by the approved Promotion Plan and is under the recorded physical live roots. Stop if files remain uncommitted or any path is misplaced or unapproved.
5. **Push verification and PR.** Push the branch, fetch its remote ref, and require the local `HEAD` SHA to equal `origin/<promotion-branch>`. Only after that equality check may the promoter report the branch as pushed or open a pull request against the chosen base branch. The base branch is updated only by merging that PR, never by a direct push.

Per-outcome apply rule:

| Outcome | Promotion action |
|---|---|
| Matched | Not promoted. It already exists live; skip it. |
| New | Copy the approved staged folder into its live layer path (`stable-cores/<name>/`, `technical-patterns/<name>/`, `industry-scenarios/<vertical>/<name>/`), preserving the canonical Standard Internal Structure. Confirm the live path does not already exist (if it does, treat it as a Delta). |
| Delta | **Surgical merge** only: apply just the added/changed hunks into the existing live file(s). Never overwrite a shared live file wholesale — other domains/config may depend on it. Re-diff after applying to confirm only the intended lines changed. |

If the staged split lives under a **gitignored** staging root (for example `.copilot-tracking/`), the approved files must be copied *out* into the real live layer paths before committing — gitignored paths are not committable in place.

The promotion step never re-classifies or re-stages content (that is the classifier subagents' job), never promotes `Matched` parts, never deletes live content except as part of an approved delta, and never commits directly to or force-pushes the base branch. If push or PR creation fails (access/SSO/protected branch), it stops, leaves the branch intact, and reports manual `git push` / PR steps rather than forcing anything.



Finish only when:

- Every distinct part is classified into exactly one primary layer (cross-cutting parts noted against the layer[s] they support) and was checked against live layer content before staging.
- Nothing was written, merged, overwritten, or deleted in the live layers — all new/delta content lives only under `workspace/<contribution-name>-split/`.
- Staged subfolders follow the canonical **Standard Internal Structure** and each has a README describing layer composition and, for deltas, the live subfolder they target.
- The source contribution was left untouched unless the user approved removing fully migrated content.
- The Summary Report accounts for every part (including skipped matches and unclassified/out-of-scope rows) — no file silently dropped, none staged under more than one layer.
- The **Per-Part Review Detail** is present with per-part evidence (New = file inventory; Delta = target live file + diff/hunks; Matched = matched live path + reason).
- The mandatory `comparison-report.md` has been generated by the FDE Split Comparison Reporter and its path reported.
- The Delta & Coverage Summary is included, computed from the per-part outcomes, with per-layer and overall `% New or Delta` and the count of any excluded (unclassified/out-of-scope) parts.
