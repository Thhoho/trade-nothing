# Report Contract

Use one deterministic `trade-nothing.report-view-model.v2` projection for every user-facing
report. Never derive candidate maturity from prose and never let a narrative model rewrite status
words.

## Time semantics

Every report renders three different concepts explicitly:

- `evidence_as_of_date`: the latest date evidence may enter the run;
- `decision_horizon`: the relative period over which the mechanism is judged; and
- `forecast_target_date`: an optional exact future target, required whenever the decision question
  names a date later than the evidence cutoff.

Never label a future target as “as of” or imply evidence extends to that date. An ambiguous or
invalid temporal contract blocks a new project handoff. Historical artifacts keep the conflict
visible for human resolution; they are not silently rewritten.

## Report grade and the two hard gates

Every run produces a report. Unmet gates lower `report_grade` and constrain what the report may do;
they never delete the research. Withholding output only moved report writing outside the engine,
where nothing is checked.

| Grade | Meaning |
| --- | --- |
| `FORMAL` | Converged, coverage complete, every crux independently sourced, screened, claim-verified. |
| `PROVISIONAL` | Converged, but at least one gate unmet. Deliverable and useful; not publishable. |
| `EXPLORATORY` | Not converged. Deliverable as research; no external use. |

Exactly two gates remain hard:

- `publication_allowed` (`FORMAL` only) — any artifact leaving the author's hands: public posts,
  newsletters, shared documents. A run that cannot reach `FORMAL` must not produce one.
- `ranking_allowed` (requires a completed CandidateScreen) — ordering, scoring, or recommendation
  language over named securities.

Both booleans and the unmet-gate list appear in the Facts Box, so a reader sees the limitation
before the narrative.

## Claim tiers

Claims carry a tier label. A weakly supported claim is publishable inside the report *with its
label*; stripping the label is the violation, not holding the belief.

- `VERIFIED` — two or more independent publisher domains. May be asserted plainly.
- `SINGLE_SOURCE` — real citation, no independent corroboration. Must be marked
  "单一来源·未交叉验证".
- `HYPOTHESIS` — no valid citation. Must be marked "假说". Explicitly allowed in the body, because
  the exploration ledger is where non-consensus insight comes from. Promoting a hypothesis to a bare
  assertion is hypothesis laundering and is the actual red line.

## Self-description is script-filled

Citation counts, round counts, independent-publisher counts, coverage ratio, and convergence status
come from `evidence_counts` and `research_grade`. A narrative model must never write these numbers.
A hand-written evidence count is precisely how a report ends up claiming more support than its
ledger holds.

## Views

- `facts_box`: deterministic compact summary with the three-axis verdict, crux table, candidate
  counts, runtime evidence counts, and singular `formal_action`. Embed it verbatim at the top of
  every new Decision Brief. A narrative model must not modify any value, status word, crux row,
  count, or action in this box.
- `brief`: **legacy** deterministic template containing the root-thesis verdict, what
  survived/failed, candidate counts, `formal_action`, one clearly separated
  `exploration_action` or null, change trigger, and runtime limits. Preserved for backward
  compatibility; prefer `facts_box` plus content-driven narrative synthesis for new reports.
- `cards`: one card per exact candidate identity. Show status before narrative, then economic
  exposure, expectation gap, pricing anchor, explicit trading vehicle and bilateral tradability
  assessment, catalyst, falsifier, blockers, and next action.
- `audit`: complete crux ledger, source registry, CandidateScreen matrix, snapshot alignment, and
  runtime details, plus exploration lineage from wild hypothesis through proxy trails and tests.
  Persist this separately as the Evidence Ledger.
- `full`: **deprecated for new reports**. Retains
  `brief -> insight cards -> candidate cards -> collapsed audit` for backward compatibility.
  New reports use `facts_box` plus narrative synthesis and persist `audit` separately.

`--report` returns `facts_box_markdown`, `evidence_ledger_markdown`, and
`candidate_cards_markdown` together with `report_view_model`. The compatibility field
`report_markdown` remains available but is marked deprecated. For a registered run, the stage
envelope persists the selected compatibility view and the complete result artifact; it does not
inline the report bodies into the parent context. Load the result artifact when compiling the two
new files, and open the Evidence Ledger only when the user asks to read or audit it.

Select a view with:

```bash
python3 scripts/deepthink_orchestrator_v2.py --report --topic "TARGET" --report-view brief
```

