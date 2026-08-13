---
name: trade-nothing
description: >
  Value-first investment research for standard Q&A and -deepthink2. Use for
  companies, events, industries, themes, A-shares, commercial space, AI chains,
  photovoltaics, and similar questions requiring current material facts,
  industry-to-market mapping, concrete securities, market boundaries, optional
  bounded Challenger review with explicit provenance, and an evidence-labelled report. It ends at research;
  it does not own orders, positions, portfolios, publication, or handoff.
---

# Trade Nothing v0.18.0 — Harness-First Research

> 先找全会改写结论的当期事实，再解释产业如何进入市场；每个付费动作都必须带来可验证增量。

**Skill root:** `./`

## What the product must add

Produce more decision value than the same model researching unaided:

1. **Current truth** — identify material facts as of a named cutoff and replace stale premises;
2. **Decision gain** — show how those facts change causality, economics, market stage, carriers,
   alternatives, triggers and invalidations;
3. **Trust boundary** — keep source fact, single-source observation, inference, hypothesis and
   execution proof distinct.

Missing a load-bearing current fact found by a comparable baseline is product failure. Passing
tests, calling more roles, collecting more URLs or writing a longer report is not investment value.

Stop at an evidence-bounded Deep Research Report. Never create orders, positions, portfolios,
target prices, return promises, publication or downstream handoff without separate authorization.

## The kernel

Persist only four semantic objects:

- `TaskSpec`: question, as-of, exact 0–10 budget, entities, mandatory fact surfaces and questions;
- `EvidenceStore`: canonical EvidenceItems and auditable SourceChecks;
- `DecisionSnapshot`: the only user-facing conclusion;
- `RunLedger`: method identity, dispatch/payload lineage, real calls, budget, failures and inputs.

The Value Lead alone replaces `DecisionSnapshot`. Tools and host adapters append evidence; a real
Challenger returns only a bounded `ChallengePacket`; the renderer creates content-addressed,
verified user/audit views from the same Snapshot. Do not create a second thesis, Agenda, CandidateMap, lifecycle or
report conclusion.

The kernel has two clocks: a committed Snapshot remains valid against the evidence frontier at
which the Lead wrote it, while later host/Challenger appends become pending obligations for the next
Lead. Never repair a host append by editing the Snapshot or deleting appended evidence.

## One useful-action loop

```text
bounded WorkingSet -> one ActionIntent -> acquire/reconcile evidence
-> append evidence and execution truth -> replace DecisionSnapshot atomically
-> deterministic validation -> stop or compile the next WorkingSet
```

An ActionIntent names a likely target, uncertainty, evidence needed, expected decision delta, stop
condition and cost bound. It is a call-scoped declaration, not a prediction that one exact field
must change. The kernel requires an actual new EvidenceItem or SourceCheck in every research loop
and a real semantic Snapshot delta. Control intent to continue stays in the packet/ledger, not in
user-facing next-validation fields.

Budget is a ceiling, not a target: `0` synthesizes supplied evidence; `1` performs the first Current
Reality Scan; `2–10` funds only unresolved actions that can change the decision. A Challenger costs
one loop; Lead resolution does not add a search loop. Stop early when no executable action can
change the Snapshot. Never auto-retry timeout, quota, authentication, permission or invalid JSON.

## Current reality is the fact gate

Complete every TaskSpec fact surface. Each SourceCheck records its security identity when relevant,
bounded window, real query or provider endpoint, concrete checked URLs, outcome and limitation.
`NO_RESULT` requires a precise negative scope; `INSUFFICIENT` remains a hard gap. Every new
EvidenceItem must be bound by a same-input SourceCheck.

