# Opportunity Research Protocol

This protocol defines the boundary between an exploratory mechanism, a concrete market-map item,
and an evidence-backed OpportunitySeed. It ends at the Deep Research Report and has no authority over
Thesis, Decision, order, position, portfolio, publication workflow, or cross-product handoff.

## 1. Three distinct objects

### Hypothesis

A causal conjecture worth testing. It may be entity-agnostic and may have no citation. It must keep
its strongest alternative explanation, falsifier, catalyst or checkpoint, and cheapest next test.

States remain descriptive only:

`HYPOTHESIS_ONLY -> TRACED -> EVIDENCE_BACKED`

`EVIDENCE_BACKED` means the mechanism deserves concrete candidate research. It does not transform
the hypothesis into a candidate. Engines and models must never auto-promote, relabel, truncate, or
copy hypothesis prose into an OpportunitySeed.

### CandidateMapItem

A concrete company, security, asset, commodity, technology, or explicit statement that no listed
vehicle was found. It connects a hypothesis to the market without claiming verification.

Fields in the v0.15 CandidateMap implementation:

```json
{
  "candidate": "Concrete company or asset",
  "ticker": "required for LISTED_EQUITY",
  "asset_type": "LISTED_EQUITY|PRIVATE_COMPANY|COMMODITY|TECHNOLOGY|OTHER",
  "market_role": "EVENT_BETA|ECONOMIC_CAPTURE|BOTTLENECK|SECOND_ORDER|SUBSTITUTE|FAILURE_HEDGE|WATCH_ONLY",
  "setup_types": ["EVENT_SETUP", "ECONOMIC_SETUP"],
  "mechanism": "event -> value or attention transfer -> candidate",
  "economic_exposure": "how business economics are captured or UNKNOWN",
  "catalyst": "observable event or checkpoint",
  "invalidation": "observable fact that breaks the mapping",
  "price_or_expectation": "current price or embedded expectation, or UNKNOWN",
  "crowding_or_position": "known fact, labelled inference, or UNKNOWN",
  "strongest_alternative_explanation": "ordinary explanation for the same observation",
  "cheap_discriminating_test": "one bounded next check",
  "field_update_modes": {
    "mechanism": "REFINE|REPLACE|CHALLENGE",
    "price_or_expectation": "REFINE|REPLACE|CHALLENGE"
  },
  "evidence_boundary": "FACT|SINGLE_SOURCE|INFERENCE|HYPOTHESIS"
}
```

Text inequality is not evidence of contradiction. `REFINE` supplies a newer or more precise current
snapshot; `REPLACE` explicitly supersedes a wrong old value and resolves prior conflict;
`CHALLENGE` records a mutually exclusive unresolved claim. Only `CHALLENGE` blocks setup readiness.

A CandidateMapItem may appear in research-attention or conditional-setup comparisons. It is not a
buy/sell instruction and does not inherit evidence from its parent hypothesis.

### OpportunitySeed

A concrete candidate path that has at least one candidate-aligned citation and is worth focused
verification. It remains a research object, not a trade or downstream workflow state.

## 2. Seed admission

A seed is admitted only when:

1. `candidate` names a concrete entity or asset, not a proposition, industry mechanism, event, or
   “if/then” sentence;
2. `asset_type=LISTED_EQUITY` includes a non-empty ticker;
3. `relation_type` is one of the allowed value-transfer roles;
4. it binds an existing origin crux and, in mapped runs, a compatible Landscape path;
5. it states the candidate-specific causal path;
6. at least one citation exactly matches structured evidence from the same role, crux, and round;
7. every admitted citation contains claim, source, date, and a concrete URL.

An `origin_hypothesis_id` is lineage only. It never supplies candidate identity, evidence, price,
catalyst, or readiness. If a mature hypothesis suggests several companies, each company must be
submitted as a separate candidate path.

## 3. Seed schema

```json
{
  "candidate": "Concrete company or asset",
  "ticker": "required for LISTED_EQUITY",
  "asset_type": "LISTED_EQUITY|PRIVATE_COMPANY|COMMODITY|TECHNOLOGY|OTHER",
  "relation_type": "DIRECT_WINNER|SUBSTITUTE_WINNER|COMPETITOR_WINNER|BOTTLENECK_OWNER|INFRA_ASSET_OWNER|SECOND_ORDER|SHORT_CANDIDATE",
  "origin_crux": "C1",
  "landscape_path_id": "L1",
  "origin_hypothesis_id": "WH-... or null",
  "causal_path": "crux outcome -> candidate-specific value transfer",
  "economic_exposure": "known capture mechanism or blank",
  "why_market_may_miss": "candidate-specific expectation gap or blank",
  "pricing_anchor": {
    "as_of_date": "YYYY-MM-DD",
    "anchor_type": "ABSOLUTE_VALUATION|RELATIVE_VALUATION|EMBEDDED_EXPECTATION|CONTRACT_PRICE|CAPACITY_OR_EARNINGS|MARKET_PRICE",
    "metric": "observable metric",
    "current_value": "current value",
    "comparison_value": "comparison",
    "source": "organization",
    "source_url": "same-round seed evidence URL",
    "source_claim": "what the source establishes"
  },
  "catalyst": "observable event or blank",
  "catalyst_window": {
    "event": "observable event",
    "expected_by": "YYYY-MM-DD",
    "date_status": "REVIEW_CHECKPOINT|DATE_CLAIMED_UNVERIFIED"
  },
  "falsifier": "observable candidate-specific failure condition or blank",
  "evidence": []
}
```

Missing price, economic exposure, catalyst, or falsifier is a visible verification gap. It must not
delete the lead, but it also cannot be silently filled from an abstract parent hypothesis.

## 4. Discovery and verification are asymmetric

Discovery may mention and compare CandidateMapItems with explicit evidence labels. Focused
verification is stricter and asks whether a selected candidate has:

- candidate-specific economic capture;
- an observable price or embedded-expectation anchor;
- catalyst timing inside the declared horizon;
- liquidity, crowding and tradability evidence when relevant;
- a concrete falsifier and strongest alternative explanation;
- at least two genuinely independent publisher paths for high-confidence factual claims.

Failure to pass focused verification means `WATCH_ONLY` or `NO_USABLE_SETUP` for the current
window. It does not prove that the theme has no market opportunity.

## 5. Conditional ordering

The Deep Research Report may provide:

- research-attention ordering;
- `EVENT_SETUP` ordering;
- `ECONOMIC_SETUP` ordering.

Every ordered setup must show its trigger, invalidation, time window, crowding or position risk,
and evidence boundary. Do not describe this ordering as expected return, conviction, buy/sell
advice, target price, or position size.

## 6. Identity and de-duplication

- Prefer ticker as the exact identity for listed securities;
- otherwise use normalized explicit entity name plus asset type;
- keep different causal paths separate even when they point to the same entity;
- do not merge evidence across unrelated cruxes or mechanisms to manufacture confidence;
- never freeze an abstract mechanism as a candidate identity.

## 7. Stop semantics

`NO_USABLE_SETUP` is valid only after bounded work covers concrete securities, alternative and
second-order routes, price/crowding, and the declared event window, and explicitly inspects the
economic-chain, market-carrier, competitor/substitute, failure/adverse, and ownership/capital
candidate-construction routes. An `INSUFFICIENT` route remains incomplete. Search exhaustion means only
that the current route produced no new information. It is not market-negative evidence.
