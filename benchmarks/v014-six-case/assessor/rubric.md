# Blind Assessor Rubric

The assessor receives anonymized report artifacts plus `answer-key.json`; the assessor must not know
which arm produced which artifact. Read the report for 60 seconds before answering the comprehension
questions, then perform the full audit.

Count metrics mechanically:

- `decisive_claim_total`: report claims that materially change truth, pricing, vehicle, or action.
- `decisive_claim_correct`: decisive claims supported by the frozen packet without changing legal,
  temporal, adjustment, or maturity semantics.
- `false_source_count`: cited sources that do not exist in the packet, post-date as-of, or do not
  support the associated claim.
- `major_path_total`: number of paths in the evaluator key. This denominator is identical across arms.
- `major_path_found`: keyed paths explicitly evaluated, including a justified rejection.
- `candidate_count`: named tradeable vehicles presented as LEAD or more mature; generic industries do
  not count.
- `effective_seed_count`: candidates with a defensible value-capture chain, as-of pricing anchor,
  catalyst/observable, and falsifier. A candidate may still be WATCHLIST.
- `false_opportunity_count`: candidates matching a keyed trap or relying on a broken value-capture
  chain. It cannot exceed candidate count.
- `pricing_anchor_total`: candidate dossiers that require a pricing judgment.
- `pricing_anchor_valid`: dossiers binding a packet as-of price and stating what expectation/gap would
  make that price attractive; merely copying the price is not valid.
- `maturity_misread_count`: LEAD/WATCHLIST evidence presented as verified recommendation, proposal
  presented as final law, planned/contracted capacity presented as delivered, or similar inflation.
- `comprehension_question_total`: always 3 per artifact.
- `comprehension_question_correct`: answers correctly recovered after the initial 60-second read.
- `manual_edit_count`: material edits needed to fix verdict, maturity, candidate, pricing, or action;
  grammar edits do not count.

Do not reward report length, candidate count, confident tone, role count, or predicted returns.
