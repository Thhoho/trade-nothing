#!/usr/bin/env python3
"""Phase-1 A/B: turn blind assessor outputs into harness assessment JSONs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUN = REPO / ".runs" / "rebuild-ab-20260813"
RESULTS = RUN / "results"
ASSESSOR_DIR = RUN / "assessors"

CASES = [
    "ai_gpu_bottleneck_2024",
    "eu_ev_tariffs_2024",
    "glp1_value_capture_2024",
    "red_sea_shipping_2024",
    "regional_bank_cre_2024",
    "ai_power_infrastructure_2025",
]


def main() -> int:
    mapping = json.loads((RUN / "assessor-mapping.json").read_text(encoding="utf-8"))
    missing = []
    for case in CASES:
        out = ASSESSOR_DIR / f"{case}.result.json"
        if not out.is_file():
            missing.append(case)
            continue
        scored = json.loads(out.read_text(encoding="utf-8"))
        for label in ("A", "B"):
            variant = mapping[case][label]
            stem = f"{case}__{variant}"
            result = json.loads((RESULTS / f"{stem}.result.json").read_text(encoding="utf-8"))
            metrics = scored[label]
            for field in list(metrics):
                metrics[field] = int(metrics[field])
            assessment = {
                "schema_version": "trade-nothing.benchmark-assessment.v2",
                "case_id": case,
                "variant": variant,
                "blind": True,
                "assessor_id": f"rebuild-ab-20260813/assessor/{case}",
                "artifact_sha256": result["artifact_sha256"],
                "metrics": metrics,
                "exploration_metrics_assessed": True,
                "comprehension_answers": scored.get("comprehension_answers", {}).get(label),
            }
            (RESULTS / f"{stem}.assessment.json").write_text(
                json.dumps(assessment, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    if missing:
        print(f"missing assessor outputs: {missing}")
        return 1
    print("wrote 12 assessment JSONs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
