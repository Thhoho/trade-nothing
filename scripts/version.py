"""Centralized version and semantic-surface audit for Trade Nothing."""
from __future__ import annotations

import json
import re
from pathlib import Path


__version__ = "0.13.1"


def _surface_contracts(version):
    tag = f"v{version}"
    return {
        "SKILL.md": [
            f"# Trade Nothing {tag} — The Sovereign Alpha Hunter",
            f"Crux-Based Adversarial Pipeline ({tag}, recommended)",
            f"*Trade Nothing {tag} — Hunt Alpha, Not Consensus.*",
        ],
        "README.md": [
            f"docs/release-{tag}.md",
            f"## {tag}: hypothesis-led, time-bounded research",
            f"**Calibration status:** {tag} is implemented",
            "v0.10 foundation design",
        ],
        "README_zh.md": [
            f"docs/release-{tag}.md",
            f"## {tag}：假说驱动、时间有界的研究",
            f"**校准状态：** {tag} 已实现",
            "v0.10 基础设计",
        ],
        "CONTRIBUTING.md": [
            f"The current source version is `{tag}`.",
            "preserve explicit historical versions",
        ],
        f"docs/release-{tag}.md": [
            f"# Trade Nothing {tag}",
            "`UNBENCHMARKED_METHOD_CHANGE`",
            "historical",
        ],
        "agents/framer.md": [f"# Trade Nothing {tag} — The Framer"],
        "agents/detective.md": [f"# Trade Nothing {tag} — The Detective"],
        "agents/inquisitor.md": [f"# Trade Nothing {tag} — The Inquisitor"],
        "agents/judge.md": [f"# Trade Nothing {tag} — The Judge"],
        "scripts/crux_engine.py": [f"Trade Nothing {tag} — Crux Engine"],
        "scripts/deepthink_orchestrator_v2.py": [
            f"Trade Nothing {tag} — Crux Orchestrator",
            f'Trade Nothing {tag} Crux Orchestrator',
        ],
        "scripts/model_tiers.py": [f"Trade Nothing {tag} — Model Tiering Policy"],
        "scripts/report_v2.py": [
            f"Trade Nothing {tag} — Compact Formal Report Renderer"
        ],
        "scripts/tier1_providers.py": [
            f"Trade Nothing {tag} — Tier-1 Structured Data Providers",
            f'TradeNothing/{version} research',
        ],
    }


def version_consistency_errors(base_dir=None):
    """Return semantic version errors without rewriting historical references."""
    root = (
        Path(base_dir).resolve()
        if base_dir is not None
        else Path(__file__).resolve().parents[1]
    )
    errors = []
    contracts = _surface_contracts(__version__)

    for relative, required_fragments in contracts.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"{relative}: missing current-version surface")
            continue
        text = path.read_text(encoding="utf-8")
        for fragment in required_fragments:
            if fragment not in text:
                errors.append(f"{relative}: missing {fragment!r}")

    target_label = f"Trade Nothing v{__version__}"
    active_label_files = [
        "SKILL.md",
        "agents/framer.md",
        "agents/detective.md",
        "agents/inquisitor.md",
        "agents/judge.md",
        "scripts/crux_engine.py",
        "scripts/deepthink_orchestrator_v2.py",
        "scripts/model_tiers.py",
        "scripts/report_v2.py",
        "scripts/tier1_providers.py",
    ]
    label_pattern = re.compile(r"Trade Nothing v\d+\.\d+(?:\.\d+)?")
    for relative in active_label_files:
        path = root / relative
        if not path.is_file():
            continue
        for found in label_pattern.findall(path.read_text(encoding="utf-8")):
            if found != target_label:
                errors.append(
                    f"{relative}: stale active label {found!r}; expected {target_label!r}"
                )

    benchmark_path = root / "benchmarks/current.json"
    if not benchmark_path.is_file():
        errors.append("benchmarks/current.json: missing method binding")
    else:
        try:
            benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"benchmarks/current.json: invalid JSON: {exc}")
        else:
            operational = benchmark.get("operational_method_identity") or {}
            if operational.get("method_version") != __version__:
                errors.append(
                    "benchmarks/current.json: operational method_version "
                    f"{operational.get('method_version')!r} != {__version__!r}"
                )
            if benchmark.get("calibration_status") != "UNBENCHMARKED_METHOD_CHANGE":
                errors.append(
                    f"benchmarks/current.json: v{__version__} must retain the honest "
                    "UNBENCHMARKED_METHOD_CHANGE status until recalibrated"
                )

    historical_doc = root / "docs/hypothesis-led-research-v0.10.md"
    if not historical_doc.is_file():
        errors.append(
            "docs/hypothesis-led-research-v0.10.md: historical design must be retained"
        )
    validator_path = root / "scripts/validate_report_v2.py"
    if (
        validator_path.is_file()
        and 'state_bound_md.startswith("# Trade Nothing v0.10")'
        not in validator_path.read_text(encoding="utf-8")
    ):
        errors.append(
            "scripts/validate_report_v2.py: legacy v0.10 audit-view compatibility "
            "must remain explicit"
        )

    return errors


def check_version_consistency(base_dir=None):
    """Fail when a current-version surface drifts while preserving historical versions."""
    errors = version_consistency_errors(base_dir)
    if errors:
        print("❌ [ERROR] Version semantic inconsistencies detected:")
        for error in errors:
            print(f"   - {error}")
        raise ValueError("Version semantic consistency check failed!")
    print(
        "✅ [SUCCESS] Version semantic consistency check passed "
        f"for v{__version__}; historical versions preserved."
    )


if __name__ == "__main__":
    check_version_consistency()
