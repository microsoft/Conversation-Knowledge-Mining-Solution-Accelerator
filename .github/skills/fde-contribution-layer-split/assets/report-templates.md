# Report Templates

Read-on-demand output templates for `fde-contribution-layer-split`. The run must
emit all three sections below, in this order, after the split is staged.

## 1. Summary Report

Report every part of the contribution, even ones skipped as matches. The split
is exhaustive and mutually exclusive: every file/component under the resolved
solution path appears in exactly one row — a staged destination (new or delta),
matched-ignored, or an explicit **Unclassified** / **Out of scope** row. Never
omit a file.

| Part | Classified Layer | Staged Destination | Outcome | Notes |
|---|---|---|---|---|
| Example: Foundry + AKS baseline | Stable Core | — | Matched — ignored | Same service set as existing `stable-cores/ms-iq`; not staged |
| Example: alerting agent pattern | Technical Pattern | `workspace/<name>-split/technical-patterns/realtime-alerts` | Staged — delta | Adds a new notification channel extension point vs. existing `technical-patterns/realtime-alerts`; needs human review/merge |
| Example: refinery sensor dataset | Industry Scenario | `workspace/<name>-split/industry-scenarios/energy/welloil-alarms` | Staged — new | No prior scenario pack covered this dataset shape |
| Example: unrelated top-level `.git` metadata | — | — | Out of scope | Not part of the solution; excluded from the split |

## 2. Per-Part Review Detail (required)

The Summary Report table is a scannable index; it is **not** enough on its own to
approve a promotion. Immediately after it, emit one entry per **in-scope** part
(every `Matched`, `Delta`, and `New` row — omit `Out of scope`, list
`Unclassified` with whatever is known). Each entry must let a reviewer judge the
part **without** opening the source contribution or running another agent:

* **New** — the **file inventory** being added: the staged folder tree (files,
  not just the folder name) with a one-line purpose per significant file/asset,
  and the canonical live destination path.
* **Delta** — the **exact live target** (`stable-cores/<name>/…`,
  `technical-patterns/<name>/…`, or `industry-scenarios/<vertical>/<name>/…`
  file[s]) and the **concrete change**: a per-file diff summary or the
  added/changed hunks (from a read-only `git diff --no-index <live-file>
  <staged-file>`), plus a one-line rationale for why the delta is real (new
  integration / extension point / dataset / eval). Make clear it is a surgical
  addition, not a wholesale rewrite of the shared live file.
* **Matched** — the specific **live equivalent it maps to** (path) and *why*
  (same service set / same pattern shape / same scenario intent), so the
  reviewer can confirm it is safe to skip.

Format each entry as a short block:

```text
### <part name> — <Layer> — <Outcome>
- Staged at:   <staged path>            (New/Delta only)
- Live target: <live path>              (Delta = target file; New = destination; Matched = matched live path)
- Evidence:
    New   -> file tree + per-file purpose
    Delta -> diff summary / hunks + why it is a real delta
    Matched -> why this equals the live equivalent
```

Keep it evidence-first and concise — no narration beyond what a reviewer needs to
approve or reject that specific part.

## 3. Delta & Coverage Summary

Always produce a quantitative roll-up (computed directly from the per-part
outcomes, not estimated) so the human sees how much of the contribution is
genuinely new versus already covered.

**Headline metric — "% New or Delta"**: of in-scope parts (classified into one of
the three layers), the share staged as new or delta.

* Denominator = `Matched` + `Delta` + `New`. **Exclude** `Unclassified` and
  `Out of scope` (report their counts separately).
* `% New or Delta = (New + Delta) / (Matched + Delta + New) × 100`, rounded to
  the nearest percent.
* Report per layer and an overall row; show `—` for a layer with zero in-scope
  parts.

| Layer | In-scope parts | Matched (existing) | Delta | New | % New or Delta |
|---|---|---|---|---|---|
| Stable Core | … | … | … | … | …% |
| Technical Pattern | … | … | … | … | …% |
| Industry Scenario | … | … | … | … | …% |
| **Overall** | … | … | … | … | **…%** |

Below the table, add one line for anything excluded: `Excluded from %: N
unclassified, M out of scope`. State the overall `% New or Delta` in plain words
as the headline (e.g. "68% of this contribution is new or delta versus the live
layers; 32% already exists").
