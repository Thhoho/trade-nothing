#!/usr/bin/env python3
"""Regression tests for current-versus-historical version semantics."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import version


ROOT = Path(__file__).resolve().parents[1]


def _copy_semantic_fixture(destination):
    required = set(version._surface_contracts(version.__version__))
    required.update(
        {
            "benchmarks/current.json",
            "docs/hypothesis-led-research-v0.10.md",
            "scripts/validate_report_v2.py",
        }
    )
    for relative in sorted(required):
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


class VersionSemanticTests(unittest.TestCase):
    def test_current_repository_passes_semantic_audit(self):
        self.assertEqual(version.version_consistency_errors(ROOT), [])

    def test_stale_active_label_fails_without_rewriting_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp)
            _copy_semantic_fixture(fixture)
            judge = fixture / "agents/judge.md"
            judge.write_text(
                judge.read_text(encoding="utf-8").replace(
                    f"Trade Nothing v{version.__version__}", "Trade Nothing v0.10", 1
                ),
                encoding="utf-8",
            )
            errors = version.version_consistency_errors(fixture)
            self.assertTrue(
                any("agents/judge.md: stale active label" in error for error in errors),
                errors,
            )
            historical = fixture / "docs/hypothesis-led-research-v0.10.md"
            self.assertTrue(historical.is_file())

    def test_benchmark_binding_uses_current_method_version(self):
        current = json.loads(
            (ROOT / "benchmarks/current.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            current["operational_method_identity"]["method_version"],
            version.__version__,
        )
        self.assertEqual(
            current["calibration_status"],
            "UNBENCHMARKED_METHOD_CHANGE",
        )

    def test_readmes_publish_safe_agent_install_contract(self):
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README_zh.md").read_text(encoding="utf-8")
        tag = f"v{version.__version__}"

        for fragment in (
            "Natural-language installation for an agent",
            "Do not start a research run",
            f"git clone --branch {tag} --depth 1",
            f"git cat-file -t {tag}",
            f"git rev-parse '{tag}^{{commit}}'",
            "scripts/install_skill.py --source <checkout> --targets <target>",
            'make install DEV_DIR="<checkout>"',
        ):
            self.assertIn(fragment, english)

        for fragment in (
            "在 Agent 中用自然语言安装",
            "不要启动任何研究 run",
            f"git clone --branch {tag} --depth 1",
            f"git cat-file -t {tag}",
            f"git rev-parse '{tag}^{{commit}}'",
            "scripts/install_skill.py --source <checkout> --targets <target>",
            'make install DEV_DIR="<checkout>"',
        ):
            self.assertIn(fragment, chinese)

        for stale_command in (
            "make test-live",
            "python3 -m pip install -r requirements.txt",
        ):
            self.assertNotIn(stale_command, english)
            self.assertNotIn(stale_command, chinese)


if __name__ == "__main__":
    unittest.main(verbosity=2)
