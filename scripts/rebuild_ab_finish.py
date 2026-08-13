#!/usr/bin/env python3
"""Phase-1 A/B: write result JSONs, randomize blind A/B mapping, build assessor prompts."""
from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUN = REPO / ".runs" / "rebuild-ab-20260813"
RESULTS = RUN / "results"
ASSESSOR_DIR = RUN / "assessors"
SUITE_PATH = REPO / "benchmarks" / "v014-six-case" / "suite-rebuild.json"
KEY_PATH = REPO / "benchmarks" / "v014-six-case" / "assessor" / "answer-key-386d8df.json"
RUBRIC_PATH = REPO / "benchmarks" / "v014-six-case" / "assessor" / "rubric.md"

SUITE = json.loads(SUITE_PATH.read_text(encoding="utf-8"))
KEY = json.loads(KEY_PATH.read_text(encoding="utf-8"))
RUBRIC = RUBRIC_PATH.read_text(encoding="utf-8")

CASES = [c["case_id"] for c in SUITE["cases"]]
VARIANTS = SUITE["variants"]
SUITE_SHA = SUITE["suite_contract_sha256"]

USAGE = {
    "ai_gpu_bottleneck_2024__single_agent": (12876, 39.7),
    "ai_gpu_bottleneck_2024__thin_rebuild": (13049, 100.6),
    "eu_ev_tariffs_2024__single_agent": (12812, 54.2),
    "eu_ev_tariffs_2024__thin_rebuild": (13039, 58.9),
    "glp1_value_capture_2024__single_agent": (12876, 50.2),
    "glp1_value_capture_2024__thin_rebuild": (13102, 59.8),
    "red_sea_shipping_2024__single_agent": (12850, 48.6),
    "red_sea_shipping_2024__thin_rebuild": (13066, 82.2),
    "regional_bank_cre_2024__single_agent": (12945, 52.4),
    "regional_bank_cre_2024__thin_rebuild": (13179, 93.6),
    "ai_power_infrastructure_2025__single_agent": (12908, 61.2),
    "ai_power_infrastructure_2025__thin_rebuild": (13113, 56.1),
}

EXPLORATION_METRICS = {
    "insight_card_total": 0,
    "insight_card_valid": 0,
    "causal_path_total": 0,
    "causal_path_valid": 0,
    "exploration_trace_total": 0,
    "exploration_trace_complete": 0,
    "hypothesis_laundering_count": 0,
    "formal_exploration_action_confusion_count": 0,
}
CORE_METRICS = [
    "decisive_claim_total", "decisive_claim_correct", "false_source_count",
    "major_path_total", "major_path_found", "candidate_count",
    "effective_seed_count", "false_opportunity_count",
    "pricing_anchor_total", "pricing_anchor_valid", "maturity_misread_count",
    "comprehension_question_total", "comprehension_question_correct",
    "manual_edit_count",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_results():
    for case in CASES:
        for variant in VARIANTS:
            stem = f"{case}__{variant}"
            artifact = RESULTS / f"{stem}.artifact.md"
            entry = SUITE["variant_manifest"][variant]
            tokens, wall = USAGE[stem]
            result = {
                "schema_version": "trade-nothing.benchmark-result.v1",
                "case_id": case,
                "variant": variant,
                "suite_contract_sha256": SUITE_SHA,
                "variant_contract_sha256": entry["variant_contract_sha256"],
                "engine_version": entry["engine_version"],
                "engine_receipt": {
                    "runner_kind": "PROMPT_ONLY",
                    "engine_version": entry["engine_version"],
                    "variant_contract_sha256": entry["variant_contract_sha256"],
                    "instruction_sha256": entry["instruction_sha256"],
                    "host_invocation_id": f"rebuild-ab-20260813/{stem}",
                    "verified_by_host": True,
                },
                "completion_status": "COMPLETE",
                "execution_id": f"rebuild-ab-20260813/{stem}",
                "artifact_path": f"{stem}.artifact.md",
                "artifact_sha256": sha(artifact),
                "usage": {
                    "tokens_total": tokens,
                    "search_count": 0,
                    "wall_seconds": round(wall, 1),
                },
                "recovery_count": 0,
            }
            (RESULTS / f"{stem}.result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    print(f"wrote {len(CASES) * len(VARIANTS)} result JSONs")


def build_assessor_prompts():
    ASSESSOR_DIR.mkdir(exist_ok=True)
    mapping = {}
    for case in CASES:
        key_entry = KEY["cases"][case]
        rng = random.Random()
        order = ["single_agent", "thin_rebuild"]
        rng.shuffle(order)
        mapping[case] = {"A": order[0], "B": order[1]}
        paths = {
            "A": RESULTS / f"{case}__{order[0]}.artifact.md",
            "B": RESULTS / f"{case}__{order[1]}.artifact.md",
        }
        prompt = ASSESSOR_DIR / f"{case}.md"
        prompt.write_text(
            f"""# Blind benchmark assessor — case {case}

You score TWO anonymized research reports against the rubric and answer key below.
You do NOT know — and must not try to infer — which research method produced which report.
The labels A/B are random.

Read the rubric, the answer key entry for this case, and the two report files:
- Report A: {paths['A']}
- Report B: {paths['B']}

Procedure:
1. Read each report once, start to finish (~60 seconds each).
2. For EACH report, answer the three comprehension_questions from the key. These test whether a reader who skimmed once recovered the report's actual content — answer strictly from what the report says, correct only if faithful to the report.
3. Count the metrics per the rubric for EACH report. Be adversarial on correctness: a decisive claim is correct only if supported by the frozen packet evidence AND it preserves legal/temporal/adjustment/maturity semantics; a false source is a cited source that does not exist in the packet, post-dates as-of, or does not support the claim; maturity misread = LEAD/WATCHLIST evidence presented as verified recommendation, proposal as final law, planned capacity as delivered, etc.
4. major_path_total is fixed at {len(key_entry['major_paths'])} for BOTH reports.

Output EXACTLY one JSON object and nothing else (no prose, no code fences):

{{
  "A": {{
    "decisive_claim_total": int, "decisive_claim_correct": int, "false_source_count": int,
    "major_path_total": {len(key_entry['major_paths'])}, "major_path_found": int,
    "candidate_count": int, "effective_seed_count": int, "false_opportunity_count": int,
    "pricing_anchor_total": int, "pricing_anchor_valid": int, "maturity_misread_count": int,
    "comprehension_question_total": 3, "comprehension_question_correct": int,
    "manual_edit_count": int,
    "insight_card_total": 0, "insight_card_valid": 0,
    "causal_path_total": 0, "causal_path_valid": 0,
    "exploration_trace_total": 0, "exploration_trace_complete": 0,
    "hypothesis_laundering_count": 0, "formal_exploration_action_confusion_count": 0
  }},
  "B": {{ ...same fields... }},
  "comprehension_answers": {{ "A": ["a1", "a2", "a3"], "B": ["a1", "a2", "a3"] }}
}}

Constraints: candidate_count must be >= effective_seed_count and >= false_opportunity_count;
pricing_anchor_total >= pricing_anchor_valid; decisive_claim_total >= decisive_claim_correct;
comprehension_question_correct <= 3. All values integers.

## Rubric

{RUBRIC}

## Answer key — case {case}

{json.dumps(key_entry, ensure_ascii=False, indent=2)}
""",
            encoding="utf-8",
        )
    (RUN / "assessor-mapping.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("assessor prompts + mapping written")


def main() -> int:
    write_results()
    build_assessor_prompts()
    return 0


if __name__ == "__main__":
    sys.exit(main())
