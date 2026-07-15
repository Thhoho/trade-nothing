# Project Handoff Protocol

Use this protocol only when moving a completed or explicitly non-formal `deepthink2` state into
`tradenothing-next`. A Markdown report is not an executable handoff.

```bash
python3 scripts/project_handoff.py \
  --state "/absolute/path/to/v2_state.json" \
  --output "/absolute/path/to/tradenothing-next-handoff.json" \
  --report-path "/absolute/path/to/report.md"
```

The exporter:

- retains the question contract, logic graph, Landscape Map, final trace, crux ledger, candidate
  screens and snapshot-bound claim-verification records;
- removes research rounds, raw role transcripts, search logs and dispatch prompts;
- writes `lesson_injections=[]`; Lesson selection remains a separate human action in the product;
- binds the compact state to `handoff_integrity.state_sha256`;
- never promotes a candidate, creates a Thesis, approves a Decision or opens a Paper Position.

The checksum detects accidental transfer or UI tampering. It does not authenticate the skill,
runtime, publisher or user. Candidate isolation and claim-verification gates remain independently
mandatory. The product must recompute the checksum before accepting a handoff and must continue to
derive candidate maturity from the imported evidence state.

Do not overwrite the source state. Existing output files require explicit `--force`; symlink outputs
are refused.