The orchestrator does not include `synthesis_packet` by default. Add `--include-synthesis` only
when the caller explicitly wants optional narrative enhancement. A synthesis may improve prose but
must not change any state, count, blocker, next-action code, source, maturity term, exploration
status, or observation/inference boundary. It may not invent a spark that is absent from the stored
exploration ledger.

## Composed Decision Brief

The orchestrator produces a report-data bundle; it does not make an unconstrained narrative model
the source of report truth. A host composes a new Decision Brief in this order:

1. embed `facts_box_markdown` verbatim at the file top;
2. append no more than 120 lines of content-driven narrative from `report_view_model` and, only
   when present, `synthesis_packet`;
3. optionally append `candidate_cards_markdown` without rewriting card states or action codes.

The complete Brief stays within 150 lines before any separately persisted Candidate Cards. It must
surface both the locked `formal_action` and the research-only `exploration_action` without implying
that the latter is authorized. Narrative structure and headings may vary; the verdict, time
contract, crux rows, coverage counts, candidate counts, action codes, and evidence boundaries may
not. Citations must already exist in structured input and use inline publisher/date links.

Registered runs persist the Facts Box, Evidence Ledger, and Candidate Cards as separate
content-addressed artifacts. The LLM-composed Brief is a later host artifact; the compatibility
`report_path` is not evidence that free narrative composition occurred.

## Insight cards

The report must make useful intuition legible without laundering it into evidence. Render a compact
“What we may be missing” card for each selected exploration path with:

- `status` first (`HYPOTHESIS_ONLY`, `TRACED`, or `EVIDENCE_BACKED`);
- `observation`: cited fact or explicit `UNVERIFIED_CLUE`;
- `inference`: the proposed mechanism;
- `surprise_if_true`: why the opportunity or risk map changes;
- `strongest_alternative_explanation`;
- `disconfirming_observation`;
- `expiry_date`, explicitly separated from maturity and requiring human park/supersede review;
- `proxy_trace`: path IDs and bounded clues already followed;
- `cheap_discriminating_test`;
- `payoff_boundary`: optional explicitly supplied same-unit upside/downside magnitudes and their
  mechanical break-even success threshold;
- `evidence_boundary`: what is known, inferred, and still missing.

Do not embed raw Detective/Inquisitor prose or search logs. Insight cards are sanitized projections
of typed exploration objects. Their count, eloquence, or novelty cannot alter formal state.
The break-even threshold, when present, is `downside / (upside + downside)`. It does not estimate
the actual success probability, expected return, target price, trade direction, or size.

## Required separation

The brief must render root-thesis truth and candidate maturity independently:

- root: `edge_state / evidence_direction / actionability`;
- candidate: `EVIDENCE_BACKED / READY_FOR_SCREENING / WATCHLIST / REJECTED /
  THESIS_CANDIDATE / VERIFIED_FOR_HUMAN`;
- cross-system promotion: only `VERIFIED_FOR_HUMAN` is eligible for human review of a new DRAFT
  Thesis.
- discovery coverage: planned Landscape paths, role probes, aggregate path states, and seed
  conversion. Do not hide `UNKNOWN` paths or count them as support.
- exploration maturity: wild hypotheses, sparks, proxy trails, alternative explanations, and
  bounded next tests. Do not count them as candidates or evidence unless a separate formal object
  independently meets its own gate.

For `UNIVERSE_SEARCH`, the report must derive the root verdict with the current deterministic
coverage semantics. Never render a stored global bull/bear direction, weakest support, mean support,
or directional support trace across heterogeneous candidates. The audit may show each crux's
supporting and opposing evidence, but candidate direction and pricing remain candidate-local.

Do not turn `NO_EDGE` into `SHORT`. Do not call a lead, READY seed, WATCHLIST, or unverified
THESIS_CANDIDATE an opportunity, recommendation, or simulated-trade candidate.
An opportunity-oriented report with `UNPROBED` paths is delivered at a reduced `report_grade` with
the coverage gap stated; it is not withheld.
`NO_EDGE` or zero candidates may coexist with high-information exploration actions. Those actions
mean “worth one more bounded test,” not “investable.”

## Formal action and exploration action

Every report must keep these two namespaces physically and semantically separate:

- `formal_action`: the only deterministic state-transition action permitted by root/candidate
  maturity. It is singular for the report and uses only the existing codes below. Candidate cards
  may still display their own state-bound legal next action.
