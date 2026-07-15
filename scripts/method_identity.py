#!/usr/bin/env python3
"""Deterministic identity for the operational Trade Nothing method bundle."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
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

    names = git_bytes("ls-tree", "-r", "--name-only", commit).decode("utf-8").splitlines()
    paths = sorted(
        path for path in names
        if path == "SKILL.md"
        or (path.startswith("agents/") and path.count("/") == 1 and path.endswith(".md"))
        or (path.startswith("references/") and path.count("/") == 1 and path.endswith(".md"))
        or (
            path.startswith("scripts/")
            and path.count("/") == 1
            and path.endswith(".py")
            and not Path(path).name.startswith("test_")
        )
    )
    if "SKILL.md" not in paths:
        raise ValueError("method identity Git tree is missing SKILL.md")
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
        "schema_version": SCHEMA,
        "scope": SCOPE,
        "method_version": match.group(1),
        "files": entries,
    }
    return {
        "schema_version": SCHEMA,
        "scope": SCOPE,
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
