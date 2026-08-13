#!/usr/bin/env python3
"""Deterministic identity for the operational Trade Nothing method bundle."""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

from version import __version__


SCHEMA = "trade-nothing.method-identity.v1"
SCOPE = "operational-bundle.v2"
ROOT = Path(__file__).resolve().parents[1]

# The method identity is an allowlist, not a checksum of the repository.  Historical
# engines remain readable in source control but cannot silently become part of a new
# run merely because a .py or .md file exists beside the active kernel.
ACTIVE_METHOD_PATHS = (
    "SKILL.md",
    "references/research-loop-contract.md",
    "scripts/version.py",
    "scripts/method_identity.py",
    "scripts/research_core.py",
    "scripts/research_loop.py",
    "scripts/research_report.py",
    "scripts/free_market_observations.py",
    "scripts/market_snapshot_adapter.py",
    "scripts/research_market_input.py",
    "scripts/research_registry.py",
    "scripts/research_io.py",
    "scripts/process_control.py",
)


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _operational_paths(root=ROOT):
    root = Path(root).resolve()
    unique = [root / relative for relative in ACTIVE_METHOD_PATHS]
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


def build_method_identity_from_git(repo, commit):
    """Rebuild an operational-bundle identity from an immutable Git tree."""
    repo = Path(repo).resolve()
    commit = str(commit or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("method identity Git commit must be a full sha")

    def git_bytes(*args):
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise ValueError("cannot read method identity Git tree: " + detail)
        return completed.stdout

    names = set(
        git_bytes("ls-tree", "-r", "--name-only", commit).decode("utf-8").splitlines()
    )
    identity_source = git_bytes("show", f"{commit}:scripts/method_identity.py").decode(
        "utf-8"
    )
    parsed = ast.parse(identity_source)
    assignments = {}
    for node in parsed.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id in {
            "SCHEMA", "SCOPE", "ACTIVE_METHOD_PATHS"
        }:
            try:
                assignments[target.id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    commit_schema = str(assignments.get("SCHEMA") or SCHEMA)
    commit_scope = str(assignments.get("SCOPE") or "operational-bundle.v1")
    if commit_scope == "operational-bundle.v2":
        configured_paths = assignments.get("ACTIVE_METHOD_PATHS")
        if not isinstance(configured_paths, (tuple, list)) or not configured_paths:
            raise ValueError("method identity Git tree has no active allowlist")
        paths = [str(path) for path in configured_paths]
    else:
        # Reproduce the pre-v0.17 operational-bundle.v1 rule from the immutable
        # tree. Historical benchmark identity must not be reinterpreted through
        # today's allowlist.
        paths = sorted(
            path for path in names
            if path == "SKILL.md"
            or (
                path.startswith("agents/")
                and (path.endswith(".md") or path.endswith(".yaml"))
            )
            or (path.startswith("references/") and path.endswith(".md"))
            or (
                path.startswith("scripts/")
                and path.endswith(".py")
                and not Path(path).name.startswith("test_")
            )
        )
    missing = sorted(set(paths) - names)
    if missing:
        raise ValueError(
            "method identity Git tree is missing active inputs: " + ", ".join(missing)
        )
    version_text = git_bytes("show", f"{commit}:scripts/version.py").decode("utf-8")
    match = re.search(r'^__version__\s*=\s*["\'](\d+\.\d+\.\d+)["\']', version_text, re.M)
    if not match:
        raise ValueError("method identity Git tree has no valid __version__")
    entries = [
        {
            "path": path,
            "sha256": hashlib.sha256(git_bytes("show", f"{commit}:{path}")).hexdigest(),
        }
        for path in paths
    ]
    contract = {
        "schema_version": commit_schema,
        "scope": commit_scope,
        "method_version": match.group(1),
        "files": entries,
    }
    return {
        "schema_version": commit_schema,
        "scope": commit_scope,
        "method_version": match.group(1),
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
