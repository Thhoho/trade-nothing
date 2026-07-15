# Frozen Benchmark Protocol

Use this protocol to compare reasoning, maturity control, and report usability from identical frozen
inputs. Do not load an assessment or future outcome into a research role's context. This protocol
does not test source discovery, full-universe coverage, or alpha.

## Separation

Keep four artifacts physically separate:

1. **Suite case**: prompt, question type, as-of date, frozen evidence identifiers, an
   `evidence_manifest` binding every packet path and SHA-256, and one budget shared by every
   variant. It must not contain expected answers, future returns, major-path labels, or evaluator
   rubrics. Validation rejects missing, changed, path-traversing, or post-as-of packets.
2. **Single-case dispatch**: the generated research input containing exactly one case, its bound
   evidence packet(s), the suite contract hash, an exact variant contract, and no assessor material.
   Generate it outside the suite directory; never give a research arm repository or
   benchmark-directory access.
3. **Research result**: exact artifact hash, engine version, completion status, usage, and recovery
   count. The research system must not include a self-assessment.
4. **Blind assessment**: a human or independent evaluator scores the already-frozen artifact and
   binds its assessment to that artifact's SHA-256.

Run `scripts/benchmark_harness.py validate-suite` before dispatch, then use `materialize-case` to
write each research input into a separate runtime directory. Copy the printed
`suite_contract_sha256` into every result. The contract hash binds prompts, arms, budgets, packet
identifiers, paths, and packet hashes. Run `score` only after every declared case/variant pair has
both a result and a blind assessment.

`variant_manifest` is mandatory. A prompt-only baseline binds its instruction path and SHA-256. A
skill arm binds a full Git commit plus the hashes of its entrypoint and orchestrator. Variant labels
without executable pins are not experiments.

Before running, use `verify-variants --source-repo <canonical repo>` to resolve every pinned file from
the Git object database and compare its hash. Every result must include a host-verified
`engine_receipt` binding runner kind, engine version, variant contract, actual file hashes, and a
unique host invocation ID. This catches accidental drift; it does not protect against a malicious
host fabricating receipts.

The benchmark suite is shipped in installed skill copies for reproducibility. Therefore research
arms must run without filesystem/tool access and receive only the generated dispatch. Prompt-only
instructions such as “do not read assessor files” do not qualify as blind isolation.

```bash
python3 scripts/benchmark_harness.py materialize-case \
  --suite benchmarks/v014-six-case/suite.json \
  --case-id ai_power_infrastructure_2025 \
  --variant single_agent \
  --output /private/tmp/ai_power_infrastructure_2025.dispatch.json
```

Minimal suite:

```json
{
  "schema_version": "trade-nothing.benchmark-suite.v3",
  "suite_id": "v014-six-case",
  "variants": ["single_agent", "v0_12", "v0_14"],
  "variant_manifest": {
    "single_agent": {
      "runner_kind": "PROMPT_ONLY",
      "engine_version": "prompt:<instruction sha256>",
      "instruction_path": "arms/single_agent.md",
      "instruction_sha256": "64 lowercase hex characters"
    },
    "v0_12": {
      "runner_kind": "GIT_SKILL_SNAPSHOT",
      "engine_version": "git:<full commit sha>",
      "git_commit": "40 lowercase hex characters",
      "entrypoint_path": "SKILL.md",
      "entrypoint_sha256": "64 lowercase hex characters",
      "orchestrator_path": "scripts/deepthink_orchestrator_v2.py",
      "orchestrator_sha256": "64 lowercase hex characters"
    },
    "v0_14": {
      "runner_kind": "GIT_SKILL_SNAPSHOT",
      "engine_version": "git:<full commit sha>",
      "git_commit": "40 lowercase hex characters",
      "entrypoint_path": "SKILL.md",
      "entrypoint_sha256": "64 lowercase hex characters",
      "orchestrator_path": "scripts/deepthink_orchestrator_v2.py",
      "orchestrator_sha256": "64 lowercase hex characters"
    }
  },
  "evaluation_scope": "CLOSED_PACKET_REASONING",
  "research_access": {"external_search_allowed": false, "filesystem_allowed": false},
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
    "budget": {"max_tokens": 50000, "max_searches": 0, "max_wall_seconds": 1800}
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
  "variant_contract_sha256": "hash embedded in the arm dispatch",
  "execution_id": "RUN-OR-BASELINE-ID",
  "engine_version": "exact engine_version from the arm manifest",
  "engine_receipt": {
    "verified_by_host": true,
    "host_invocation_id": "unique host-side invocation id",
    "runner_kind": "GIT_SKILL_SNAPSHOT",
    "engine_version": "exact engine_version from the arm manifest",
    "variant_contract_sha256": "exact arm contract hash",
    "git_commit": "exact pinned commit",
    "entrypoint_sha256": "exact pinned entrypoint hash",
    "orchestrator_sha256": "exact pinned orchestrator hash"
  },
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

Give each arm the same frozen evidence packet and the same maximum Token and wall-clock budget.
External search and filesystem access are forbidden, so `max_searches` must be zero. A run exceeding
any cap is not comparable. Report failed and recovered runs; do not silently drop them.

## What this benchmark cannot prove

The packet is selected and summarized by a curator. Even after evaluator conclusions are removed,
source selection narrows the search space. Therefore `major_path_coverage` is closed-packet reasoning
coverage, not discovery recall. Passing this suite can justify report or reasoning changes; it cannot
justify claims that the system finds more opportunities.

A discovery benchmark must be a separate `FROZEN_CORPUS_DISCOVERY` suite with an as-of searchable
corpus, decoy documents, hidden entity/path labels, retrieval logs, and no live web or host
filesystem access. Score source recall, novel valid paths, false discoveries, and cost independently
from report comprehension. Do not merge the two scopes into one headline metric.

## Frozen-corpus discovery pilot

The persisted `benchmarks/v014-discovery-pilot` suite implements that separate scope. It contains
three as-of cases, three pinned arms, and twenty curator-frozen primary-source extracts mixed across
themes so that irrelevant but plausible documents act as decoys. It is a retrieval-method pilot,
not a full-document corpus, live-web universe test, expected-return test, or alpha claim. The v0.12
and v0.14 arms are `GIT_METHOD_ADAPTER` runs: the host verifies the pinned skill commit,
entrypoint, and orchestrator, then gives the same model a separately hashed one-shot projection of
that method. This compares method projections under one runtime; it does not claim that the full
multi-agent orchestrator executed or that agent-isolation effects were measured.

Research roles receive only the public dispatch plus two host-mediated gateway operations. `corpus_search` returns
metadata and a short snippet; `corpus_read` returns a body only after search exposed that document
ID. The gateway applies the case cutoff date, caps queries and distinct documents, logs every event,
and becomes immutable when its retrieval receipt is finalized. Keep the evaluator-only answer key
outside every research context.

```bash
python3 scripts/discovery_benchmark_harness.py validate-suite \
  --suite benchmarks/v014-discovery-pilot/suite.json
python3 scripts/discovery_benchmark_harness.py verify-variants \
  --suite benchmarks/v014-discovery-pilot/suite.json \
  --source-repo .
python3 scripts/discovery_benchmark_harness.py init-run \
  --suite benchmarks/v014-discovery-pilot/suite.json \
  --case-id ai_power_infrastructure_2025 \
  --variant v0_14 \
  --output-dir /private/tmp/ai-power-v014
python3 scripts/discovery_benchmark_harness.py search \
  --run-dir /private/tmp/ai-power-v014 \
  --query 'data center power interconnection regulation' --limit 5
python3 scripts/discovery_benchmark_harness.py read \
  --run-dir /private/tmp/ai-power-v014 --doc-id DOC-FERC-SUSQUEHANNA
python3 scripts/discovery_benchmark_harness.py finalize-retrieval \
  --run-dir /private/tmp/ai-power-v014
```

The host must mediate those calls rather than exposing the CLI, repository, corpus path, or answer
key to the research model. Store the report, retrieval log, retrieval receipt, host engine receipt,
result, and later blind assessment together. Only after all nine case/variant pairs are complete may
`score` produce a comparison-ready summary.

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
