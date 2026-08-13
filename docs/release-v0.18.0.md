# Trade Nothing v0.18.0 — Harness-First Research Kernel

v0.18 fixes the failures exposed by the same-model report comparison and the latest five-run audit.
It does not add another research state machine. It makes the existing four-object kernel usable
through the host that already runs it and closes places where execution or formatting could become
a second source of truth.

## Product outcome

Inside Codex, native tools and one native child agent are now the default execution path. The
portable Trade Nothing layer owns TaskSpec, EvidenceStore, DecisionSnapshot, RunLedger, packet
contracts and pure reporting. Codex orchestrates tool calls, child context, waiting and
cancellation; the portable kernel records caller-reported child identity without promoting it to
attestation. Claude Code and Antigravity process launchers remain explicit optional, one-request
adapters.

The product objective remains unchanged: under the same model, cutoff and comparable budget, the
Skill must recover more decision-changing current facts and produce a more useful decision than an
unassisted run. This release remains `UNBENCHMARKED_METHOD_CHANGE`; deterministic tests do not prove
that objective.

## P0 corrections

### Historical truth no longer changes retroactively

Each accepted Lead action records a `snapshot_frontier`. Persisted Snapshot validation replays the
EvidenceItems, SourceChecks and Challenges visible at that frontier. Later host or Challenger
appends create pending obligations for the next Lead rather than invalidating the old commit.
Evidence and execution histories are append-only, and a Snapshot change requires exactly one new
Lead action and accepted Lead receipt.

This removes the architectural pressure that previously caused host repair code to rewrite a
Snapshot or delete newly appended evidence.

### Numeric truth is typed and rendered once

Evidence `number` accepts JSON `null` only. Structured values use typed measures with a registered
metric, raw value, compatible unit/dimension, explicit subject, as-of, period and registered basis.
The kernel owns canonical definitions and the deterministic formatter owns scale; model-authored
unit-bearing numeric prose is rejected after Unicode/Markdown canonicalization instead of being
matched by value alone. One EvidenceItem cannot bridge two securities.
Host-input lineage hashes full normalized EvidenceItems and
SourceChecks, not just dedupe identifiers.

The regression case `2167.1641 CNY_BN` now renders as
`2.167万亿元（21671.64亿元）`, closing the observed ten-times unit error.

### One report truth

Reporting now emits content-addressed, read-only user and audit views from the same validated run
plus a verifier-bound bundle that binds both artifacts to run ID, state revision, TaskSpec,
EvidenceStore, DecisionSnapshot, complete RunLedger/research-run hashes, method identity and exact
renderer source. The delivery contract
forbids manual prepends, copied value corrections or a
second report-side conclusion.

### Execution provenance no longer overclaims

Requested orchestration and achieved provenance are separate. A native child Challenger records
`HARNESS_SUBAGENT / HARNESS_REPORTED`; an optional external process records
`HOST_PROCESS / PROCESS_REPORTED / PROCESS_CONTEXT_REPORTED`; a manual parent receipt remains
`SELF_DECLARED / UNVERIFIED`. A self-declared receipt cannot satisfy Challenger. Harness reporting
and external-process reporting record caller observations; neither is proof of separation, model
diversity or a cryptographic process boundary. The repository exposes no arbitrary record-stamping
API; strong process proof is deferred to an application host that owns spawn and result capture.

## P1 value corrections

- Official-index enumeration is no longer treated as materiality recall. Loss, impairment,
  related-party borrowing, incentives, pledges, unlocks, guarantees, financing, contracts,
  litigation and control-change titles require `OPENED_RELEVANT` plus bound evidence rather than
  template or generic reviewed dismissal.
- A marker event first requires host-extracted body facts with locators and a SourceCheck-bound
  document hash. The Lead then chooses exactly one outcome; event-family identity is derived rather
  than freely assigned, and duplicate notices render as one event.
- Evidence carries semantic roles. One observation may honestly support current reality, economic
  exposure and market state; the kernel no longer rewards duplicate evidence created to satisfy an
  artificial disjointness rule.
- `market_carriers_by_horizon` records what marginal capital is trading even when no security passes
  the recommendation gate. Qualified candidates remain a separate, stricter claim.
- A named closest alternative requires canonical security identity and its own market evidence;
  negative `AVOID`/`SHORT` calls are outside the candidate contract.
- Stable material-gap IDs replace runtime obligation IDs in user-facing Snapshot semantics.
- `continue_research` remains runtime intent and no longer contaminates the user's lowest-cost next
  validation.
- ActionIntent target is a routing hint. Acceptance requires a new observation and an actual
  semantic Snapshot delta, not a forced mutation of one predicted field.
- External CLI execution is recorded as caller-reported rather than promoted to a false strong proof
  through an adapter or plausible serialized ledger fields.

## Native Challenger flow

Start a Codex run with `HARNESS_ORCHESTRATED`. The parent performs Lead research with native tools.
When a bounded `CHALLENGER` dispatch appears, the parent sends that exact prompt to one native child
agent, records child and parent IDs in a harness-reported receipt, submits the ChallengePacket, and
then resolves it as Lead. A Claude CLI authentication or permission failure is not on this path.

## Validation

The deterministic suite covers:

- frontier-aware historical validation and pending obligations;
- destructive-transition rejection;
- typed measure normalization, unit scale and free-text numeric binding;
- material-title recall;
- market carrier without forced recommendation;
- native child Challenger acceptance and forged-label rejection;
- requested-versus-achieved execution reporting;
- pure user/audit report views and report-bundle artifacts;
- timeout, permission, invalid JSON, no-retry, install and method-identity boundaries.

## Historical compatibility

v0.18 uses v2 research run, EvidenceStore, DecisionSnapshot, RunLedger and WorkingSet schemas. Older
runs remain historical artifacts but are not resumed as current-method truth. v0.17 design notes and
the v0.16 baseline remain available for archaeology; retired role engines stay outside the active
method allowlist and installed Skill bundle.
