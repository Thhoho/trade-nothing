#!/usr/bin/env python3
"""One-off Phase-1 A/B setup: derive a two-arm suite from the frozen v014 six-case suite.

Arms:
  * single_agent  — official PROMPT_ONLY baseline (arms/single_agent.md), untouched;
  * thin_rebuild  — Trade Nothing rebuild constitution, closed-packet mode
                    (rebuild/arms/closed-packet.md, copied into the suite arms dir).

All contract hashes are recomputed by the harness's own validate_suite; nothing is
hand-rolled. The frozen original suite-386d8df.json is never modified.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SUITE_DIR = REPO / "benchmarks" / "v014-six-case"
SOURCE_SUITE = SUITE_DIR / "suite-386d8df.json"
TARGET_SUITE = SUITE_DIR / "suite-rebuild.json"
ARM_SOURCE = REPO / "rebuild" / "arms" / "closed-packet.md"
ARM_TARGET = SUITE_DIR / "arms" / "closed-packet-thin.md"


def main() -> int:
    shutil.copyfile(ARM_SOURCE, ARM_TARGET)
    arm_sha = hashlib.sha256(ARM_TARGET.read_bytes()).hexdigest()

    suite = json.loads(SOURCE_SUITE.read_text(encoding="utf-8"))
    baseline = suite["variant_manifest"]["single_agent"]
    thin_entry = {
        "runner_kind": "PROMPT_ONLY",
        "engine_version": f"prompt:{arm_sha}",
        "instruction_path": "arms/closed-packet-thin.md",
        "instruction_sha256": arm_sha,
    }

    derived = {
        **suite,
        "suite_id": "rebuild-ab-386d8df",
        "variants": ["single_agent", "thin_rebuild"],
        "variant_manifest": {
            "single_agent": baseline,
            "thin_rebuild": thin_entry,
        },
        "candidate_variant": "thin_rebuild",
    }

    from benchmark_harness import validate_suite  # harness normalizes all hashes

    normalized = validate_suite(derived)
    TARGET_SUITE.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"arm copied: {ARM_TARGET.name} sha256={arm_sha}")
    print(f"suite written: {TARGET_SUITE.name}")
    print(f"suite_contract_sha256: {normalized['suite_contract_sha256']}")
    for variant in normalized["variants"]:
        entry = normalized["variant_manifest"][variant]
        print(f"  {variant}: engine={entry['engine_version']} "
              f"contract={entry['variant_contract_sha256'][:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
