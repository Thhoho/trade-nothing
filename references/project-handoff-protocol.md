# Project Handoff Protocol

Use this protocol only when moving a completed or explicitly non-formal `deepthink2` state into
`tradenothing-next`. A Markdown report is not an executable handoff.

Run the read-only preflight first. It reports every known blocker and warning in one response:

```bash
python3 scripts/project_handoff.py \
  --state "/absolute/path/to/v2_state.json" \
  --check
```

```bash
python3 scripts/project_handoff.py \
  --state "/absolute/path/to/v2_state.json" \
  --output "/absolute/path/to/tradenothing-next-handoff.json" \
  --report-path "/absolute/path/to/report.md"
```

The v3 exporter:

- retains the question contract, logic graph, Landscape Map, final trace, crux ledger, candidate
  screens and snapshot-bound claim-verification records;
- removes research rounds, raw role transcripts, search logs and dispatch prompts;
- writes `lesson_injections=[]`; Lesson selection remains a separate human action in the product;
- binds the compact state to `handoff_integrity.state_sha256`;
- exports `method_identity` captured at run initialization;
- binds the explicit `state.runtime.run_purpose` selected before the run starts; missing or
  unrecognized purposes fail closed;
- never promotes a candidate, creates a Thesis, approves a Decision or opens a Paper Position.

The checksum detects accidental transfer or UI tampering. It does not authenticate the skill,
runtime, publisher or user. Candidate isolation and claim-verification gates remain independently
mandatory. The product must recompute the checksum before accepting a handoff and must continue to
derive candidate maturity from the imported evidence state.

Only `PRODUCTION_RESEARCH` is eligible for the product effectiveness cohort. Live-discovery and
closed-packet benchmarks, historical replays, and controlled fixtures remain audit-only even when
their mechanics pass. The exporter records purpose; it never decides cohort membership for the
product.

Never repair a blocked historical state by inventing a question type, logic graph, run ID,
run purpose, three-axis verdict, isolation receipt, method identity or Landscape Map after the run.
Preserve it as audit-only history or rerun the question under the current method.

Do not overwrite the source state. Existing output files require explicit `--force`; symlink outputs
are refused.
