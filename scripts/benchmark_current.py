#!/usr/bin/env python3
"""Resolve and verify the benchmark suites for the current operational method."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

import benchmark_harness
import discovery_benchmark_harness
from method_identity import build_method_identity


POINTER_SCHEMA = "trade-nothing.benchmark-current.v2"
CALIBRATED = "CALIBRATED_CURRENT_METHOD"
UNBENCHMARKED = "UNBENCHMARKED_METHOD_CHANGE"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POINTER = ROOT / "benchmarks" / "current.json"


def _load_json(path):
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return value


def _bound_path(value, field):
    text = str(value or "").strip()
    pure = PurePosixPath(text)
    if not text or pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"{field} must remain inside the skill root")
    path = (ROOT / text).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"{field} escapes the skill root")
    if not path.is_file():
        raise ValueError(f"{field} is missing: {text}")
    return path


def check_current(pointer_path=DEFAULT_POINTER, source_repo=None):
    pointer_path = Path(pointer_path).resolve()
    pointer = _load_json(pointer_path)
    if pointer.get("schema_version") != POINTER_SCHEMA:
        raise ValueError(f"benchmark pointer schema must be {POINTER_SCHEMA}")
    actual_identity = build_method_identity(ROOT)
    if pointer.get("operational_method_identity") != actual_identity:
        raise ValueError("benchmark_current_drift: pointer does not match operational method")
    calibration_status = pointer.get("calibration_status")
    if calibration_status not in {CALIBRATED, UNBENCHMARKED}:
        raise ValueError("benchmark pointer calibration_status is invalid")
    calibrated_identity = pointer.get("last_calibrated_method_identity")
    if not isinstance(calibrated_identity, dict):
        raise ValueError(
            "benchmark pointer last_calibrated_method_identity is required"
        )
    if calibration_status == CALIBRATED:
        if calibrated_identity != actual_identity:
            raise ValueError(
                "benchmark calibrated pointer must bind the operational method"
            )
    elif calibrated_identity == actual_identity:
        raise ValueError(
            "unbenchmarked method change must differ from last calibration"
        )

    summaries = {}
    configurations = (
        ("closed_packet", benchmark_harness),
        ("discovery", discovery_benchmark_harness),
    )
    for label, harness in configurations:
        entry = pointer.get(label)
        if not isinstance(entry, dict):
            raise ValueError(f"benchmark pointer {label} entry is required")
        if set(entry) != {
            "suite_path", "answer_key_path", "current_variant", "suite_contract_sha256"
        }:
            raise ValueError(f"benchmark pointer {label} fields are invalid")
        suite_path = _bound_path(entry["suite_path"], f"{label}.suite_path")
        answer_key_path = _bound_path(entry["answer_key_path"], f"{label}.answer_key_path")
        raw_suite = harness._load_json(suite_path)
        if label == "closed_packet":
            suite = harness.validate_evidence_files(raw_suite, suite_path)
        else:
            suite = harness.validate_suite(raw_suite, suite_path)
        if suite["suite_contract_sha256"] != entry["suite_contract_sha256"]:
            raise ValueError(f"benchmark pointer {label} suite contract mismatch")
        variant = str(entry["current_variant"] or "")
        contract = suite["variant_manifest"].get(variant)
        if not isinstance(contract, dict):
            raise ValueError(f"benchmark pointer {label} current variant is missing")
        expected_suite_identity = (
            actual_identity
            if calibration_status == CALIBRATED
            else calibrated_identity
        )
        if (
            contract.get("method_contract_sha256")
            != expected_suite_identity.get("contract_sha256")
        ):
            raise ValueError(f"benchmark pointer {label} method identity mismatch")
        answer_key = _load_json(answer_key_path)
        if answer_key.get("suite_id") != suite["suite_id"]:
            raise ValueError(f"benchmark pointer {label} answer key suite mismatch")
        if source_repo is not None:
            harness.verify_git_variants(suite, source_repo)
        summaries[label] = {
            "suite_id": suite["suite_id"],
            "suite_path": str(suite_path),
            "answer_key_path": str(answer_key_path),
            "suite_contract_sha256": suite["suite_contract_sha256"],
            "current_variant": variant,
            "engine_version": contract["engine_version"],
        }
    return {
        "status": calibration_status,
        "operational_method_identity": actual_identity,
        "last_calibrated_method_identity": calibrated_identity,
        "current_method_calibrated": calibration_status == CALIBRATED,
        "benchmark_semantics": (
            "Historical suites remain valid controls for the last calibrated "
            "method; they are not effectiveness evidence for the current "
            "operational method."
            if calibration_status == UNBENCHMARKED
            else "The resolved suites bind the current operational method."
        ),
        **summaries,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the current benchmark pointer")
    parser.add_argument("--pointer", default=str(DEFAULT_POINTER))
    parser.add_argument("--source-repo", help="optional Git repo for pinned snapshot verification")
    args = parser.parse_args()
    if not args.check:
        parser.error("--check is required")
    print(json.dumps(
        check_current(args.pointer, args.source_repo),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
