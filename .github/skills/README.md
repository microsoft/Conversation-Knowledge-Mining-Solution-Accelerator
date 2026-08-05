# Agent Skills

This folder contains Copilot Agent Skills for repeatable project workflows.

## Available Skills

- `/use-case-update-guardrails` - Use when changing a project use case, migrating datasets, converting industry terminology, removing original-solution features, or checking deployment completeness across data, agents, UI/API, Fabric, Foundry, Copilot Studio, infra, docs, tests, and CI/CD.
- `/fde-contribution-layer-split` - Use when a contributed solution is provided (typically staged under `001-wip-repo-structure/workspace/`, but any resolved path is supported), to classify its parts across the stable-core, technical-pattern, and industry-scenario layers, check each part against existing layer content, and stage the split as three separate folders inside `workspace/` for human review — never writes directly to the live layer folders.

Skills in this folder are intended to guide repeatable workflows. Companion instructions may also exist under `.github/instructions/` for lighter automatic guardrails during ordinary edits.
