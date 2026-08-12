# Product-value assessment quick guide

Use this only after the same-model single-agent report and the Trade Nothing report are frozen.
The assessor must not know which artifact is which and must not see the material-fact key while
reading. This is a product-value gate, not an Alpha or return test.

## 1. Freeze the evaluator-only key

```json
{
  "schema_version": "trade-nothing.product-value-key.v1",
  "case_id": "stable-case-id",
  "research_question_sha256": "64 lowercase hex characters",
  "as_of_date": "2026-08-12",
  "material_facts": [
    {
      "fact_id": "F-01",
      "weight": 5,
      "claim": "The dated fact that would change the decision.",
      "date": "2026-08-01",
      "source_url": "https://issuer.example/announcement.pdf",
      "decision_effect": "What conclusion, carrier, timing, or risk this changes."
    }
  ]
}
```

Every material fact needs a dated concrete source and a decision effect. Keep this file outside
both research contexts.

## 2. Assess both frozen artifacts

Use the same `assessor_id` and comparison contract for both files. The host may add `variant` and
the artifact hash after the blind assessor has returned the metrics.

```json
{
  "schema_version": "trade-nothing.product-value-assessment.v1",
  "case_id": "stable-case-id",
  "variant": "single_agent",
  "blind": true,
  "artifact_sha256": "64 lowercase hex characters",
  "assessor_id": "blind-reviewer-1",
  "comparison_contract": {
    "model": "gpt-5.6-sol/high",
    "research_question_sha256": "same hash as the key",
    "as_of_date": "2026-08-12",
    "tool_profile": "same live-web and market-data access",
    "max_tokens": 1000000,
    "max_searches": 40,
    "max_wall_seconds": 3600
  },
  "usage": {
    "total_tokens": 100000,
    "search_count": 20,
    "wall_seconds": 1200
  },
  "metrics": {
    "material_fact_ids_found": ["F-01"],
    "decision_usefulness_score": 80,
    "false_source_count": 0,
    "hypothesis_laundering_count": 0,
    "material_omission_count": 0
  }
}
```

`material_omission_count` must equal the hidden-key facts absent from
`material_fact_ids_found`; the scorer recomputes it and rejects a forged zero. Usefulness is a
number from 0 to 100. Usage may not exceed the frozen budget.

## 3. Score the exact files

```bash
python3 scripts/product_value_benchmark.py \
  --key /secure/key.json \
  --baseline /secure/single-agent-assessment.json \
  --candidate /secure/trade-nothing-assessment.json \
  --baseline-artifact /frozen/single-agent-report.md \
  --candidate-artifact /frozen/trade-nothing-report.md \
  --output /secure/product-value-summary.json
```

The CLI hashes both report files itself. A typed hash, variant label, formal report grade, role
receipt, report length, or candidate count cannot substitute for material-fact recall and blind
decision usefulness.
