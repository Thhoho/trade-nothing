# OpportunitySeed Protocol

`OpportunitySeed` turns useful side findings from adversarial research into a
screening queue. It does not change the root-thesis verdict and is never a buy,
sell, return, target-price, or sizing recommendation.

## Two lanes: exploration is not promotion

The method keeps two ledgers with different truth standards:

1. **Exploration ledger** — `wild_hypotheses`, `hypothesis_sparks`, and `proxy_trails`. This is where
   bold conjectures, indirect clues, analogies, counter-mechanisms, and cheap next tests survive.
   Evidence may be absent. A new conjecture with no accepted observation remains
   `HYPOTHESIS_ONLY`; it is never silently dropped merely for being early.
2. **Promotion ledger** — admitted `OpportunitySeed` objects and their deterministic maturation,
   CandidateScreen, and claim-verification states. Every existing citation and human gate remains
   mandatory.

Exploration objects are not weak OpportunitySeeds. They do not count as candidates, evidence-backed
leads, source diversity, pricing anchors, convergence evidence, or promotion progress. A role may
later emit a *new, separately validated* OpportunitySeed inspired by a spark, but no engine or model
may mutate or relabel the original exploration object into a seed.

Use these exploration states:

`HYPOTHESIS_ONLY -> TRACED -> EVIDENCE_BACKED`.

- `HYPOTHESIS_ONLY`: conjecture plus falsifier or discriminating test; admissible evidence may be
  empty.
- `TRACED`: at least one accepted proxy observation exists. It may support, contradict, or leave
  the proposed mechanism ambiguous.
- `EVIDENCE_BACKED`: trace evidence is sufficient to justify drafting a *separate*
  OpportunitySeed. The hypothesis is still non-promotable and is not itself a seed.

Mechanism completeness, economic capture, instrument identity, and pricing are fields and blocker
conditions, not additional states. These labels are exploration maturity, not engine promotion
states. Even exploration `EVIDENCE_BACKED` must satisfy the independent Admission rule below before
an `OpportunitySeed` exists.

Introduced in v0.10 and retained in v0.11.0, expiry and falsifier are explicit audit fields, not
silently inferred maturity states. Crossing either boundary must stay visible for human review or
a later explicitly authorized run; the runtime does not delete, promote, or relabel the hypothesis
automatically.

Every new `hypothesis_spark` should carry `subject`, `origin_crux`, optional
`landscape_path_id`, `status=HYPOTHESIS_ONLY`, `hypothesis`, `why_nonconsensus`, a list-valued
`causal_chain`, `value_transfer`, `strongest_alternative_explanation`, `falsifier`, `catalyst`,
`cheap_discriminating_test`, and optional same-unit scenario `payoff`. The deterministic ledger
assigns its immutable `hypothesis_id`.

Every top-level `proxy_trail` should reference an existing `hypothesis_id` or repeat the exact
same-round `hypothesis` text, then carry `proxy`, `causal_link`,
`direction=SUPPORTS|CONTRADICTS|AMBIGUOUS`, `alternative_explanation`, `checkpoint`, and optional
`evidence`. It represents an observation actually encountered. A suggested query belongs in the
spark's cheap test or Framer `proxy_plan`; a query or publisher route alone is not a ProxyTrail and
does not advance maturity.

## Admission rule

A seed is admitted only when all of the following hold:

1. It names a concrete candidate and one allowed `relation_type`.
2. It points to an existing `origin_crux` and states a causal path. In a mapped run it also binds
   `landscape_path_id`, whose `linked_crux_id` must match `origin_crux`.
3. Optional `origin_hypothesis_id` is lineage only. When non-null, it must resolve to an existing
   exploration hypothesis whose `context.origin_crux` matches the seed's `origin_crux`. It grants
   no evidence, readiness, screening, or promotion credit.
4. At least one citation exactly matches structured evidence submitted by the
   same agent for the same crux in the same round.
5. The citation contains claim, source, date, and a concrete non-homepage URL.

The engine drops invented, homepage-only, cross-agent, and cross-crux evidence.
Each agent may submit at most three seeds per round.
It must preserve separately well-formed exploration objects even when they fail this seed rule.

## Schema

```json
{
  "candidate": "<company, asset, commodity, or technology>",
  "ticker": null,
  "asset_type": "LISTED_EQUITY|PRIVATE_COMPANY|COMMODITY|TECHNOLOGY|OTHER",
  "relation_type": "DIRECT_WINNER|SUBSTITUTE_WINNER|COMPETITOR_WINNER|BOTTLENECK_OWNER|INFRA_ASSET_OWNER|SECOND_ORDER|SHORT_CANDIDATE",
  "origin_crux": "C1",
  "landscape_path_id": "L1",
  "origin_hypothesis_id": "WH-... or null",
  "causal_path": "<crux outcome -> value transfer -> candidate exposure>",
  "economic_exposure": "<how the candidate captures or loses economics; blank if unknown>",
  "why_market_may_miss": "<specific pricing or attention gap; blank if unknown>",
  "pricing_anchor": {
    "as_of_date": "YYYY-MM-DD",
    "anchor_type": "ABSOLUTE_VALUATION|RELATIVE_VALUATION|EMBEDDED_EXPECTATION|CONTRACT_PRICE|CAPACITY_OR_EARNINGS|MARKET_PRICE",
    "metric": "<observable metric>",
    "current_value": "<current price, multiple, or embedded assumption>",
    "comparison_value": "<peer, historical, contract, or thesis-implied comparison>",
    "source": "<organization>",
    "source_url": "<must exactly match one same-round seed evidence URL>",
    "source_claim": "<what the source establishes>"
  },
  "catalyst": "<observable event; blank if unknown>",
  "catalyst_window": {
    "event": "<observable event>",
    "expected_by": "<YYYY-MM-DD>",
    "date_status": "REVIEW_CHECKPOINT|DATE_CLAIMED_UNVERIFIED"
  },
  "falsifier": "<observable fact that kills this candidate path; blank if unknown>",
  "evidence": [
    {
      "claim": "<exactly reuse a same-round structured evidence claim>",
      "number": null,
      "source": "<organization>",
      "url": "<specific URL>",
      "date": "<YYYY-MM-DD or YYYY-MM>",
      "source_tier": "primary|secondary"
    }
  ]
}
```

