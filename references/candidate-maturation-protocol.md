# Candidate Maturation Protocol

Use this protocol after an `OpportunitySeed` is admitted and remains `EVIDENCE_BACKED`. Seed-local
gap work may run in parallel with root research so a short-lived opportunity window is not wasted.
It closes the gap between discovery and CandidateScreen without rewriting the seed, changing root
state, or weakening any evidence or promotion gate.

## State model

The original seed contract and seed evidence remain immutable. Candidate maturation adds three
separate histories:

1. `candidate_gap_tasks`: deterministic, content-addressed research contracts. A task always keeps
   `status=PLANNED`.
2. `candidate_evidence_supplements`: every bounded search attempt, including `NOT_ALIGNED` and
   `CONTRADICTED` results.
3. `candidate_gap_resolutions`: one terminal record per task: `COMPLETED`, `SOURCE_EXHAUSTED`, or
   `WAITING_EVENT`.

Only a `SUPPORTED` supplement bound to a `COMPLETED` resolution participates in the effective-seed
projection. It may add an independent citation and fill only the task's missing field. It may not
overwrite an existing scalar or nested field. A contradiction remains a blocker. Exhaustion and
waiting are valid terminal research results, not failures to be hidden.

## Task contract

The planner selects at most three entities and creates at most one open task per seed. Each task
freezes:

- one blocker and target claim;
- allowed source types and publishers already used by the effective seed;
- a four-attempt search budget;
- explicit success and failure conditions;
- the origin seed, crux, causal path, as-of date, and state hash.

The planner ignores root-only blockers it cannot legally change. A pre-convergence task may fill a
pricing anchor or collect an independent source, but the seed remains non-screenable until the root,
origin, Landscape, horizon, and all other original readiness gates pass. Research order may use the
linked hypothesis's asymmetry/testability score as a tie-break; this is research attention only.

Task, supplement, and resolution identities derive from canonical SHA-256 payloads. Editing any
historical record invalidates the v4 project handoff.

## Commands

```bash
python3 scripts/deepthink_orchestrator_v2.py --plan-candidate-gaps --topic "TARGET"

python3 scripts/deepthink_orchestrator_v2.py --submit-gap-evidence --topic "TARGET" \
  --task-id "CGT-..." --supplement '<candidate-evidence-supplement JSON>'

python3 scripts/deepthink_orchestrator_v2.py --close-gap-task --topic "TARGET" \
  --task-id "CGT-..." --close-status SOURCE_EXHAUSTED \
  --close-reason "bounded search found no claim-aligned independent source"
```

An exact replay is idempotent. A publisher used by the seed or already attempted by the task cannot
be reused as aligned evidence. `SUPPORTED` may deterministically dispatch CandidateScreen when all
remaining gates pass. `CONTRADICTED`, `SOURCE_EXHAUSTED`, and `WAITING_EVENT` never auto-create a
new task, Thesis, Decision, position, or trade.

## Handoff and reporting

Export these histories only through `project-handoff.v4`. Older handoff schemas cannot represent
candidate maturation and must not silently drop it. Reports show the task ID, target claim, source
types, budget, success/failure conditions, attempts, and terminal resolution. The legal next action
for an open task is `EXECUTE_CANDIDATE_GAP_TASK`.

Task completion proves only that the bounded evidence contract reached a terminal state. Candidate
research value still requires a fresh `PRODUCTION_RESEARCH` cohort and downstream CandidateScreen,
claim verification, human selection, and paper-cycle outcomes.
