#!/usr/bin/env python3
"""Regression tests for the radar's explicit persistence boundary."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import logic_radar_v2


class LogicRadarPersistenceTests(unittest.TestCase):
    def _source(self):
        return (
            "### [Radar_002] Rates\n"
            "- **状态**: 🟢 监控中\n\n"
            "[ASSERTION: US_10Y > 4.0 by 2020-01-01]\n\n"
            "## 4. 校准日志 (Calibration Log)\n"
            "记录过去分析的事后验证。对了为什么对，错了为什么错。这是系统学会自我校正的关键。\n\n"
            "（暂无条目——首次使用 `-calibrate` 模式后将自动填充）\n"
        )

    def _values(self):
        return {
            "US_10Y": {
                "value": 5.0,
                "source": "fixture",
                "threshold_status": "🔥 TRIGGERED",
            }
        }

    def test_default_is_read_only_and_explicit_flag_persists(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "Evolution.md"
            original = self._source()
            path.write_text(original, encoding="utf-8")
            with mock.patch.object(
                logic_radar_v2, "get_current_values", return_value=self._values()
            ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                io.StringIO()
            ):
                logic_radar_v2.run_radar(str(path))
            self.assertEqual(path.read_text(encoding="utf-8"), original)

            with mock.patch.object(
                logic_radar_v2, "get_current_values", return_value=self._values()
            ), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                io.StringIO()
            ):
                logic_radar_v2.run_radar(str(path), write_evolution=True)
            updated = path.read_text(encoding="utf-8")
            self.assertIn("🔥 TRIGGERED", updated)
            self.assertIn("[CALIBRATED ✅正确:", updated)


if __name__ == "__main__":
    unittest.main(verbosity=2)
