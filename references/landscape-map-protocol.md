# Landscape Map Protocol

Use this protocol whenever `research_intent` is `OPPORTUNITY_DISCOVERY` or `HYBRID`, including a
single-company or single-asset task. Question type alone does not decide whether opportunity
discovery runs. A pure `THESIS_CHALLENGE` may omit the map. The map expands the causal search
surface before the research roles see entity names. It is a hypothesis garden, not evidence,
candidate ranking, or a claim that every industry has seven investable paths.

## Framer contract

Return `hypothesis_garden.wild_hypotheses` with 5–7 paths. Across the map, include all five
archetypes:

- `DIRECT_CAPTURE`: the actor paid directly by incremental demand;
- `BOTTLENECK_OWNER`: the scarce capacity, right, permit, network, or process owner;
- `ENABLER_OR_INPUT`: an upstream input without which delivery cannot scale;
- `SUBSTITUTE_OR_AVOIDANCE`: a workaround that captures value when the presumed path fails;
- `ADVERSE_EXPOSURE`: an asset whose economics deteriorate because of the same causal change.

Every Framer path must include unique local `hypothesis_id`, `path_id`, `linked_crux_id`, `hypothesis`,
`hypothesis_status=HYPOTHESIS_ONLY`, `surprise_if_true`, symmetric `scenario_paths`, a 3–6 node
`value_transfer_chain`, `economic_capture_test`, `pricing_question`,
`cheap_discriminating_test`, 1–3 `proxy_plan` routes, `falsifier`, and exactly two distinct
`search_queries`. Paths must be entity-agnostic. “Company X benefits” is an output candidate, not
a valid starting map.

On initialization the deterministic exploration ledger assigns the immutable, content-addressed
persisted `WH-...` ID and preserves the Framer ID as lineage alias. Subsequent proxy trails, report
traces, and optional seed `origin_hypothesis_id` use the stored persisted ID, not a guessed hash.

`proxy_plan` names possible observations and bounded routes; it is not a `ProxyTrail`. Only a
research role that actually encounters an observation may emit a top-level `proxy_trails` item.
This distinction keeps every Framer path at `HYPOTHESIS_ONLY` instead of falsely initializing it as
`TRACED`.

The garden should be genuinely plural, not seven phrasings of the same consensus chain. At least
one path must ask where value migrates if the named thesis fails, one must inspect an indirect
physical or documentary proxy, and one must describe adverse exposure. A bold path is welcome
because it remains `HYPOTHESIS_ONLY`; rhetorical novelty never satisfies an evidence gate.

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

Each assigned role may additionally emit `hypothesis_sparks` and `proxy_trails`. These do not alter
the finding state. If a search reveals only an indirect clue, return `UNKNOWN` for the formal
finding, preserve the actual observation as `TRACED`, and specify the cheapest next test. A proxy trail
may propose a later bounded query; it does not expand the current round's search allowance or prove
that a source exists.

## State aggregation

- `UNPROBED`: one or both required roles have not returned an accepted finding;
- `SUPPORTED`: both roles probed, at least one supports, and neither rejects;
- `REJECTED`: both roles probed, at least one rejects, and neither supports;
- `UNKNOWN`: both roles probed but results conflict or neither resolves the path.

Any `UNPROBED` path blocks opportunity-run convergence, formal reporting, and an `EDGE_FOUND`
claim. `UNKNOWN` is completed coverage, not positive evidence. It must remain visible in the report.
Neither `REJECTED` nor `UNKNOWN` deletes its underlying wild hypothesis; the exploration ledger
retains the path, counter-explanation, trace, and stop condition without treating it as a candidate.

For `UNIVERSE_SEARCH`, completed coverage is the root stopping unit. After two consecutive rounds
with no new seed or seed-evidence growth and the normal crux/source dry gates, the engine may close
directionally mixed global cruxes as `MONITORABLE`. This does not promote any seed, produce a
universe direction, or establish an edge. Those decisions remain candidate-local.

## Candidate binding

Every OpportunitySeed emitted in a mapped run must include `landscape_path_id`. The engine rejects
missing or unknown path IDs and any seed whose `origin_crux` differs from the path's
`linked_crux_id`. A seed bound to a path that is not `SUPPORTED` remains an evidence-backed lead
and cannot become `READY_FOR_SCREENING`. Never combine evidence across paths to repair that state.
An entity mentioned only in a spark or proxy trail is not a bound seed and must stay out of candidate
counts until a separately admitted OpportunitySeed satisfies the normal citation rule.

## Report contract

Expose the chain in this order:

`wild hypothesis -> proxy trail -> assigned roles/rounds -> accepted findings -> aggregate path
state -> separately admitted bound seeds`

Show counts for planned, unprobed, supported, rejected, and unknown paths. Candidate cards must
display both `landscape_path_id` and `origin_crux`; omitting either destroys auditability. A
separate insight card may show the hypothesis, observation/inference boundary, best alternative
explanation, and next test, but must render `HYPOTHESIS_ONLY` before the narrative when applicable.
