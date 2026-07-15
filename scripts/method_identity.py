#!/usr/bin/env python3
"""Deterministic identity for the operational Trade Nothing method bundle."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from version import __version__


SCHEMA = "trade-nothing.method-identity.v1"
SCOPE = "operational-bundle.v1"
ROOT = Path(__file__).resolve().parents[1]


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _operational_paths(root=ROOT):
    root = Path(root).resolve()
    paths = [root / "SKILL.md"]
    for folder, suffix in (("agents", ".md"), ("references", ".md"), ("scripts", ".py")):
        for path in (root / folder).glob(f"*{suffix}"):
            if folder == "scripts" and path.name.startswith("test_"):
                continue
            paths.append(path)
    unique = sorted(
        {path.resolve() for path in paths},
        key=lambda path: path.relative_to(root).as_posix(),
    )
    missing = [str(path) for path in unique if not path.is_file()]
    if missing:
        raise ValueError("method identity inputs missing: " + ", ".join(missing))
    return unique


def build_method_identity(root=ROOT):
    root = Path(root).resolve()
    entries = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in _operational_paths(root)
    ]
    contract = {
        "schema_version": SCHEMA,
        "scope": SCOPE,
        "method_version": __version__,
        "files": entries,
    }
    return {
        "schema_version": SCHEMA,
        "scope": SCOPE,
        "method_version": __version__,
        "contract_sha256": hashlib.sha256(
            canonical_json(contract).encode("utf-8")
        ).hexdigest(),
        "file_count": len(entries),
    }


def validate_method_identity(identity, root=ROOT):
    if not isinstance(identity, dict):
        raise ValueError("method_identity must be an object")
    expected = build_method_identity(root)
    if identity != expected:
        raise ValueError(
            "method_contract_drift: pinned identity does not match the current operational bundle"
        )
    return expected


if __name__ == "__main__":
    print(json.dumps(build_method_identity(), ensure_ascii=False, indent=2))
