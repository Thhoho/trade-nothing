#!/usr/bin/env python3
"""Install the controlled skill bundle without touching runtime/user state."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
from pathlib import Path

import check_source_sync


MANIFEST_NAME = ".trade-nothing-install-manifest.json"
MANIFEST_SCHEMA = "trade-nothing.install-manifest.v1"


def _safe_target(path):
    target = Path(path).expanduser().absolute()
    if target == Path(target.anchor) or target == Path.home().absolute():
        raise ValueError(f"unsafe install target: {target}")
    if target.exists() and target.is_symlink():
        raise ValueError(f"install target must not be a symlink: {target}")
    return target


def _manifest_entries(source):
    entries = []
    for path in check_source_sync.controlled_files(source):
        entries.append({
            "path": path.relative_to(source).as_posix(),
            "sha256": check_source_sync.digest(path),
        })
    return entries


def _quarantine_root(target, configured=""):
    if configured:
        root = Path(configured).expanduser().absolute()
    else:
        root = Path.home() / ".trade-nothing" / "install-quarantine"
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = hashlib.sha256(str(target).encode("utf-8")).hexdigest()[:10]
    return root / f"{stamp}-{suffix}"


def install_target(source, raw_target, *, quarantine_root="", dry_run=False):
    source = Path(source).expanduser().resolve()
    target = _safe_target(raw_target)
    if source == target:
        raise ValueError("source and install target must differ")
    source_files = check_source_sync.controlled_files(source)
    source_rel = {path.relative_to(source) for path in source_files}
    target_candidates = check_source_sync.controlled_candidates(target)
    stale = sorted(
        (path for path in target_candidates if path.relative_to(target) not in source_rel),
        key=lambda path: path.relative_to(target).as_posix(),
    )
    quarantine = _quarantine_root(target, quarantine_root) if stale else None

    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)
        for old in stale:
            rel = old.relative_to(target)
            destination = quarantine / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old), str(destination))
        for src in source_files:
            rel = src.relative_to(source)
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.is_symlink():
                raise ValueError(f"managed destination must not be a symlink: {dst}")
            shutil.copy2(src, dst)
        manifest = {
            "schema_version": MANIFEST_SCHEMA,
            "source": str(source),
            "target": str(target),
            "installed_at": dt.datetime.now(dt.timezone.utc).replace(
                microsecond=0
            ).isoformat(),
            "controlled_files": _manifest_entries(source),
            "quarantined_files": [
                path.relative_to(target).as_posix() for path in stale
            ],
            "quarantine_path": str(quarantine) if quarantine else "",
            "runtime_state_touched": False,
        }
        rendered = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
        temp = target / f"{MANIFEST_NAME}.tmp-{os.getpid()}"
        temp.write_text(rendered, encoding="utf-8")
        os.replace(temp, target / MANIFEST_NAME)
        issues = check_source_sync.compare(source, target)
        if issues:
            raise ValueError("post-install source sync failed: " + "; ".join(issues))

    return {
        "target": str(target),
        "controlled_file_count": len(source_files),
        "quarantined_file_count": len(stale),
        "quarantined_files": [path.relative_to(target).as_posix() for path in stale],
        "quarantine_path": str(quarantine) if quarantine else "",
        "runtime_state_touched": False,
        "dry_run": dry_run,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--targets", nargs="+", required=True)
    parser.add_argument("--quarantine-root", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    source = Path(args.source).expanduser().resolve()
    outcomes = [
        install_target(
            source,
            target,
            quarantine_root=args.quarantine_root,
            dry_run=args.dry_run,
        )
        for target in args.targets
    ]
    print(json.dumps({
        "status": "install_dry_run" if args.dry_run else "install_complete",
        "source": str(source),
        "targets": outcomes,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