For listed companies, enumerate the official disclosure index over the longer of “since the latest
periodic report” and 120 days, capped by as-of. A complete manifest records every title, URL, date,
disposition and reason. Open every potentially material item. Loss, impairment, related-party
borrowing, equity incentives, pledges, unlocks, guarantees, financing, contracts, litigation and
control changes cannot be dismissed by a template title reason. `OPENED_RELEVANT` entries require
matching evidence. Model assertion alone cannot complete this gate: the manifest must enter through
a host input or a controlled fixture. An optional external CLI's output remains caller-reported and
must be reconciled into an explicit host input before it can satisfy this gate.

Inspect at least financial/audit/cash-flow reality; operations, customers, orders and milestones;
control, pledge, freeze and related parties; unlocks, holdings changes, buybacks and financing;
investment, disposal, litigation, regulation and listing risk. Do not substitute a few thematic
keyword searches for bounded index enumeration.

Every HIGH EvidenceItem must appear in `material_changes`, `open_material_gaps`, or a reasoned
`non_material_evidence_disposition`. Facts use `FACT`; one genuine source uses `SINGLE_SOURCE`;
reasoning uses `INFERENCE`; an unverified mechanism uses `HYPOTHESIS`.

A material-title EvidenceItem cannot be closed with “not important” prose. Its EvidenceItem first
needs at least two host-extracted `document_facts`: typed fact, locator, verbatim excerpt, controlled
event type/anchor and document SHA-256. The same hash must appear in the binding SourceCheck's
acquisition receipts as `docsha256:<hash>`. The Lead cannot author these facts. It then chooses exactly one outcome:
material change, open gap, or non-material disposition. The last names a decision dimension,
explains why the body facts do not change the decision and states a concrete reversal condition.
The kernel derives the event family from subject, event type and host anchor; the Lead does not submit
that internal ID and cannot merge unrelated events or count duplicate announcements as separate changes.

Every structured number uses typed `measures` with one registered metric, numeric value, compatible
unit/dimension, explicit `subject_id`, as-of, period and registered basis ID. The kernel owns the
canonical metric definition; an unregistered alias or prose basis fails closed. `number` must be
JSON `null`; never put an opaque string or dictionary there. Do not restate values in factual prose:
the deterministic formatter owns scale and display. Each EvidenceItem binds at most one security,
and every measure subject must equal one of that item's entities or its single security. Every
measure needs a concrete publisher URL and ISO date no later than as-of.

## Connect industry to market without collapsing them

Keep two paths visible:

```text
fact -> constraint change -> profit-pool shift -> company economic exposure
narrative/event -> marginal capital -> market carrier -> crowding/verification/divergence
```

Explain `EVENT_DAYS`, `TACTICAL_WEEKS`, `EARNINGS_QUARTERS` and `STRUCTURAL_YEARS` separately.
Never use one timeless stock rank.

Always distinguish an observed market carrier from a qualified research candidate.
`market_carriers_by_horizon` names what marginal capital is trading, why, the closest alternative
and switch condition; it is not a recommendation and may exist even when no setup qualifies.
The closest alternative is either `UNKNOWN` or one canonical `ticker@MIC` with its own
security-bound market evidence; free-text or borrowed evidence cannot create a comparison.

A `CONDITIONAL_PRIORITY` candidate needs canonical `ticker@MIC`, horizon, economic exposure, market
role, why now, closest alternative, switch condition, trigger, invalidation and price/crowding
boundary. It binds one value-transfer path, one same-horizon market view, role-qualified
security-bound `exposure_evidence_ids` and `market_evidence_ids`, and their union. One EvidenceItem
may carry multiple honest roles; do not duplicate an observation merely to satisfy topology. When
the Lead discovers a new
priority security, the kernel automatically creates all listed-company fact-surface obligations for
that security; industry-level coverage can no longer bypass company reality. `WATCH`,
`EXPLORE` and `NO_SETUP` are not recommendations. `WATCH` still requires a concrete security,
economic-exposure evidence, market-state evidence, why-now, trigger, invalidation and crowding
boundary. `NO_SETUP` is an empty sentinel, never a named alternative. Negative calls such as `AVOID` or
`SHORT` are outside this research contract and cannot be smuggled in as candidate stances.

