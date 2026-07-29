#!/usr/bin/env python3
"""Verify that controlled Trade Nothing source files match installed copies."""
import argparse
import hashlib
from pathlib import Path


ROOT_FILES = (
    "SKILL.md", "README.md", "README_zh.md", "CONTRIBUTING.md",
    "LICENSE", "requirements.txt", "Makefile",
)


def controlled_files(root: Path):
    files = [root / name for name in ROOT_FILES]
    files.extend(sorted((root / "agents").glob("*.md")))
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
    return issues


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True)
    ap.add_argument("--targets", nargs="+", required=True)
    args = ap.parse_args()
    source = Path(args.source).expanduser().resolve()
    issues = []
    for raw in args.targets:
        issues.extend(compare(source, Path(raw).expanduser().resolve()))
    if issues:
        print("SOURCE SYNC FAILED")
        for issue in issues:
            print(f"- {issue}")
        raise SystemExit(2)
    print(f"SOURCE SYNC PASSED: {source} -> {len(args.targets)} target(s)")


if __name__ == "__main__":
    main()
