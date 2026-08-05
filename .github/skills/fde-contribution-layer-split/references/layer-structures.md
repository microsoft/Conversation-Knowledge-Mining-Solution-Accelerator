# Standard Internal Structure (Expected Layer Shape)

Read-on-demand reference for `fde-contribution-layer-split`. This is the
**authoritative** canonical shape each staged layer subfolder must follow —
apply it verbatim.

Stage every layer subfolder to the structure below, mirroring the eventual live
layer — **not** whatever shape the source contribution used — so a staged folder
can later be moved into the live layer unchanged. Create only the subfolders a
part actually needs (omit empty ones), and give every staged layer subfolder a
`README.md`.

## Stable Core — `stable-cores/<name>/`

Stable Core must **always ship both IaC flavors — Bicep and Terraform** — as
first-class, side-by-side options under `infra/`, each with its own reusable
`modules/` (never a single monolithic template). A contribution may provide only
one flavor; when so, stage it as-is and **author the equivalent other flavor** (a
faithful translation of the same resources, parameters, and module layout). Mark
every generated flavor in `infra/README.md` and its file headers as **generated
from the provided `<flavor>` — human-review/validate before deployment**, and
record it as a distinct part so a reviewer approves it explicitly.

Use **vanilla Bicep and Terraform only** — no Azure Verified Modules (AVM) and no
`br/public` or other external module-registry references; every module must be
locally authored in-repo. This is a **hard requirement even when the source
contribution is built on AVM**: never carry AVM forward into the staged Stable
Core. Concretely, the staged output must **not** contain:

* any `avm/` folder (e.g. `infra/bicep/avm/modules/...`),
* any `module ... 'br/public:avm/...'` or other registry reference, or
* any "plain resource then AVM-module update" two-step wrapper pattern.

When the source uses AVM, **rewrite each AVM module as a plain, self-contained
vanilla module** — direct `resource` declarations (Bicep) / `resource` blocks
(Terraform) — placed under `infra/bicep/modules/` and `infra/terraform/modules/`
(never an `avm/` subfolder). Preserve the equivalent resource configuration and
WAF hardening, drop the registry dependency, and record the conversion as a
distinct part so a reviewer approves it. Author both flavors to **Azure
Well-Architected Framework (WAF)** principles (reliability, security, cost
optimization, operational excellence, performance efficiency), reflecting those
choices (identity/network baselines, diagnostics/observability, resilience
defaults) in the modules and `infra/README.md`.

```text
stable-cores/<name>/
├── infra/
│   ├── bicep/
│   │   ├── main.bicep        # azd up / deployment entrypoint (Bicep)
│   │   └── modules/          # reusable Bicep resource modules
│   ├── terraform/
│   │   ├── main.tf           # deployment entrypoint (Terraform)
│   │   ├── variables.tf
│   │   └── modules/          # reusable Terraform modules
│   ├── landing-zone/         # networking, security/identity baseline (shared)
│   └── README.md             # both IaC flavors and how to deploy each; flags any generated flavor
├── src/       # core service integration + environment bootstrap (azd up entrypoint)
├── skills/    # reusable engineering automation / guardrails
├── docs/      # deployment + architecture guidance
└── README.md  # what this core provides (ships both Bicep and Terraform) and how it is deployed
```

## Technical Pattern — `technical-patterns/<name>/`

```text
technical-patterns/<name>/
├── src/       # agent/app orchestration, prompt architecture, tool-calling, UI/workflow scaffolding
├── config/    # externalized extension points: config schema, `.env.example`, prompt templates parameterized by env/config (no domain values baked in)
├── infra/     # pattern-scoped resource control-plane wiring
├── skills/    # pattern-level automation
├── evals/     # pattern-level checks / validation assets
├── docs/      # pattern usage + configurable extension-point docs (list every env var / setting an Industry Scenario must supply)
└── README.md  # what the pattern does, the extension points it exposes (e.g. system prompt, model/endpoint, thresholds via env), and which Stable Core(s) it builds on
```

## Industry Scenario — `industry-scenarios/<vertical>/<name>/`

```text
industry-scenarios/<vertical>/<name>/
├── data/      # scenario datasets (sample/synthetic/structured), schemas
├── src/       # domain prompts, config mappings, business rules, POC presets
├── evals/     # scenario eval datasets/harnesses (accuracy, grounding, safety, latency, cost)
├── docs/      # scenario documentation
└── README.md  # the scenario, its vertical, and which Technical Pattern(s) it composes with
```

`<vertical>` must be one of the standard verticals: `energy`, `fsi`, `gov`,
`hls`, `mfg-mobility`, `physical-ai`, `rcg`, `security`, `telco-medio`. Do not
invent a new vertical unless the user explicitly confirms one is needed.
