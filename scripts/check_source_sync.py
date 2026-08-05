#!/usr/bin/env python3
"""Verify that controlled Trade Nothing source files match installed copies."""
import argparse
import hashlib
from pathlib import Path


ROOT_FILES = (
    "SKILL.md", "README.md", "README_zh.md", "CONTRIBUTING.md",
    "LICENSE", "requirements.txt", "Makefile",
)

# Historical execution/sizing surfaces remain under legacy/ for source archaeology only.
# They must never re-enter a framework skill installation.
FORBIDDEN_PUBLISHED_PATHS = frozenset({
    "docs/deepthink2_output_audit_and_iteration_plan_2026-07-12.md",
    "docs/phil_and_position.md",
    "docs/pipeline-audit-v0.12-2026-08-04.md",
    "scripts/excel_model_builder.py",
    "scripts/consensus_distance.py",
    "scripts/data_providers.py",
    "scripts/logic_radar_daemon.py",
    "scripts/portfolio_manager.py",
    "scripts/scenario_matrix.py",
    "scripts/test_data_acquisition.py",
    "scripts/test_integrated_providers.py",
})


def controlled_files(root: Path):
    files = [root / name for name in ROOT_FILES]
    files.extend(sorted((root / "agents").glob("*.md")))
    files.extend(sorted((root / "agents").glob("*.yaml")))
    files.extend(sorted((root / "references").glob("*")))
    files.extend(sorted((root / "docs").glob("*.md")))
    files.extend(sorted((root / "scripts").glob("*.py")))
    files.extend(sorted((root / "benchmarks").glob("**/*")))
    files.extend(
        sorted(
            path
            for path in (root / "assets").glob("**/*")
            if path.name != ".DS_Store"
        )
    )
    controlled = [path for path in files if path.is_file()]
    forbidden = sorted(
        path.relative_to(root).as_posix()
        for path in controlled
        if path.relative_to(root).as_posix() in FORBIDDEN_PUBLISHED_PATHS
    )
    if forbidden:
        raise ValueError(
            "forbidden legacy files entered the published bundle: " + ", ".join(forbidden)
        )
    return controlled


def controlled_candidates(root: Path):
    """Files that can affect the installed operational bundle."""
    if not root.is_dir():
        return []
    files = [root / name for name in ROOT_FILES if (root / name).is_file()]
    files.extend(sorted((root / "agents").glob("*.md")))
    files.extend(sorted((root / "agents").glob("*.yaml")))
    files.extend(sorted((root / "references").glob("*")))
    files.extend(sorted((root / "docs").glob("*.md")))
    files.extend(sorted((root / "scripts").glob("*.py")))
    files.extend(sorted((root / "benchmarks").glob("**/*")))
    files.extend(
        sorted(
            path for path in (root / "assets").glob("**/*")
            if path.name != ".DS_Store"
        )
    )
    return [path for path in files if path.is_file()]


def digest(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def compare(source: Path, target: Path):
    issues = []
    for src in controlled_files(source):
        rel = src.relative_to(source)
        dst = target / rel
        if not dst.is_file():
            issues.append(f"MISSING {target}: {rel}")
        elif digest(src) != digest(dst):
            issues.append(f"DIFF {target}: {rel}")
    expected = {path.relative_to(source) for path in controlled_files(source)}
    for dst in controlled_candidates(target):
        rel = dst.relative_to(target)
        if rel not in expected:
            issues.append(f"EXTRA_CONTROLLED {target}: {rel}")
    return issues


def inert_extra_notes(target: Path):
    notes = []
    if (target / "Methodology_Evolution.md").is_file():
        notes.append(
            f"IGNORED_LEGACY_MEMORY {target}: Methodology_Evolution.md"
        )
    if (target / "scripts" / ".state").exists():
        notes.append(f"IGNORED_LEGACY_STATE {target}: scripts/.state")
    if (target / ".git").exists():
        notes.append(f"PRESERVED_TARGET_METADATA {target}: .git")
    return notes


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True)
    ap.add_argument("--targets", nargs="+", required=True)
    args = ap.parse_args()
    source = Path(args.source).expanduser().resolve()
    issues = []
    notes = []
    for raw in args.targets:
        target = Path(raw).expanduser().resolve()
        issues.extend(compare(source, target))
        notes.extend(inert_extra_notes(target))
    if issues:
        print("SOURCE SYNC FAILED")
        for issue in issues:
            print(f"- {issue}")
        raise SystemExit(2)
    print(f"SOURCE SYNC PASSED: {source} -> {len(args.targets)} target(s)")
    for note in notes:
        print(f"- {note}")


if __name__ == "__main__":
    main()
