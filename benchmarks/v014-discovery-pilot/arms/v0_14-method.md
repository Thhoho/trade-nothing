# v0.14 landscape-first crux research method adapter

This is a frozen-corpus projection of the pinned v0.14 `trade-nothing -deepthink2` method. Execute
the method yourself as one researcher; do not claim that separate agents or the full orchestrator
ran. Use only the dispatch and corpus tools.

1. Frame the root question and separate thesis truth, market pricing, and tradeable vehicle. Build
   3–5 decisive cruxes with causal role, pass condition, falsifier, and weakest link.
2. Before naming companies, create an entity-agnostic Landscape Map of 5–7 paths. Across the map
   include all five archetypes: `DIRECT_CAPTURE`, `BOTTLENECK_OWNER`, `ENABLER_OR_INPUT`,
   `SUBSTITUTE_OR_AVOIDANCE`, and `ADVERSE_EXPOSURE`. Every path must show: path ID, linked crux,
   hypothesis, a 3–6 node value-transfer chain, economic-capture test, pricing question, falsifier,
   and exactly two distinct search queries.
3. Probe every planned path from two adversarial perspectives: a constructive evidence search and
   a falsification search. Because this adapter is single-model, label these as two passes, not as
   independent agents. Record each pass as `SUPPORTED`, `REJECTED`, or `UNKNOWN` with read
   `doc_id` evidence. Aggregate a path as supported only when neither pass rejects it; preserve
   conflict as `UNKNOWN`. No path may remain `UNPROBED` in a complete report.
4. Maintain a separate root-crux ledger. Do not average conflicts or borrow evidence across paths.
   Harvest at most three OpportunitySeeds only from completed paths. Each seed must bind its
   `landscape_path_id` and `origin_crux`, and include its own value-capture chain, as-of pricing
   anchor or explicit `UNKNOWN`, catalyst/observable, falsifier, maturity, and next research step.
   A seed from an unsupported path is a lead, never ready for screening.
5. Conclude the root thesis as `EDGE_FOUND`, `NO_EDGE`, or `INSUFFICIENT_EVIDENCE`. Judge thesis,
   pricing gap, and vehicle separately. `NO_EDGE` never means `AVOID` or `SHORT`.
6. Produce one concise Markdown report containing: root verdict and next action; Landscape Map
   coverage table from planned path through two passes, aggregate state, and seed binding; crux
   ledger; separate thesis/pricing/vehicle judgments; up to three candidate cards; unresolved gaps;
   and a decisive-claim audit table with frozen `doc_id` citations.

Never invent price anchors, evidence, agent isolation, or certainty. Label unsupported fields
`UNKNOWN` and keep research leads distinct from investable conclusions.
