---
name: repo-scenario-discovery
description: Discover sample questions and scenarios/use cases from ANY repository before planning tests for a web app. Use this at the START of test planning for any web app served from a repo. It scans README/docs/config for a "Sample Questions" (or equivalent) section and for a list of scenarios/use cases/datasets/modes. Behavior degrades gracefully — some repos have neither, some have only questions, some have only scenarios, some have both. If more than one scenario is found, it asks the user which scenario is loaded in the app URL they provided; otherwise it proceeds silently.
---

# Repo Sample-Question & Scenario Discovery (generic)

Use this skill BEFORE navigating the app or calling `planner_setup_page`. Its job
is to look for two OPTIONAL pieces of context in whatever repo the user is
working in, without assuming any specific file names, folder layout, or
vocabulary:

1. **Sample questions / example prompts** the planner can reuse verbatim as seed
   inputs for chat / search / query / form scenarios.
2. **Scenarios / use cases / datasets / modes / personas** that change what the
   app displays.

Both are optional. Do not fail if either is missing — just report what you
found and move on.

## When to use

- The user asked you to plan tests for a web app URL that appears to be served
  from the current workspace.
- You have not yet explored the live UI.

## When NOT to use

- The user already provided the scenario name AND sample questions inline.
- The workspace is clearly unrelated to the app under test (empty folder, or a
  docs-only repo for a different product).

## Workflow

### 1. Detect the doc surface

Identify plausible documentation locations without hardcoding names:

- The workspace root and any `README*` / `readme*` / `Readme*` file up to ~2
  levels deep.
- Any top-level docs folder: `docs/`, `doc/`, `documentation/`, `wiki/`,
  `website/`, `site/`.
- Any top-level samples / examples folder: `samples/`, `examples/`, `demo/`,
  `demos/`, `fixtures/`.
- Any top-level config folder that might list datasets: `config/`, `configs/`,
  `data/config/`, `.config/`.

If none of these exist, skip to step 4 with empty results.

### 2. Look for sample questions / example prompts (optional)

Use `grep_search` case-insensitively across README and docs. Try, in order, and
stop at the first section that yields concrete items:

- Headings matching:
  `^#{1,6}\s*(sample|example|suggested|try(ing)? these|starter|seed)\s*(questions?|prompts?|queries|inputs?)`
- Body markers: `\btry (asking|these)\b`, `\bexample prompts?\b`,
  `\bsample queries\b`, `\bstarter prompts?\b`.
- Config / data files: any `*.json`, `*.ya?ml`, or `*.md` under `data/`,
  `config/`, or `samples/` whose keys / fields match
  `questions?|prompts?|examples?|queries`.

Extract each item verbatim, preserving:

- The heading or group it appeared under (this is often the scenario name).
- The full text of the question / prompt.

If nothing matches, record `sample_questions: []` and continue — do NOT invent
questions.

### 3. Look for scenarios / use cases / datasets / modes (optional)

Scenarios go by many names. Search case-insensitively for any of these signals:

- Headings mentioning `scenarios?`, `use ?cases?`, `datasets?`, `demos?`,
  `modes?`, `personas?`, `sample (packs?|scenarios?)`.
- Config keys named `scenarios`, `usecases`, `use_cases`, `datasets`, `demos`,
  `modes`, `presets`, `packs`.
- Folders named `*_usecase`, `*-usecase`, `*_scenario`, `*-scenario`,
  `*_dataset`, `*_demo`, or a `samples/*` / `examples/*` folder with more than
  one sibling.
- CLI / env references like `--scenario`, `SCENARIO=`, `DATASET=`, `DEMO=`.

For each candidate, capture (fields are optional):

- A display name (heading text, config `name`, or humanized folder name).
- An identifier (config key, folder name, or slug).
- A short description if one is nearby.
- Any sample questions from step 2 that appeared under the same heading.

Deduplicate by normalized display name.

### 4. Decide whether to ask the user

- **No scenarios found** — the app is single-purpose or the repo doesn't model
  scenarios. Continue silently; do NOT ask the user anything.
- **Exactly one scenario found** — assume it. Mention it in one line
  (`Detected scenario: <name>`) and continue without asking.
- **More than one scenario found** — ASK the user which scenario is currently
  loaded in the app at the URL they provided. Present the list as short
  numbered options with the one-line description (if any). Wait for their
  answer.

Do NOT try to infer the scenario from the URL, hostname, or path. If the user
says "I don't know" or "any", tell them to check the app's landing / home /
setup screen and reply again; do not silently pick one.

### 5. Hand off to the planner

Return a compact summary the calling agent will use for planning. Every field
is optional — omit or leave empty when nothing was found:

```yaml
scenario:
  name: <display name, or null>
  id: <slug/key/folder, or null>
  description: <short description, or null>
sample_questions:
  - <verbatim item 1>
  - <verbatim item 2>
sources:
  - <path/to/README.md>
  - <path/to/other-doc-or-config>
notes: <optional one-liner, e.g. "No sample questions found in repo">
```

The planner SHOULD:

- Seed at least one test case per `sample_questions` entry, using the text
  verbatim, when the app has a chat / search / query surface.
- Scope any data-specific assertions (labels, categories, KPI names) to the
  chosen `scenario` when one was selected.
- Fall back to UI-discovered inputs when `sample_questions` is empty.

## Guardrails

- Do NOT invent sample questions or scenario names. Only report what the repo
  actually contains.
- Do NOT hardcode assumptions about any specific repo's file layout.
- Do NOT pick a scenario based on the URL, hostname, or slug — ask when more
  than one is possible.
- Do NOT call `planner_setup_page` or any `browser_*` tool from this skill.
  This skill is repo-side only.
- Do NOT block planning when the repo has no sample questions and no
  scenarios — return empty results and let the planner drive off the live UI.
