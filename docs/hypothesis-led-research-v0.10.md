# Hypothesis-Led Research v0.10

## Objective

Trade Nothing must be both imaginative and auditable:

- imagination decides which possible value-transfer paths deserve attention;
- evidence decides whether a path may be promoted, screened, or shown to a human;
- risk control decides what must be true before any later human action;
- none of the workflow heuristics is a probability, expected return, position size, or trade.

The change addresses two recurring failure modes:

1. a strong but over-conjunctive root thesis can suppress optional upside paths;
2. repeated zero-novelty rounds can consume the fuse without either resolving or retiring a
   sufficiently tested crux.

## Dual-track architecture

```text
research_intent
  ├─ formal evidence track
  │    crux -> accepted evidence -> root verdict
  │    OpportunitySeed -> CandidateScreen -> Claim Verification -> human review
  │
  └─ exploration track (no promotion or trading authority)
       Hypothesis Garden -> WildHypothesis -> ProxyTrail
       -> evidence-backed research lead
       -> explicit OpportunitySeed admission gate
```

The tracks are deliberately asymmetric. A bold idea may enter the exploration ledger without a
citation. It cannot enter CandidateScreen, alter the root verdict, become a Thesis, or create a
trade until it independently satisfies the existing evidence and promotion contracts.

## Research intent

The Framer emits one explicit intent:

- `THESIS_CHALLENGE`: test a bounded claim; an exploration ledger is optional.
- `OPPORTUNITY_DISCOVERY`: finding non-consensus value-transfer paths is a primary objective.
- `HYBRID`: challenge the named thesis and deliberately search for adjacent or substitute paths.

Legacy frames without `research_intent` remain readable. The runtime infers `HYBRID` only when the
frame already contains an opportunity path or Landscape Map; otherwise it treats the frame as
`THESIS_CHALLENGE`. New framing prompts must emit the field explicitly.

## WildHypothesis contract

A hypothesis is a structured speculation, not a weakly sourced claim. It records:

- immutable `hypothesis_id` plus merged provenance (`source_agents`) retaining
  every contributing `FRAMER`, `DETECTIVE`, or `INQUISITOR` role;
- related crux and optional Landscape path;
- the non-consensus proposition and a 3–6 node causal chain;
- the upside or adverse value-transfer mechanism;
- why consensus may miss it;
- observable proxy plan and alternative explanation;
- catalyst/checkpoint, ISO expiry after the frame as-of date, and falsifier;
- optional explicit upside/downside scenario payoffs in relative risk units.

Allowed states are:

- `HYPOTHESIS_ONLY`: admitted as a testable idea, with no accepted proxy;
- `TRACED`: at least one accepted proxy observation exists;
- `EVIDENCE_BACKED`: the exploration claim has sufficient trace evidence to justify drafting a
  separate OpportunitySeed, but it is still not an OpportunitySeed and has no promotion rights.

Expiry and falsification remain explicit fields and audit observations rather than extra maturity
states in v0.10. A hypothesis that crosses its expiry or falsifier must be parked by the human
reviewer or superseded in a later, explicitly authorized run; the runtime does not silently delete
or promote it.

There is no direct transition from a hypothesis state to CandidateScreen. The only bridge is a new
OpportunitySeed that independently passes same-agent, same-round, same-crux citation admission.

## ProxyTrail contract

A ProxyTrail is a small observable clue that can support, contradict, or leave a hypothesis
ambiguous. Typical proxy types are:

- issuer wording or disclosure changes;
- customer/counterparty references;
- hiring and role design;
- procurement, capex, or equipment movement;
- patent, certification, or technical milestones;
- regulatory, permit, project, or grid records;
- channel/customer behavior;
- pricing, crowding, or reflexivity;
- other physically specified observations.

Every item records `direction`, observation, alternative explanation, and
concrete evidence when available. Source dates belong to the bound evidence
receipts rather than an unaudited top-level trail field. Uncited observations
remain provisional. Valid citations are de-duplicated by normalized publisher
URL plus claim and number.

