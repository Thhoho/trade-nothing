# Trade Nothing v0.16.0

## Why this release exists

A controlled comparison exposed a product-level failure: the multi-round Skill could preserve
excellent evidence and execution lineage yet miss a recent, load-bearing company event that the
same model found in a single-agent run. The formal process cost roughly three times as much while
producing a worse current economic conclusion.

v0.16 changes the optimization target from process completeness to **decision gain over a
same-model baseline**. It does not claim that the new method has already won that comparison.
Until a new blind run is complete, calibration remains `UNBENCHMARKED_METHOD_CHANGE` and all older
benchmark suites are historical controls.

## Architecture change

The default path is now:

```text
Primary Entities
  -> Current Reality Scan
  -> Material Change Gate
  -> Research Agenda
  -> Value Lead
  -> Targeted Challenge when needed
  -> Current Truth
  -> Industry-to-market map
  -> Deep Research Report
```

This is not a replacement state machine. `material_change_engine.py` is a small deterministic
register and delivery gate beside the existing Agenda. It owns subject coverage, material-change
lineage, open material leads, and current/superseded projection. The existing evidence kernel,
Agenda, Market Bridge, CandidateMap, temporal boundary, and execution receipts remain in place.

## User-visible changes

- Framer identifies 1–4 `primary_entities` before producing the Agenda.
- The first Lead call scans each subject's required current official fact surface before answering
  narrow questions.
- A HIGH lead already encountered cannot be buried in limitations. It must be verified, rejected,
  or displayed as a first-page `MATERIAL_FACT_GAP` blocker.
- Agenda-native execution is adaptive: Lead first, Challenger only for load-bearing claims, and
  Judge only for explicit legacy crux audit.
- Execution receipt v2 binds the exact `required_roles`; omitted roles are typed `SKIPPED` payloads
  and cannot smuggle unbound research into state.
- The Deep Research Report starts with Current Reality, material changes, known gaps, and the
  decision-ready boundary before process details.
- Role prompts now use task-local context. A Challenger receives only target claims, their current
  evidence, and relevant material-change state rather than a complete state dump.

## Product acceptance

The new product-value benchmark is separate from closed-packet reasoning calibration. It compares
the same model, prompt, as-of, tools, and declared budget, then gates on:

- weighted material-fact recall;
- decisive-claim precision;
- decision usefulness and comprehension;
- false-source and hypothesis-laundering counts;
- search, token, and wall-time cost.

The candidate method is blocked if any known material fact is omitted, material recall is below the
single-agent baseline, decision usefulness does not improve, any evidence-boundary safety count is
non-zero, or cost exceeds 1.5x before a measurable benefit is established. Assessments bind actual
report-file hashes and one blinded assessor; the scorer derives omissions from the hidden key and
rejects self-declared zeros or budget drift.

## Compatibility and limits

- Historical v0.15 runs remain readable as `HISTORICAL_REPLAY` after method identity changes.
- Legacy crux/Judge execution remains available only when explicitly requested.
- A clear Current Reality gate proves bounded coverage and absence of known blockers; it does not
  prove exhaustive internet recall, investment performance, or Alpha.
- Engineering tests validate contracts and fail-closed behavior only. The current method remains
  unproven until real-theme same-model comparison is completed.
