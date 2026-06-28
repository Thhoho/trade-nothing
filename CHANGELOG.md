# Changelog

## v0.10.2

- Treat `fuse_break` as a blocked state, not convergence. Formal reports are refused
  while any crux remains `OPEN` or `PENDING`.
- Add citation quality gates for `-deepthink2`: concrete URLs are required, homepage
  citations are filtered, unsupported Judge signals are zeroed, and strong signals
  without numeric citations are capped.
- Add `scripts/validate_report_v2.py` to validate final reports for concrete references,
  filled BATTLE_LOG sections, known citation IDs, and uncited data-like numbers.
- Add a B-layer citation whitelist to v2 reports so synthesis can only reuse
  engine-registered references.
- Update agent prompts to require concrete article/filing/API URLs rather than bare domains.