- `exploration_action`: zero or one optional research proposal chosen for information gain.
  They cannot trigger CandidateScreen, Thesis creation, claim verification, a trade, or a formal
  state change. Each requires explicit human authorization for any new search/tool/runtime budget.

An exploration action has this shape:

```json
{
  "action_code": "DESIGN_PROXY_TRAIL|COLLECT_FIRST_PROXY_EVIDENCE|ARTICULATE_STRONGEST_ALTERNATIVE|COLLECT_SECOND_PROXY_EVIDENCE|SEEK_INDEPENDENT_PUBLISHER|COLLECT_PROXY_EVIDENCE|SEEK_DISCONFIRMING_PROXY|TEST_INDEPENDENT_REPLICATION|AUTHORIZED_ACTION_IN_FLIGHT|NO_FOLLOW_ON_AFTER_BOUNDED_ACTION|NO_EXPLORATION_TRACK|NO_HYPOTHESIS_AVAILABLE",
  "action_type": "<compatibility alias of action_code>",
  "hypothesis_id": "WH-...",
  "hypothesis_state": "HYPOTHESIS_ONLY|TRACED|EVIDENCE_BACKED",
  "instruction": "<one discriminating research task>",
  "question": "<one discriminating question>",
  "source_class": "<one bounded primary publisher class>",
  "bounded_query": "<one query or null>",
  "success_condition": "<one observation that changes exploration information>",
  "stop_condition": "<explicit exhaustion or falsification stop>",
  "design_target_id": "DT-...",
  "design_state_revision": 12,
  "budget_boundary": {
    "max_bounded_queries": 1,
    "max_documents_read": 3,
    "max_new_proxy_trails": 1,
    "max_new_publisher_domains": 1,
    "automatic_follow_on": false
  },
  "requires_human_authorization": "<boolean derived from state>",
  "authorization_state": "NEEDS_ACTION_DESIGN|PROPOSED_NOT_AUTHORIZED|PLANNED_NOT_AUTHORIZED|AUTHORIZED_NOT_EXECUTED|NOT_REQUIRED|ROUTE_CLOSED_REQUIRES_NEW_PLAN",
  "authorization_ready": "<boolean derived from state>",
  "executable_after_authorization": "<boolean derived from state>",
  "execution_receipt": null
}
```

`PROPOSED_NOT_AUTHORIZED` is legal only when source class, bounded query, document cap, success
condition, and stop condition are complete. Otherwise the host emits `NEEDS_ACTION_DESIGN`,
`authorization_ready=false`, and `executable_after_authorization=false`; that object cannot be
authorized or executed as a search. The report must show its `design_target_id`
and `design_state_revision`, which authorize only a typed design write. While an
exact plan or authorization is open, show the host action ID/status; an
authorized action becomes `AUTHORIZED_ACTION_IN_FLIGHT` with zero new budget.
Terminal cancelled, stale, failed-no-search, and completed records must not
masquerade as the current proposal.

Never disguise an exploration action as the report's formal next action, and never use it to bypass
a fuse break, root convergence, seed admission, CandidateScreen, or snapshot verification.
Active-round prompts may carry the hypothesis ledger for incidental observations, but must not
carry or execute the proposed `exploration_action`. The optional adapter is a
four-step gate: `--record-exploration-design` writes only the exact
target/revision-bound design; `--plan-exploration` freezes one attempt;
`--authorize-exploration` requires an explicit receipt for that ID; and
`--submit-exploration-result` validates the frozen route and receipt. An
unapproved plan may be explicitly cancelled with a reason. Authorization is
labelled `CALLER_ATTESTED_NOT_HOST_VERIFIED` unless the host separately binds a
real approval event.

A normal result requires exactly one query, at most three documents, exact
`YYYY-MM-DD` dates on or before the frozen as-of, and evidence bound by
document ID or full canonical citation identity. A pre-query tool/runtime
failure uses `EXECUTION_FAILED_NO_SEARCH` with zero searches/documents and
closes no route. A mid-query runtime failure uses
`EXECUTION_FAILED_DURING_QUERY`, preserves any concrete read receipts, ingests
no proxy, and also closes no route. If formal or exploration state changes after authorization,
the report history must show `STALE_RESULT_NOT_RECORDED`, result SHA-256,
no evidence ingestion, and no automatic retry.
The dispatch contract publishes separate machine-valid result shapes for a
normal observation, a pre-query failure, and an in-query failure. Any document
placeholder is an object schema; an executable `documents_read` example is
always an array of zero to three concrete receipt objects, never a string.

