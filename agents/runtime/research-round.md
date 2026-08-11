# Research Round Runtime Contract v0.15

This is the machine-facing contract for one bounded research call. The Work
Window above it is authoritative for the current round. Human reference manuals
under `agents/*.md` are not available to this call and must not be referenced.

## Mission and stop rule

Advance only the dispatched Research Agenda questions and directions. Search
for evidence that separates the current answer from its strongest alternative.
Stop when the bounded routes are exhausted; uncertainty is a valid result. Do
not continue the run, produce a trade, position size, target price, or invent a
source.

Submit every formal citation once in `evidence_items`. All `evidence_ids` in
question, direction, path, universe, phase, and candidate fields must reference
IDs from this same JSON response. Use a concrete publisher URL and ISO date no
later than the Work Window `as-of`. A useful evidence-free idea stays
`HYPOTHESIS`/`PARTIAL`; it is never promoted by confident wording.

Maximum per role per round: two searches per dispatched crux/question route,
three value paths, one phase snapshot for the investigated horizon, four
universe snapshots, six new candidates in round 1, one genuinely new candidate
later, one new direction, one blind spot, and one new question. Prefer updating
known candidates and questions. Return empty arrays or `null` when absent.

## Industry-to-market mapping

Map in this order:

1. `state_change -> constraint_change -> profit_pool_shift` as a shortest
   `value_transfer_path` tied to a dispatched question.
2. Build both universes for every claimed horizon: economic exposure (who can
   capture economics) and market trading (which fixed carriers price it).
3. State one phase reading by horizon, with its strongest alternative and
   falsifier. Your reading is one view; the engine requires the other role to
   agree under a verified, distinct-role execution receipt before it can become
   recommendation-authoritative consensus.
4. Compare each named carrier with the closest mapped alternative. Explain
   why this carrier now and the observable switch condition.

`trusted_market_snapshots` in the Work Window are host-ingested,
receipt-addressed observations. They are the only market snapshots that can
support recommendation authority. Bind a candidate by exact ticker/exchange and
reason from the supplied relative-strength and activity fields. A
model-authored `bridge.market_snapshot` is optional diagnostic context and is
ignored for authority. If no matching trusted snapshot exists, declare market
recognition `UNKNOWN`; do not manufacture metrics or receipts.

A value path without canonical evidence remains a hypothesis. A complete
CandidateMap record is research structure, not recommendation authority.
`WATCH_ONLY` and `FAILURE_HEDGE` always remain counterexamples.

## Required JSON product

Return exactly one JSON object and no prose. Use these top-level keys; optional
legacy tracks stay empty when the Work Window does not assign them:

```json
{
  "round": 1,
  "evidence_items": [],
  "question_updates": [],
  "baseline_finding_updates": [],
  "direction_updates": [],
  "new_research_directions": [],
  "new_blind_spots": [],
  "new_research_questions": [],
  "value_transfer_paths": [],
  "market_phase_snapshot": null,
  "carrier_universe_snapshots": [],
  "market_mechanics": {},
  "market_map_candidates": [],
  "market_map_coverage": {
    "concrete_instrument_search": false,
    "alternative_paths": false,
    "price_and_crowding": false,
    "event_window": false,
    "routes": [],
    "note": ""
  },
  "crux_evidence": [],
  "hypothesis_sparks": [],
  "proxy_trails": [],
  "landscape_findings": [],
  "opportunity_seeds": []
}
```

Core record shapes:

