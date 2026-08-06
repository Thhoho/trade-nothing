# Trade Nothing v0.14.0

Release-candidate audit date: 2026-08-06

v0.14.0 makes the research method match its opportunity-discovery philosophy: search broadly for
non-consensus, asymmetric payoff structures, then spend scarce research capacity on evidence that
can actually distinguish the proposed mechanism from its strongest alternative. It fixes a
liveness failure in which a stream of new but non-discriminating URLs could keep cruxes `OPEN`
until the round fuse.

This release does not relax formal convergence, source diversity, Landscape coverage, isolation,
CandidateScreen, snapshot claim verification, human review, or trading controls.

## Decision-discriminating evidence

- Every accepted citation now receives an explicit decision disposition: directional bull,
  directional bear, new but non-discriminating, agent evidence omitted by Judge, or no new
  admissible evidence.
- Bibliographic novelty is no longer decision progress. Only a new Judge-accepted citation with a
  non-zero directional signal resets the evidence-exhaustion streak.
- A new background, balanced, or otherwise non-discriminating citation remains in the Evidence
  Ledger. It does not change support and counts as a decision-dry bilateral probe.
- Two adequately sourced, valid bilateral decision-dry probes may settle an unresolved crux as
  `MONITORABLE`. This means bounded research exhaustion only, never truth, probability, or edge.
- Host dry-round stopping uses the same decision semantics, so audit-only URL growth cannot keep a
  run alive indefinitely.

## Asymmetric research allocation

- `WildHypothesis.exploration_priority` now propagates to its Landscape path as a research-attention
  score. It breaks ties only after fairness, dispatch alignment, and starvation prevention.
- Framer, Detective, Inquisitor, and Judge instructions ask for the cheapest observation that
  separates the non-consensus mechanism from its strongest alternative explanation.
- Crux and Landscape schedulers use qualitative asymmetry only to order research attention. The
  score is not an investment rank, probability, expected return, target price, direction, or
  position-size input.

## Feasible rounds and useful parallel work

- Framing feasibility now budgets settlement touches under the engine's real two-crux-per-round
  capacity. Directional cruxes need enough contested evidence touches; unresolved cruxes need
  source acquisition plus the decision-dry window.
- A five-crux non-universe frame therefore needs at least eight rounds under the current contract.
  Source acquisition and decision-dry probing may overlap, so the gate does not inflate that floor
  by pretending they are serial phases. A requested fuse below the real floor is rejected before
  state initialization.
- Continuation recommendations use aggregate missing dispatch slots rather than the largest
  single-crux gap, preventing severe underestimation on broad runs.
- Candidate-local pricing, catalyst, falsifier, and snapshot gap tasks may be prepared before root
  convergence. They remain explicitly unable to settle root cruxes, satisfy Landscape coverage,
  unlock ranking, or bypass CandidateScreen.

## Report and audit surface

- Evidence Ledger rows show directional versus non-discriminating decision touches.
- Resolution Memos expose the real aggregate continuation demand and distinguish source novelty
  from decision progress.
- The complete graded report bundle still renders at terminal stops. `FORMAL` remains gated by root
  convergence, required Landscape completion, and independent sourcing for every crux.

## Compatibility and migration

- Existing v0.13.x run state is not rewritten. Its pinned method identity remains historical and
  fails closed if a v0.14.0 runtime attempts to resume it.
- Historical state may be inspected or projected read-only to explain how the new policy would
  allocate work. Such a projection is not a replay, migration, or new formal verdict.
- New runs must be framed and initialized under the v0.14.0 method identity.

## Calibration boundary

`scripts/benchmark_current.py --check` remains `UNBENCHMARKED_METHOD_CHANGE`. Passing deterministic
engineering tests establishes contract consistency, not improved opportunity recall, lead quality,
alpha, return, or risk-adjusted performance. Historical suites remain controls for the last
calibrated method until a new blind effectiveness benchmark is completed.

## Release verification

Run from the repository root:

```bash
python3 scripts/version.py
python3 scripts/benchmark_current.py --check --source-repo .
make test
```

Then install into fresh temporary Gemini, Codex, and Claude targets and run
`scripts/check_source_sync.py`. The annotated tag `v0.14.0` must point to the exact commit that
passes these checks. Do not create or push the tag without explicit release authorization.

## 中文摘要

v0.14.0 把“非对称机会”从口号变成研究资源分配规则：先允许大胆的非共识假说进入探索
账本，再优先寻找能区分该机制与最强替代解释的低成本证据。新的 URL 仍可进入审计，
但只有带方向判别力的 Judge 接纳证据才算决策进展；否则会推进证据耗尽，避免 run 因
背景材料不断新增而永远卡在 `OPEN`。正式报告、来源、Landscape、候选筛选和人工复核
闸门均未放松。
