# OpportunitySeed Protocol

`OpportunitySeed` turns useful side findings from adversarial research into a
screening queue. It does not change the root-thesis verdict and is never a buy,
sell, return, target-price, or sizing recommendation.

## Admission rule

A seed is admitted only when all of the following hold:

1. It names a concrete candidate and one allowed `relation_type`.
2. It points to an existing `origin_crux` and states a causal path.
3. At least one citation exactly matches structured evidence submitted by the
   same agent for the same crux in the same round.
4. The citation contains claim, source, date, and a concrete non-homepage URL.

The engine drops invented, homepage-only, cross-agent, and cross-crux evidence.
Each agent may submit at most three seeds per round.

## Schema

```json
{
  "candidate": "<company, asset, commodity, or technology>",
  "ticker": null,
  "asset_type": "LISTED_EQUITY|PRIVATE_COMPANY|COMMODITY|TECHNOLOGY|OTHER",
  "relation_type": "DIRECT_WINNER|SUBSTITUTE_WINNER|COMPETITOR_WINNER|BOTTLENECK_OWNER|INFRA_ASSET_OWNER|SECOND_ORDER|SHORT_CANDIDATE",
  "origin_crux": "C1",
  "causal_path": "<crux outcome -> value transfer -> candidate exposure>",
  "economic_exposure": "<how the candidate captures or loses economics; blank if unknown>",
  "why_market_may_miss": "<specific pricing or attention gap; blank if unknown>",
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
- Evidence-ready path: at least two distinct concrete source URLs, plus a
  non-empty economic exposure and falsifier. This is not yet screen eligibility.
- `READY_FOR_SCREENING`: the evidence-ready path also requires a contested and settled or
  monitorable origin crux with the minimum source count, a converged root thesis, and a structured
  catalyst date inside the root research horizon.

Fail closed without deleting the lead:

- `BLOCKED_ORIGIN_CRUX`: the origin crux is untested, unsettled, or source-thin.
- `BLOCKED_ROOT_UNCONVERGED`: the root thesis has not passed convergence.
- `NEEDS_CATALYST_CHECK`: the catalyst date is missing or malformed.
- `OUT_OF_HORIZON_LEAD`: the catalyst is expired or outside the root horizon.

`READY_FOR_SCREENING` means “eligible for the two-sided CandidateScreen,” not
“investable.” Run Candidate Analyst and Candidate Skeptic using
`references/candidate-screen-protocol.md`. Valuation, liquidity, governance,
crowding, and catalyst timing must pass that separate evidence gate.

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
the evidence-backed research leads. `NO_EDGE` never means `AVOID` or `SHORT`.