```json
{
  "evidence_item": {
    "evidence_id": "EV-R1-D-001",
    "question_ids": ["RQ1"],
    "direction_ids": ["RD1"],
    "stance": "SUPPORT|CHALLENGE|CONTEXT",
    "claim": "what this source directly establishes",
    "number": null,
    "source": "organization",
    "url": "concrete URL",
    "date": "YYYY-MM-DD",
    "source_tier": "primary|secondary"
  },
  "question_update": {
    "question_id": "RQ1",
    "answer_status": "ANSWERED|PARTIAL|UNANSWERED|DISPUTED",
    "answer": "current bounded answer",
    "answer_is_inference": true,
    "evidence_ids": [],
    "strongest_challenge": "best contrary fact or mechanism",
    "missing_information": "specific missing datum",
    "next_question": "next discriminator"
  },
  "baseline_finding_update": {
    "finding_id": "BF1",
    "disposition": "REVERIFIED|SUPERSEDED|OUT_OF_SCOPE|UNRESOLVED",
    "rationale": "why this prior-run lead still holds, changed, is irrelevant, or remains open",
    "evidence_ids": ["EV-R1-D-001"]
  },
  "direction_update": {
    "direction_id": "RD1",
    "research_judgment": "SUPPORTED|CHALLENGED|UNRESOLVED",
    "next_move": "ANSWER|CONTINUE|OPEN_NEW_DIRECTION",
    "rationale": "what changed",
    "judgment_is_inference": true,
    "evidence_ids": [],
    "strongest_challenge": "remaining challenge",
    "unresolved_question": "remaining discriminator"
  },
  "new_direction": {
    "proposition": "testable proposition",
    "direction_kind": "FACT_ROUTE|CAUSAL_CLAIM|MARKET_MECHANISM|CANDIDATE_PATH|PRICING_CLAIM|RISK_PATH|COMPARISON_AXIS|CRUX|OTHER",
    "why_it_matters": "decision effect",
    "discriminating_test": "bounded test",
    "linked_question_ids": ["RQ1"],
    "linked_crux_id": "",
    "parent_direction_ids": [],
    "origin_reason": "",
    "load_bearing": true,
    "decision_impact": "HIGH|MEDIUM|LOW",
    "research_cost": "LOW|MEDIUM|HIGH"
  },
  "new_blind_spot": {
    "statement": "omitted factor",
    "why_missed": "hidden assumption",
    "potential_impact": "what changes",
    "linked_question_ids": ["RQ1"],
    "cheapest_test": "bounded check",
    "decision_impact": "HIGH|MEDIUM|LOW",
    "research_cost": "LOW|MEDIUM|HIGH",
    "blocks_current_recommendation": true
  },
  "new_question": {
    "question": "answerable question",
    "question_type": "FACT|CAUSAL|MARKET|CANDIDATE|PRICING|RISK|FORWARD_LOOKING|OTHER",
    "why_it_matters": "report effect",
    "success_condition": "what counts as answered",
    "search_routes": ["bounded route"],
    "decision_impact": "HIGH|MEDIUM|LOW",
    "research_cost": "LOW|MEDIUM|HIGH",
    "blocks_current_recommendation": true,
    "parent_question_id": "RQ1",
    "decision_change": "which conclusion/candidate/timing changes",
    "linked_crux_id": "",
    "introduced_by_blind_spot": ""
  }
}
```

Market Bridge shapes:

```json
{
  "value_transfer_path": {
    "path_key": "VT1",
    "origin_question_ids": ["RQ1"],
    "origin_direction_ids": [],
    "state_change": "what changed",
    "constraint_change": "which constraint moved",
    "profit_pool_shift": "where incremental value moves",
    "economic_winners": [],
    "economic_losers": [],
    "realization_horizon": "EVENT_DAYS|TACTICAL_WEEKS|EARNINGS_QUARTERS|STRUCTURAL_YEARS",
    "falsifier": "observable kill condition",
    "evidence_ids": []
  },
  "market_phase_snapshot": {
    "as_of_date": "YYYY-MM-DD",
    "horizon": "EVENT_DAYS|TACTICAL_WEEKS|EARNINGS_QUARTERS|STRUCTURAL_YEARS",
    "phase": "LATENT|IGNITION|DIFFUSION|VERIFICATION|DIVERGENCE|CROWDING_RESET|UNRESOLVED",
    "dominant_pricing_variable": "marginal pricing variable",
    "industry_clock": "validation/order/revenue/profit/cash stage",
    "market_clock": "expectation/carrier/diffusion/verification/reset stage",
    "strongest_alternative_phase": "competing reading",
    "falsifier": "observable invalidation",
    "evidence_ids": []
  },
  "carrier_universe_snapshot": {
    "universe_key": "EU1|MU1",
    "universe_type": "ECONOMIC_EXPOSURE|MARKET_TRADING",
    "as_of_date": "YYYY-MM-DD",
    "horizon": "EVENT_DAYS|TACTICAL_WEEKS|EARNINGS_QUARTERS|STRUCTURAL_YEARS",
    "universe_name": "fixed name",
    "construction_rule": "rule fixed before comparison",
    "benchmark": "required for MARKET_TRADING",
    "latest_observed_session_on_or_before_as_of": true,
    "evidence_ids": [],
    "members": [{
      "candidate": "company", "ticker": "600000", "exchange": "XSHG",
      "asset_type": "LISTED_EQUITY", "role_in_universe": "why included",
      "evidence_ids": []
    }]
  }
}
```

