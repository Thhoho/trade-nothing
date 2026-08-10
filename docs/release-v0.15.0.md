# Trade Nothing v0.15.0

v0.15.0 is a product-shape reset: a research topic and its Research Agenda are the primary object,
opportunity discovery is a core task, verification is selective, and the skill ends at a Deep
Research Report with conditional recommendations.

## What changed

- Added a lightweight CandidateMap for concrete companies, securities, assets and technologies.
  Listed equities require a ticker. CandidateMap has no promotion lifecycle or expected-return
  score.
- Added explicit market roles: `EVENT_BETA`, `ECONOMIC_CAPTURE`, `BOTTLENECK`, `SECOND_ORDER`,
  `SUBSTITUTE`, `FAILURE_HEDGE` and `WATCH_ONLY`.
- Separated `EVENT_SETUP` from `ECONOMIC_SETUP`; the same security may have different usefulness
  across the two paths.
- Preserved weak but concrete leads under `FACT`, `SINGLE_SOURCE`, `INFERENCE` and `HYPOTHESIS`
  labels instead of requiring high-confidence evidence at discovery time.
- Removed automatic CandidateScreen and candidate-gap dispatch from convergence and reporting.
  Those legacy verification tools remain available only through explicit commands.
- Added a deterministic Research Agenda with `OPEN`, `PARTIAL`, `ANSWERED`, and `DISPUTED`
  question states, answer variants, bound evidence, strongest challenges, missing information,
  new blind spots, and newly created research questions.
- Made `# Deep Research Report` the default report. It leads with conclusions and conditional
  recommendations, then shows Agenda progress, market mechanics, named carriers, blind spots,
  scenarios, triggers, invalidations, price/crowding, evidence boundaries and next tests.
- Made mechanism hypotheses optional. Opportunity discovery no longer requires a hypothesis
  garden; a complete Landscape remains available only when explicitly declared.
- Made the legacy synthesis packet opt-in. Historical Decision Brief, Facts Box, Candidate Cards
  and audit views remain explicit compatibility surfaces.
- Disabled automatic promotion of mature hypothesis prose into an OpportunitySeed and enforced a
  ticker for listed-equity seeds.
- Added an explicit host-owned market snapshot plane. Adapter output now binds the normalized
  snapshot payload, ingestion requires an upstream receipt plus relative-strength/activity evidence,
  and model-authored snapshots cannot grant recommendation authority.
- Tightened conditional priorities: hypothesis-only value paths and single-role phase readings fail
  closed; phase consensus requires both research roles.
- Replaced 30KB role-manual injection with a compact shared runtime contract and role overlay while
  retaining the full manuals as human reference.

## Boundary

The skill stops at a deep research report and conditional advice. It does not build or manage Thesis, Decision,
order, position, portfolio, publication, notification, or cross-product handoff workflows.

## Validation

Deterministic replays cover:

- a Zhuque-3 event path with separate event-beta and economic-capture carriers;
- Agenda answer updates, citation binding, disputes, blind spots and question reprioritization;
- a fully covered theme with `NO_USABLE_SETUP`;
- incomplete coverage that must stay `EXPLORE`;
- rejection of an abstract listed-equity mapping without a ticker;
- same-ticker merging without manufacturing a confidence or return score;
- no default CandidateScreen or gap-task side effect.
- rejection of valuation-only, tampered, conflicting, model-supplied and receipt-free market
  snapshots;
- no conditional priority from a hypothesis-only value path or single-role phase view.

These are engineering and product-contract tests, not evidence of opportunity recall, Alpha,
return, or risk-adjusted performance.

## Calibration status

The operational bundle remains `UNBENCHMARKED_METHOD_CHANGE`. The v0.14 closed-packet and
discovery suites are historical controls only; they do not validate v0.15 effectiveness. A new
blind replay and human usefulness benchmark is required before making effectiveness claims.

## Upgrade note

Archived state remains readable. Old frames without a Research Agenda receive a labelled derived
compatibility agenda; old OpportunitySeeds are projected into CandidateMap at report
time without rewriting history. Legacy screening and claim-verification commands remain explicit,
but no longer run from the default discovery path.
