# Frozen Benchmark Protocol

Use this protocol only to evaluate whether a research architecture adds value. Do not load an
assessment or future outcome into a research role's context.

## Separation

Keep four artifacts physically separate:

1. **Suite case**: prompt, question type, as-of date, frozen evidence identifiers, an
   `evidence_manifest` binding every packet path and SHA-256, and one budget shared by every
   variant. It must not contain expected answers, future returns, major-path labels, or evaluator
   rubrics. Validation rejects missing, changed, path-traversing, or post-as-of packets.
2. **Single-case dispatch**: the generated research input containing exactly one case, its bound
   evidence packet(s), the suite contract hash, and no assessor material. Generate it outside the
   suite directory; never give a research arm repository or benchmark-directory access.
3. **Research result**: exact artifact hash, engine version, completion status, usage, and recovery
   count. The research system must not include a self-assessment.
4. **Blind assessment**: a human or independent evaluator scores the already-frozen artifact and
   binds its assessment to that artifact's SHA-256.

Run `scripts/benchmark_harness.py validate-suite` before dispatch, then use `materialize-case` to
write each research input into a separate runtime directory. Copy the printed
`suite_contract_sha256` into every result. The contract hash binds prompts, arms, budgets, packet
identifiers, paths, and packet hashes. Run `score` only after every declared case/variant pair has
both a result and a blind assessment.

The benchmark suite is shipped in installed skill copies for reproducibility. Therefore research
arms must run without filesystem/tool access and receive only the generated dispatch. Prompt-only
instructions such as “do not read assessor files” do not qualify as blind isolation.

```bash
python3 scripts/benchmark_harness.py materialize-case \
  --suite benchmarks/v014-six-case/suite.json \
  --case-id ai_power_infrastructure_2025 \
  --output /private/tmp/ai_power_infrastructure_2025.dispatch.json
```

Minimal suite:

```json
{
  "schema_version": "trade-nothing.benchmark-suite.v1",
  "suite_id": "v014-six-case",
  "variants": ["single_agent", "v0_12", "v0_14"],
  "evidence_manifest": {
    "SNAP-001": {"path": "evidence/SNAP-001.json", "sha256": "64 lowercase hex characters"},
    "SNAP-002": {"path": "evidence/SNAP-002.json", "sha256": "64 lowercase hex characters"}
  },
  "cases": [{
    "case_id": "universe_01",
    "question_type": "UNIVERSE_SEARCH",
    "as_of": "2025-01-15",
    "prompt": "Question shown to every arm",
    "frozen_evidence": ["SNAP-001", "SNAP-002"],
    "budget": {"max_tokens": 50000, "max_searches": 20, "max_wall_seconds": 1800}
  }]
}
```

For every pair, store `<case_id>__<variant>.result.json` and
`<case_id>__<variant>.assessment.json` in one results directory. Keep the bound report artifact in
that directory as well; paths outside it are rejected.

Minimal result:

```json
{
  "schema_version": "trade-nothing.benchmark-result.v1",
  "case_id": "universe_01",
  "variant": "v0_14",
  "suite_contract_sha256": "hash printed by validate-suite",
  "execution_id": "RUN-OR-BASELINE-ID",
  "engine_version": "git-sha-or-baseline-version",
  "completion_status": "COMPLETE",
  "artifact_path": "universe_01__v0_13.report.md",
  "artifact_sha256": "64 lowercase hex characters",
  "usage": {"tokens_total": 12000, "search_count": 8, "wall_seconds": 420},
  "recovery_count": 0
}
```

Minimal assessment:

```json
{
  "schema_version": "trade-nothing.benchmark-assessment.v1",
  "case_id": "universe_01",
  "variant": "v0_13",
  "artifact_sha256": "same hash as the exact report",
  "assessor_id": "blind-reviewer-1",
  "blind": true,
  "metrics": {
    "decisive_claim_total": 0,
    "decisive_claim_correct": 0,
    "false_source_count": 0,
    "major_path_total": 0,
    "major_path_found": 0,
    "candidate_count": 0,
    "effective_seed_count": 0,
    "false_opportunity_count": 0,
    "pricing_anchor_total": 0,
    "pricing_anchor_valid": 0,
    "maturity_misread_count": 0,
    "comprehension_question_total": 0,
    "comprehension_question_correct": 0,
    "manual_edit_count": 0
  }
}
```

## Comparison arms

Use at least two arms. The persisted v0.14 six-case benchmark uses:

- `single_agent`: the same model with one structured research prompt;
- `v0_12`: current crux workflow without Landscape Map;
- `v0_14`: current crux workflow with Landscape Map, explicit pricing/vehicle separation, bounded
  artifact handoffs, opportunity harvesting, and CandidateScreen contracts.

Give each arm the same frozen evidence packet and the same maximum Token, search, and wall-clock
budget. A run exceeding any cap is not comparable. Report failed and recovered runs; do not silently
drop them.

## Metrics

An assessor records integer counts. The harness derives rates and cost-normalized metrics:

- decisive claim precision and false-source count;
- major value-path coverage;
- candidate count, effective seeds, and false opportunities;
- valid as-of pricing anchors;
- candidate-maturity misreads;
- 60-second comprehension questions;
- manual edits;
- Tokens and wall time per effective seed.

Three- and six-month relative returns are a separate lagging observation. They must never replace
frozen-thesis, pricing, vehicle, catalyst, and execution attribution.

## Stop rules

- If six cases show no path-coverage gain from Landscape Map, stop expanding it.
- If twenty cases show no lower false-opportunity rate or higher path coverage than the same-model
  single-agent arm, delete redundant roles.
- If five consecutive live runs produce no valid as-of pricing anchor, stop prompt tuning and add a
  dedicated price/valuation/consensus adapter.
- Never use candidate count, report length, or search count as a success metric.
