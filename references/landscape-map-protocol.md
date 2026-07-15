# Landscape Map Protocol

Use this protocol only for opportunity-oriented frames: `UNIVERSE_SEARCH`, `COMPARATIVE`, or any
frame containing an `OPPORTUNITY_PATH` crux. The map expands the causal search surface before the
research roles see entity names. It is a hypothesis ledger, not evidence, candidate ranking, or a
claim that every industry has seven investable paths.

## Framer contract

Return 5–7 paths. Across the map, include all five archetypes:

- `DIRECT_CAPTURE`: the actor paid directly by incremental demand;
- `BOTTLENECK_OWNER`: the scarce capacity, right, permit, network, or process owner;
- `ENABLER_OR_INPUT`: an upstream input without which delivery cannot scale;
- `SUBSTITUTE_OR_AVOIDANCE`: a workaround that captures value when the presumed path fails;
- `ADVERSE_EXPOSURE`: an asset whose economics deteriorate because of the same causal change.

Every path must include `path_id`, `linked_crux_id`, `hypothesis`,
`hypothesis_status=HYPOTHESIS`, a 3–6 node `value_transfer_chain`, `economic_capture_test`,
`pricing_question`, `falsifier`, and exactly two distinct `search_queries`. Paths must be
entity-agnostic. “Company X benefits” is an output candidate, not a valid starting map.

## Dispatch and evidence contract

The engine sorts paths by `path_id`. Each round, it assigns at most two role-unprobed paths to the
Detective and at most two to the Inquisitor. Both roles must eventually probe every path. Each role
returns exactly one `landscape_findings` item per assignment:

```json
{
  "path_id": "L1",
  "linked_crux_id": "C1",
  "state": "SUPPORTED | REJECTED | UNKNOWN",
  "rationale": "bounded conclusion",
  "evidence": [{"claim": "...", "number": null, "source": "...", "url": "...", "date": "..."}]
}
```

`SUPPORTED` and `REJECTED` require an exact citation object already present in the same role's,
same-round, same-crux structured evidence. `UNKNOWN` may have no evidence. The engine rejects
unassigned paths, changed crux links, duplicated findings, invented citations, and findings beyond
the two-path role budget.

## State aggregation

- `UNPROBED`: one or both required roles have not returned an accepted finding;
- `SUPPORTED`: both roles probed, at least one supports, and neither rejects;
- `REJECTED`: both roles probed, at least one rejects, and neither supports;
- `UNKNOWN`: both roles probed but results conflict or neither resolves the path.

Any `UNPROBED` path blocks opportunity-run convergence, formal reporting, and an `EDGE_FOUND`
claim. `UNKNOWN` is completed coverage, not positive evidence. It must remain visible in the report.

For `UNIVERSE_SEARCH`, completed coverage is the root stopping unit. After two consecutive rounds
with no new seed or seed-evidence growth and the normal crux/source dry gates, the engine may close
directionally mixed global cruxes as `MONITORABLE`. This does not promote any seed, produce a
universe direction, or establish an edge. Those decisions remain candidate-local.

## Candidate binding

Every OpportunitySeed emitted in a mapped run must include `landscape_path_id`. The engine rejects
missing or unknown path IDs and any seed whose `origin_crux` differs from the path's
`linked_crux_id`. A seed bound to a path that is not `SUPPORTED` remains an evidence-backed lead
and cannot become `READY_FOR_SCREENING`. Never combine evidence across paths to repair that state.

## Report contract

Expose the chain in this order:

`planned path -> assigned roles/rounds -> accepted findings -> aggregate path state -> bound seeds`

Show counts for planned, unprobed, supported, rejected, and unknown paths. Candidate cards must
display both `landscape_path_id` and `origin_crux`; omitting either destroys auditability.