## Challenge and execution truth

Lead self-countercase and Challenger output are different. Request a Challenger only for named,
load-bearing claims that can change the Snapshot. It receives only those claims and relevant
evidence, cannot write the Snapshot, and cannot spawn another role.

In Codex, use one native child agent as the default Challenger. The parent supplies the bounded
prompt returned by `research_loop.py`; the child returns only one ChallengePacket; the parent
records child and parent IDs as `HARNESS_SUBAGENT / HARNESS_REPORTED / SEPARATE_CONTEXT_REPORTED`.
This is a caller-reported host provenance record; the parent ID must
equal the latest accepted Lead agent. It does not itself prove context separation, a different
model or cryptographic process attestation. An optional external process is recorded honestly as
`HOST_PROCESS / PROCESS_REPORTED / PROCESS_CONTEXT_REPORTED`; this binds the caller's process fields
and payload but is not an unforgeable host attestation. A manual parent receipt remains
`SELF_DECLARED / UNVERIFIED`. Never collapse these into one “verified” label. The Lead resolves
real attacks as `ACCEPTED`, `PARTIAL`, `REJECTED` or `UNRESOLVED`.

The repository deliberately exposes no API that stamps an arbitrary process dictionary as verified.
A future strong process proof must be minted by an application-side host that owns spawn, wait,
exit status and payload capture; until then, the CLI adapter remains a weak, explicit provenance
class rather than a false trust boundary.

## How to run

For standard Q&A, answer directly with current sources and a named as-of; do not register a deep run.

For `-deepthink2`, honor the exact budget, create explicit entities/questions in TaskSpec, and start
a new current-method run. A generic topic-only deep run is rejected. In Codex, start with
`--execution-mode HARNESS_ORCHESTRATED`, follow each returned WorkingSet, and use native tools for
Lead research. When `call_mode=CHALLENGER`, spawn exactly one native child agent with the returned
prompt, wait for its JSON, create a harness-reported receipt, submit it, then let the parent Lead
resolve. Do not invoke Claude CLI from inside Codex.

`research_host_runner.py` is an optional cross-environment/cross-model adapter only when a user
explicitly chooses it. Claude authentication or CLI permission failure must never block the native
Codex path, and the adapter cannot satisfy host-only official-index/body-extraction gates by itself.
Exact packet, receipt, resume and host-ingest commands are in
[references/research-loop-contract.md](references/research-loop-contract.md).

Use host data rather than model-reported prices. The bounded path is acquisition
(`free_market_observations.py`) -> frozen metrics (`market_snapshot_adapter.py`) -> canonical research
input (`research_market_input.py`) -> `research_loop.py ingest-host`. It binds market observations to
the discovered security without pretending price action proves economic exposure. See
[references/data-sources.md](references/data-sources.md). Never place `TUSHARE_TOKEN` in prompts,
state, receipts, reports or installed files.

## Delivery and acceptance

Render only `DecisionSnapshot`: judgment/boundary; Current Reality and gaps; question answers and
self-countercases; value paths and market by horizon; securities, alternatives, triggers and
invalidations; real challenges; next validation; Evidence Ledger and execution truth. A degraded
report is valid, but every material gap, unresolved challenge and runtime failure remains visible.
`report-user`, `report-audit` and `report-bundle` are content-addressed, read-only outputs whose
complete run, RunLedger, state, method, renderer and content hashes must pass bundle verification. Deliver
the user artifact exactly; never prepend a second conclusion or patch a unit in copied Markdown.

Run `make test` and `python3 scripts/version.py` after method changes. These prove implementation,
not effectiveness. Claim improvement only after blind, same-model, same-as-of, comparable-budget
forward tests show zero frozen P0 omissions, no false challenge provenance, no semantic
contradiction, usefulness above baseline on at least four of five diverse cases, and cost no greater
than `1.5x` baseline.

*One evidence truth. One decision truth. Every action earns its cost.*