## Exploration priority and asymmetric payoff

The runtime may rank active hypotheses to choose the next bounded research task. Priority is a
workflow heuristic based on such attributes as:

- a visible qualitative asymmetry declaration: upside shape, convexity,
  downside shape, time to a discriminating signal, and its stated basis;
- distance from consensus;
- observability and falsifiability;
- information gap and availability of a bounded causal proxy.

It is not a calibrated probability or expected return.
Qualitative asymmetry is not evidence. The queue may favor an explicitly
OUTSIZED/CONVEX or OPTION_LIKE path only after subtracting declared downside
friction, and may add one point for a NEAR discriminating signal. A substantive
cross-role conflict marks the field contested and contributes zero. This makes
upside-seeking visible without letting optimistic adjectives change formal
evidence, candidates, or sizing.

When both scenario payoffs are explicitly supplied as non-negative relative-risk magnitudes in the
same unit:

```text
break_even_success_threshold = downside / (upside + downside)
```

The result answers only: “what success rate would make these stated payoffs break even?” It does
not estimate the actual success rate. Missing, negative, non-numeric, or jointly zero inputs return
`UNKNOWN`; the runtime never invents scenario values.

## Dual report actions

Every user-facing report exposes two independent actions:

1. **Formal promotion action** — the existing deterministic action dictated by candidate maturity,
   including `STOP_NO_PROMOTABLE_CANDIDATE`.
2. **Exploration action** — one bounded hypothesis/proxy task such as checking a customer,
   procurement, certification, or pricing clue.

An exploration action cannot override a formal stop. A formal stop no longer hides valuable
unpromoted hypotheses.

The execution loop is `typed design -> plan -> explicit authorization ->
receipt`. Design binds the current target and state revision. Planning is
idempotent while open; an unapproved plan can be cancelled with a reason.
Authorization is caller-attested unless a host separately binds a real approval
event. Every normal execution is one exact query and at most three documents.
A pre-query runtime failure closes no evidence route. A post-authorization
state change stores only a stale-result SHA-256, ingests no evidence, and
requires a fresh attempt with no automatic retry.

All role, scenario, and authorized evidence is bounded by the frozen as-of.
Month-only evidence is treated as ending on the last day of that month, so a
same-month citation cannot leak past a day-precise cutoff.

## Evidence-exhaustion convergence

A zero Judge signal never changes debate support. It may still carry new, role-backed citations;
those citations are stored and reset the dry counter without moving the score.

An open crux may become `MONITORABLE` through evidence exhaustion only when all are true:

- both isolated research roles actually probed it in the dry rounds;
- the crux already has the minimum valid source anchors;
- it is not newly introduced and has had sufficient prior evidence-bearing contest;
- consecutive bilateral probes add no new valid evidence;
- no new crux or other novelty signal resets the dry condition.

Never-probed, one-sided, source-thin, or newly introduced cruxes remain fail-closed. `MONITORABLE`
means “bounded research is exhausted; watch the defined event,” not true, false, or 50% likely.

## Evaluation

The new method must be evaluated separately from alpha:

- valid non-consensus path recall in a frozen corpus;
- proxy-trail precision and alternative-explanation coverage;
- hypothesis-to-evidence-backed-lead conversion;
- false-opportunity and maturity-misread counts;
- time/tokens/searches per effective lead;
- report comprehension of formal versus exploratory states.

Historical benchmark artifacts remain immutable. Until a new blind comparison is completed,
v0.10 is an implemented but not yet discovery-calibrated method change.

## Acceptance boundaries

- Historical run state and reports are not rewritten.
- No automatic retry, resume, CandidateScreen, Thesis, Decision, order, or position is created.
- Hypothesis and proxy state cannot affect root crux scores.
- An evidence-backed hypothesis is still non-promotable.
- Report rendering stays deterministic and raw role payloads remain excluded.
- Source-sync verification must pass after canonical and installed copies are updated.
