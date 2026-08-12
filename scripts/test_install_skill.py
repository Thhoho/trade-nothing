#!/usr/bin/env python3
"""Offline tests for safe, path-robust skill installation."""
import json
import tempfile
import unittest
from pathlib import Path

import check_source_sync
import install_skill
import method_identity


REPO_ROOT = Path(__file__).resolve().parents[1]


class InstallSkillTests(unittest.TestCase):
    def test_upgrade_quarantines_stale_code_but_preserves_runtime_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "framework with spaces" / "trade-nothing"
            (target / "scripts" / ".state").mkdir(parents=True)
            legacy_state = target / "scripts" / ".state" / "live_v2_state.json"
            legacy_state.write_text('{"topic":"preserve"}\n', encoding="utf-8")
            stale_code = target / "scripts" / "retired_engine.py"
            stale_code.write_text("raise RuntimeError('stale')\n", encoding="utf-8")
            stale_portfolio = target / "scripts" / "portfolio_manager.py"
            stale_portfolio.write_text("raise RuntimeError('legacy sizing')\n", encoding="utf-8")
            stale_philosophy = target / "docs" / "phil_and_position.md"
            stale_philosophy.parent.mkdir(parents=True)
            stale_philosophy.write_text("# legacy sizing contract\n", encoding="utf-8")
            legacy_memory = target / "Methodology_Evolution.md"
            legacy_memory.write_text("# user memory\n", encoding="utf-8")

            outcome = install_skill.install_target(
                REPO_ROOT,
                target,
                quarantine_root=root / "quarantine with spaces",
            )

            self.assertEqual(
                outcome["quarantined_files"],
                [
                    "docs/phil_and_position.md",
                    "scripts/portfolio_manager.py",
                    "scripts/retired_engine.py",
                ],
            )
            self.assertFalse(stale_code.exists())
            self.assertFalse(stale_portfolio.exists())
            self.assertFalse(stale_philosophy.exists())
            self.assertTrue(legacy_state.is_file())
            self.assertTrue(legacy_memory.is_file())
            self.assertTrue((target / "tools" / "daily_topic.py").is_file())
            self.assertEqual(check_source_sync.compare(REPO_ROOT, target), [])
            manifest = json.loads(
                (target / install_skill.MANIFEST_NAME).read_text(encoding="utf-8")
            )
            self.assertFalse(manifest["runtime_state_touched"])
            self.assertEqual(
                manifest["method_identity"],
                method_identity.build_method_identity(REPO_ROOT),
            )
            self.assertEqual(
                method_identity.build_method_identity(target),
                method_identity.build_method_identity(REPO_ROOT),
            )
            quarantined = Path(outcome["quarantine_path"]) / "scripts" / "retired_engine.py"
            self.assertTrue(quarantined.is_file())

    def test_published_bundle_excludes_archived_execution_surfaces(self):
        paths = {
            path.relative_to(REPO_ROOT).as_posix()
            for path in check_source_sync.controlled_files(REPO_ROOT)
        }
        self.assertTrue(check_source_sync.FORBIDDEN_PUBLISHED_PATHS.isdisjoint(paths))

    def test_published_bundle_contains_every_method_identity_input(self):
        published = {
            path.relative_to(REPO_ROOT).as_posix()
            for path in check_source_sync.controlled_files(REPO_ROOT)
        }
        operational = {
            path.relative_to(REPO_ROOT).as_posix()
            for path in method_identity._operational_paths(REPO_ROOT)
        }
        self.assertTrue(operational.issubset(published))
        self.assertIn("agents/runtime/research-round.md", published)
        self.assertIn("tools/daily_topic.py", published)


if __name__ == "__main__":
    unittest.main(verbosity=2)