ProxyTrail audit views must expose direction conflicts as variants plus
direction/evidence/source-agent/round/crux/action bindings. An `AMBIGUOUS`
summary alone is not complete lineage. Qualitative asymmetry
(`upside_shape`, `convexity`, `downside_shape`, `time_to_signal`, basis) is an
agent declaration used only for research queue order. It must be visible next
to the priority components; it is neither evidence nor a probability, expected
return, recommendation, or sizing input. Conflicting substantive declarations
are contested and contribute no qualitative priority.
Every report view that exposes an open host action must show its exact
`action_id`, host status, and authorization assurance. Durable report history
must also project sanitized terminal host actions, including cancelled plans,
pre-authorization staleness, and `STALE_RESULT_NOT_RECORDED` with result hash,
`result_ingested=false`, and `automatic_retry=false`. `report_view` therefore
includes `authorized_action_history`, `terminal_action_history`,
`design_history`, and `closed_routes`; a blocked resolution memo must preserve
the same lifecycle truth and frozen as-of date.

## Formal next-action codes

Use exactly one action per candidate:

| Candidate state | Legal next action |
| --- | --- |
| `EVIDENCE_BACKED` with open gap task | `EXECUTE_CANDIDATE_GAP_TASK` |
| `EVIDENCE_BACKED` without gap task | `COMPLETE_SEED_CONTRACT`; if the only blocker is source diversity, use `ADD_INDEPENDENT_SOURCE` |
| `READY_FOR_SCREENING` | `RUN_CANDIDATE_SCREEN` |
| `WATCHLIST` | `CLOSE_SCREEN_GAPS_OR_WAIT` |
| `REJECTED` | `ARCHIVE_REJECTION` |
| `THESIS_CANDIDATE` | `RUN_CLAIM_VERIFICATION` |
| `VERIFIED_FOR_HUMAN` | `HUMAN_REVIEW_PROMOTION_PACKET` |

If there is no candidate, use `STOP_NO_PROMOTABLE_CANDIDATE`; if the root verdict is monitor-only,
use `WAIT_FOR_MONITOR`. These formal actions may coexist with an exploration action; the latter does
not soften or contradict the formal result.

When `EXECUTE_CANDIDATE_GAP_TASK` is selected, the card must render its immutable task ID, target
claim, allowed source types, remaining budget, success/failure conditions, attempts, and any terminal
resolution. Do not paraphrase `SOURCE_EXHAUSTED` into a positive lead or hide contradicted evidence.

## Validation

Run `scripts/validate_report_v2.py` against the persisted report and state. Treat its outputs as
three separate claims:

- `REPORT_RENDER_VALID`: Markdown and reference mechanics are valid;
- `RESEARCH_STATE_VALID`: the report matches deterministic state;
- `PROMOTION_ELIGIBILITY`: candidate-by-candidate promotion status.

No one result implies either of the other two.
Exploration richness is not a fourth promotion gate. A valid report may contain
`HYPOTHESIS_ONLY` insight cards, provided their labels and evidence boundaries match state.

For a composed Decision Brief, validation compares only the marked Facts Box byte-for-byte with
`render(state, "facts_box")`; text after the box may vary. A missing, duplicated, moved, or modified
Facts Box fails report validation. Legacy deterministic `brief`, `cards`, `audit`, and `full` views
continue to require whole-view equality with the state-derived renderer.

## Research allocation and evidence matrix

The brief and full views expose `research_allocation` as a first-class comparison of the top
exploration hypotheses. Each row includes qualitative upside shape, convexity, downside shape,
time to signal, information gap, testability, cheapest discriminating test, bounded validation
budget when selected, and stop condition. This ranks research attention only; it is not a
probability, expected return, trade ranking, or sizing input. Missing qualitative asymmetry is
rendered as a gap rather than defaulted to low risk.

Every report also exposes `evidence_matrix.rows`, each bound to exactly one `FORMAL_CRUX`,
`CANDIDATE_PATH`, or `EXPLORATION_PROXY`. Show claim, source, date, URL, direction, and binding ID.
Do not merge a ProxyTrail citation into a formal crux merely because the URL is shared. If the
archived method recorded no hypothesis ledger, render an explicit exploration method gap; absence
of recorded exploration is not evidence that no adjacent opportunity exists.