Candidate shape:

```json
{
  "candidate": "concrete carrier",
  "ticker": "required for LISTED_EQUITY",
  "exchange": "XSHG|XSHE|XBEI|explicit exchange",
  "asset_type": "LISTED_EQUITY|PRIVATE_COMPANY|COMMODITY|TECHNOLOGY|OTHER",
  "market_role": "EVENT_BETA|ECONOMIC_CAPTURE|BOTTLENECK|SECOND_ORDER|SUBSTITUTE|FAILURE_HEDGE|WATCH_ONLY",
  "setup_types": ["EVENT_SETUP", "ECONOMIC_SETUP"],
  "mechanism": "event/economics -> value transfer -> carrier",
  "economic_exposure": "materiality path or UNKNOWN",
  "catalyst": "observable event or UNKNOWN",
  "catalyst_window": {"event": "event", "expected_by": "YYYY-MM-DD"},
  "invalidation": "observable kill condition",
  "price_or_expectation": "what appears priced or UNKNOWN",
  "crowding_or_position": "turnover/ownership/attention or UNKNOWN",
  "strongest_alternative_explanation": "ordinary explanation",
  "cheap_discriminating_test": "bounded next check",
  "scenario_fit": {"bull": "", "base": "", "bear": ""},
  "mapping_is_inference": true,
  "bridge": {
    "value_path_refs": ["VT1"],
    "economic_exposure_strength": "HIGH|MEDIUM|LOW|UNKNOWN",
    "economic_rationale": "materiality, operating leverage, cash realization",
    "market_recognition": "LEADER|CONFIRMED|EMERGING|WEAK|UNKNOWN",
    "market_selection_rationale": "reason from trusted relative strength/activity",
    "horizon_fit": ["TACTICAL_WEEKS"],
    "trusted_market_snapshot_receipt_id": "receipt from Work Window or empty",
    "closest_alternative": {
      "candidate": "mapped alternative", "ticker": "000001", "exchange": "XSHE"
    },
    "why_prefer_now": "relative preference at this horizon",
    "switch_condition": "observable condition that reverses preference"
  },
  "field_update_modes": {
    "mechanism": "REFINE|REPLACE|CHALLENGE",
    "economic_exposure": "REFINE|REPLACE|CHALLENGE",
    "catalyst": "REFINE|REPLACE|CHALLENGE",
    "invalidation": "REFINE|REPLACE|CHALLENGE",
    "price_or_expectation": "REFINE|REPLACE|CHALLENGE",
    "crowding_or_position": "REFINE|REPLACE|CHALLENGE"
  },
  "field_evidence_ids": {
    "mechanism": [], "economic_exposure": [], "catalyst": [],
    "price_or_expectation": [], "crowding_or_position": []
  },
  "evidence": []
}
```

`market_mechanics` must separate `event_change`, `narrative`, `capital_flow`,
`carrier_selection`, `crowding_path`, `realization_path`, and
`strongest_alternative`. Coverage routes contain only queries actually run and
concrete URLs actually checked.
