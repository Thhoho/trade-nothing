# Trade Nothing v0.13.0

Release date: 2026-07-31

v0.13.0 is the current operational release of Trade Nothing. It retains the hypothesis-led
exploration architecture introduced in v0.10 and adds explicit temporal contracts, bounded
research-allocation semantics, and a facts-locked human reporting bundle.

## Highlights

### Exact time semantics

- `as_of_date` is the last admissible evidence date.
- `horizon` is the relative decision window.
- `forecast_target_date` is an optional exact future target and can never be rendered as evidence
  coverage.
- Missing or contradictory time fields fail closed instead of being silently repaired.

### Bounded research allocation

- Research routes, round budgets, continuation, and exploration execution remain explicit.
- A timeout, failed role, or exhausted route is retained as a receipt; it does not trigger an
  automatic retry.
- Formal research and the non-promotable exploration ledger remain physically separate.

### Facts-locked reporting

Every converged report exposes three deterministic Markdown artifacts:

1. `facts_box_markdown`
2. `evidence_ledger_markdown`
3. `candidate_cards_markdown`

The Facts Box must appear verbatim at the top of every newly composed Decision Brief. The
validator rejects missing, moved, duplicated, or modified facts while allowing the narrative after
the box to follow the actual research findings rather than a fixed prose template. Registered runs
persist the three layers as separate content-addressed artifacts.

### Preserved decision gates

- `NO_EDGE` remains different from `AVOID` and `SHORT`.
- `HYPOTHESIS_ONLY`, `TRACED`, and exploration `EVIDENCE_BACKED` remain non-promotable.
- CandidateScreen, snapshot-bound claim verification, and human review remain mandatory.
- No report, heuristic score, release tag, or passing test authorizes a Thesis, Decision, order,
  position, or research retry.

## Compatibility and history

- [`hypothesis-led-research-v0.10.md`](hypothesis-led-research-v0.10.md) remains the historical
  foundation design; its version references are intentionally unchanged.
- Frozen benchmark packets, old method identities, compatibility branches, and Git tags retain
  their original versions.
- The deterministic `brief` and `full` report views remain compatibility fallbacks. New hosts
  should use the Facts Box, Evidence Ledger, Candidate Cards, and structured view model.
- The legacy `-deepthink` v0.9 pipeline remains available but uncalibrated.

## Calibration boundary

`scripts/benchmark_current.py --check` returns `UNBENCHMARKED_METHOD_CHANGE`. The exact operational
identity is recorded in `benchmarks/current.json`; the last calibrated identity remains v0.9.9.
Deterministic engineering gates passing for v0.13.0 is not evidence of improved discovery recall,
research effectiveness, alpha, return, or risk-adjusted performance.

## Release verification

Run from the repository root:

```bash
python3 scripts/version.py
python3 scripts/benchmark_current.py --check --source-repo .
make test
```

The annotated Git tag `v0.13.0` must point to the exact commit that passes these checks.

## 中文摘要

v0.13.0 是当前运行版本：它保留 v0.10 的假说驱动探索基础，并新增失败关闭的时间契约、
有界研究预算语义，以及由 Facts Box、Evidence Ledger、Candidate Cards 组成的三层报告
产物。历史设计、冻结基准和旧标签继续保留原版本号；当前版本通过工程门不代表研究有效性
或投资收益已经得到证明。
