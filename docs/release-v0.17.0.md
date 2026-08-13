# Trade Nothing v0.17.0 — Single-Writer Research Kernel

Date: 2026-08-12

## Why this release exists

v0.16 fixed important retrieval and runtime failures, but the active method still distributed
meaning across too many objects and roles. A run could satisfy each local contract while losing a
current material fact, presenting self-critique as independent challenge, or failing to connect an
industry thesis to the security the market was actually trading.

v0.17 replaces that architecture rather than layering another state machine on it.

## New active kernel

The active method persists only TaskSpec, EvidenceStore, DecisionSnapshot and RunLedger. One Value
Lead writes the full Snapshot; an optional isolated Challenger returns a bounded ChallengePacket;
deterministic code validates and a pure renderer formats.

Research is ActionIntent-driven. Each loop must name the Snapshot field it can change, current
uncertainty, needed evidence, expected decision delta, stop condition and cost bound. The 0–10 budget
is a ceiling and additional loops require explicit authorization. A research loop is accepted only
when it adds a new observation and changes the named target field.

## Product-critical repairs

- Listed-company research must enumerate the official disclosure index over the longer of the
  latest periodic-report window and 120 days, retain a count-matched
  title/URL/date/disposition manifest, bind relevant documents to evidence, and enter through a host
  acquisition boundary.
- Every HIGH item must be visible as a material change, a gap or a reasoned non-material disposition.
- Snapshot replacement is atomic and preserves every TaskSpec question.
- Priority securities must bind value-transfer paths, same-horizon market views, separate economic-
  exposure evidence and market evidence. Both sets bind the same canonical security identity and
  cannot reuse one EvidenceItem for both roles.
- A priority security discovered from an industry/event question automatically inherits every
  listed-company reality obligation; thematic coverage can no longer bypass company disclosures.
- The active installed bundle retains bounded Tushare, BaoStock, AKShare/Tencent and CSV market
  observations plus deterministic market-snapshot calculation; provider output never creates a
  recommendation by itself.
- Receipt-bound market snapshots convert directly to canonical security-bound research input and
  may be appended between Lead calls without writing a conclusion or consuming budget.
- Challenge resolution binds the exact original ChallengePacket hash and cannot drift its targets
  or evidence.
- Manual receipt labels cannot self-attest Challenger independence. Only a registered successful
  host process (or controlled fixture) can create independent-challenge authority.
- TaskSpec, EvidenceStore and DecisionSnapshot hashes are revalidated before resume.
- Runtime failures clear the pending dispatch, stop once and never auto-retry.
- Registered state now lives under one neutral, run-scoped `research-runs/RUN-.../state.json`
  location rather than an old engine-specific state tree.

## Clean installation boundary

The installed Skill and method identity now use an explicit allowlist. The complete historical crux,
Judge, Agenda, CandidateMap, opportunity, report-synthesis and downstream lifecycle system remains
recoverable from the committed v0.16 baseline; selected source archaeology may remain in the current
tree, but none is installed into Agent copies.
Adding a file to the repository no longer grants it active semantic authority.

## Verification added

New tests cover the four-object core, atomic packet rejection, dispatch/payload hash binding,
idempotent dispatch, zero-budget authorization, source-window truth, evidence URL binding,
industry/market candidate binding, exact challenge provenance, state tampering, pure reporting,
host failure without retry, and a frozen three-event capital/control regression where omitting any
HIGH fact blocks delivery.

## Calibration boundary

This release is `UNBENCHMARKED_METHOD_CHANGE`. Deterministic tests prove the architecture behaves as
specified; they do not prove better investment judgment or Alpha.

Promotion requires blind same-model, same-as-of, comparable-budget forward tests with zero frozen
P0 omissions, no false independent challenge, no semantic contradiction, decision usefulness above
baseline on at least four of five diverse cases, and cost no greater than 1.5 times baseline.

## Historical compatibility

Tagged releases and historical source retain their original version labels. v0.10–v0.16 runs may be
inspected as historical artifacts but cannot be resumed as current v0.17 truth when method identity
differs.
