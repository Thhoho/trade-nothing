# Report Contract

Use one deterministic `trade-nothing.report-view-model.v1` projection for every user-facing
report. Never derive candidate maturity from prose and never let a narrative model rewrite status
words.

## Views

- `brief`: root-thesis verdict, what survived/failed, candidate counts, the only legal next action,
  change trigger, and runtime limits. Prefer this when parent-context cost matters.
- `cards`: one card per exact candidate identity. Show status before narrative, then economic
  exposure, expectation gap, pricing anchor, catalyst, falsifier, blockers, and next action.
- `audit`: complete crux ledger, source registry, CandidateScreen matrix, snapshot alignment, and
  runtime details.
- `full`: `brief -> cards -> collapsed audit`. This is the default persisted Markdown artifact.

For a registered run, the stage envelope persists the selected Markdown view and returns its
content-addressed `report_path`; it does not inline the report into the parent context. Only open the
full artifact when the user asks to read/audit it. Otherwise return the brief projection and path.

Select a view with:

```bash
python3 scripts/deepthink_orchestrator_v2.py --report --topic "TARGET" --report-view brief
```

The orchestrator does not include `synthesis_packet` by default. Add `--include-synthesis` only
when the caller explicitly wants optional narrative enhancement. A synthesis may improve prose but
must not change any state, count, blocker, next-action code, source, or maturity term.

## Required separation

The brief must render root-thesis truth and candidate maturity independently:

- root: `edge_state / evidence_direction / actionability`;
- candidate: `EVIDENCE_BACKED / READY_FOR_SCREENING / WATCHLIST / REJECTED /
  THESIS_CANDIDATE / VERIFIED_FOR_HUMAN`;
- cross-system promotion: only `VERIFIED_FOR_HUMAN` is eligible for human review of a new DRAFT
  Thesis.

Do not turn `NO_EDGE` into `SHORT`. Do not call a lead, READY seed, WATCHLIST, or unverified
THESIS_CANDIDATE an opportunity, recommendation, or simulated-trade candidate.

## Next-action codes

Use exactly one action per candidate:

| Candidate state | Legal next action |
| --- | --- |
| `EVIDENCE_BACKED` | `COMPLETE_SEED_CONTRACT` |
| `READY_FOR_SCREENING` | `RUN_CANDIDATE_SCREEN` |
| `WATCHLIST` | `CLOSE_SCREEN_GAPS_OR_WAIT` |
| `REJECTED` | `ARCHIVE_REJECTION` |
| `THESIS_CANDIDATE` | `RUN_CLAIM_VERIFICATION` |
| `VERIFIED_FOR_HUMAN` | `HUMAN_REVIEW_PROMOTION_PACKET` |

If there is no candidate, use `STOP_NO_PROMOTABLE_CANDIDATE`; if the root verdict is monitor-only,
use `WAIT_FOR_MONITOR`.

## Validation

Run `scripts/validate_report_v2.py` against the persisted report and state. Treat its outputs as
three separate claims:

- `REPORT_RENDER_VALID`: Markdown and reference mechanics are valid;
- `RESEARCH_STATE_VALID`: the report matches deterministic state;
- `PROMOTION_ELIGIBILITY`: candidate-by-candidate promotion status.

No one result implies either of the other two.
