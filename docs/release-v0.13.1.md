# Trade Nothing v0.13.1

Release-candidate audit date: 2026-08-06

v0.13.1 is a reporting-contract patch over the historical v0.13.0 release. It fixes paths that
could preserve the research ledger while failing to hand the host a complete user-facing report.
It does not relax convergence, source, isolation, ranking, claim-verification, human-review, or
trading controls.

## Fixed report routing

- `--report` now has one output route at every research state: `report_data_ready` with the locked
  Facts Box, Evidence Ledger, Candidate Cards, structured view model, compatibility report view,
  and a Resolution Memo when unconverged.
- The deprecated `--allow-non-formal` flag remains accepted for old callers but is now a no-op with
  a warning. It can no longer select a ledger-only early return.
- Host terminal continuation text is stored separately and no longer overwrites the report-
  composition instruction after a fuse, round-budget stop, candidate gap, or screen handoff.
- Registered stage envelopes retain report grade, unmet research gates, publication/ranking
  permissions, and candidate lifecycle state in their bounded control projection while persisting
  full Markdown bodies as content-addressed artifacts.
- Landscape requirement now comes from the declared research intent/question contract rather than
  from whether path rows happened to be present. A missing required map can no longer erase its own
  coverage gate.

## Corrected grade semantics

`report_grade` now describes the root research report only:

- `EXPLORATORY`: root research is not converged;
- `PROVISIONAL`: converged, but required Landscape coverage or independent crux sourcing is
  incomplete; and
- `FORMAL`: converged, required Landscape coverage complete, and every crux independently sourced.

CandidateScreen and snapshot-bound claim verification are projected under `candidate_lifecycle`.
CandidateScreen gates named-security ranking; claim verification gates promotion from
`THESIS_CANDIDATE` to `VERIFIED_FOR_HUMAN`. Zero candidates and zero screenable candidates remain
valid formal research outcomes. A candidate that has been rescreened uses only its latest screen
when computing ranking permission, so stale WATCHLIST history cannot override a later rejection.
Any positive ranking permission is limited to the explicit `rankable_seed_ids`; it cannot spill over
to unscreened or rejected candidates.

## Compatibility and migration

- Existing v0.13.0 run state is not rewritten. Its pinned method identity remains historical and
  fails closed if a v0.13.1 runtime attempts to resume it.
- A v0.13.0 state may be copied to an isolated scratch location for read-only report-regression
  verification. Do not adopt or mutate the original merely to regenerate a view.
- Candidate promotion requirements and isolation receipts are unchanged.

## Calibration boundary

`scripts/benchmark_current.py --check` remains `UNBENCHMARKED_METHOD_CHANGE`. Passing deterministic
engineering tests does not establish improved discovery recall, research effectiveness, alpha,
return, or risk-adjusted performance.

## Release verification

Run from the repository root:

```bash
python3 scripts/version.py
python3 scripts/benchmark_current.py --check --source-repo .
make test
```

Then install into fresh temporary Gemini, Codex, and Claude targets and run
`scripts/check_source_sync.py`. The annotated tag `v0.13.1` must point to the exact commit that
passes these checks. Do not create or push the tag without explicit release authorization.

## 中文摘要

v0.13.1 修复两类报告链路错误：旧兼容参数不再提前返回“只有证据账本”的结果，Host 的
续研提示也不再覆盖报告生成提示。同时，研究报告等级与候选晋级正式解耦：FORMAL 只看
收敛、必要 Landscape 覆盖与 crux 独立来源；CandidateScreen 只控制具名标的排序，claim
核验只控制候选能否进入人工复核。旧 run 不会被改写，也不会自动迁移或续跑。