## Evidence maturity and screening eligibility

- `EVIDENCE_BACKED`: at least one agent-backed concrete citation.
- Evidence-ready path: at least two distinct source organizations, plus non-empty economic
  exposure, expectation gap, pricing anchor, catalyst, structured catalyst window, and falsifier.
  A narrative such as “the market underestimates this” is not a pricing anchor. Use an observable
  as-of valuation, embedded expectation, contract price, capacity/earnings assumption, or relative
  benchmark. The anchor URL must exactly match same-round, same-crux seed evidence. This is not
  yet screen eligibility. Read `references/pricing-gap-protocol.md` before emitting a structured
  pricing anchor.
- `READY_FOR_SCREENING`: the evidence-ready path also requires a contested and settled or
  monitorable origin crux with the minimum source count, a converged root thesis, and a structured
  catalyst date inside the root research horizon. In a mapped run, the bound Landscape path must
  also be `SUPPORTED`; `UNPROBED`, `REJECTED`, and `UNKNOWN` paths cannot become READY.

Independent seed sources are counted by final publisher domain, never by the agent-written
`source` label. Search/grounding redirect wrappers must be resolved to the final publisher URL;
otherwise the evidence and any pricing anchor bound to it are rejected.

Fail closed without deleting the lead:

- `BLOCKED_ORIGIN_CRUX`: the origin crux is untested, unsettled, or source-thin.
- `BLOCKED_ROOT_UNCONVERGED`: the root thesis has not passed convergence.
- `NEEDS_CATALYST_CHECK`: the catalyst date is missing or malformed.
- `OUT_OF_HORIZON_LEAD`: the catalyst is expired or outside the root horizon.

Failing any seed-admission or readiness condition does not authorize copying an exploratory
inference into formal evidence. Keep the spark and its next test visible in the exploration ledger,
with the exact maturity boundary that failed.

After root convergence, an `EVIDENCE_BACKED` seed may enter the bounded Candidate Maturation loop.
The planner converts its first deterministic blocker into a content-addressed `CandidateGapTask`;
new evidence is appended as supplements and never edits the original seed contract. Read
`references/candidate-maturation-protocol.md` before planning or submitting gap evidence.

`READY_FOR_SCREENING` means “eligible for the two-sided CandidateScreen,” not
“investable.” Run Candidate Analyst and Candidate Skeptic using
`references/candidate-screen-protocol.md`. Valuation, liquidity, governance,
crowding, and catalyst timing must pass that separate evidence gate.

An exploration action may spend a separately authorized bounded research budget on one proxy trail.
It is not a formal next action, a CandidateScreen dispatch, or a recommendation. It must specify the
question, source class, search/read cap, success condition, and stop condition before execution.

## Cross-system candidate state

Use only the deterministic projection emitted by `opportunity_engine.promotion_assessment()`:

`EVIDENCE_BACKED -> READY_FOR_SCREENING -> WATCHLIST | REJECTED | THESIS_CANDIDATE -> VERIFIED_FOR_HUMAN`

Only `VERIFIED_FOR_HUMAN` may be offered to a human for creation of a fresh DRAFT Thesis. It
requires a `THESIS_CANDIDATE` screen, verified screen isolation, snapshot-bound claim verification,
and a `DRAFT_REQUIRES_HUMAN` promotion packet. Human rationale cannot override a lower state.
`COMPLETED` gap evidence means only that one bounded seed blocker was addressed; it does not skip
CandidateScreen or any later gate.

## Entity de-duplication

Keep each `OpportunitySeed` as an independent evidence path. Do not combine citations across
different cruxes or relation types to manufacture readiness. Project paths sharing the same exact
ticker, or the same normalized name when no ticker exists, into one candidate entity for reports
and default screen dispatch. Screen at most one representative ready path per entity unless the
user explicitly requests a specific seed.

## Root-thesis independence

The declared question type and logic graph control root-thesis aggregation. Weakest-crux
rejection is valid only for necessary hinges in `CONJUNCTIVE` or `CAUSAL_CHAIN` questions;
it cannot negate one surviving alternative path or an entire universe search. A `NO_EDGE`
root verdict may coexist with valid substitute, competitor, bottleneck-owner, asset-owner,
second-order, or short-candidate seeds. The report must preserve both the root assessment and
the evidence-backed research leads. It may also preserve clearly labelled `HYPOTHESIS_ONLY`
discoveries without presenting them as opportunities. `NO_EDGE` never means `AVOID` or `SHORT`.
