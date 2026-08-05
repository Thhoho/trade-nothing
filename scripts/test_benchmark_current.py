import json
import tempfile
import unittest
from pathlib import Path

import benchmark_current


REPO_ROOT = Path(__file__).resolve().parent.parent


class BenchmarkCurrentTests(unittest.TestCase):
    def test_pointer_binds_current_method_and_both_suites(self):
        source_repo = (
            None
            if (REPO_ROOT / benchmark_current.INSTALL_MANIFEST.name).is_file()
            else REPO_ROOT
        )
        result = benchmark_current.check_current(source_repo=source_repo)
        self.assertEqual(
            result["status"], "UNBENCHMARKED_METHOD_CHANGE"
        )
        self.assertFalse(result["current_method_calibrated"])
        self.assertEqual(
            result["operational_method_identity"]["method_version"],
            "0.13.0",
        )
        self.assertNotEqual(
            result["operational_method_identity"]["contract_sha256"],
            result["last_calibrated_method_identity"][
                "contract_sha256"
            ],
        )
        self.assertEqual(
            result["last_calibrated_method_identity"][
                "contract_sha256"
            ],
            (
                "5ccad9e79b03f8005bb7c2a72de26d59"
                "f97d541a96b1d820cfbc380c484e96d8"
            ),
        )
        self.assertEqual(result["closed_packet"]["current_variant"], "386d8df")
        self.assertEqual(result["discovery"]["current_variant"], "386d8df")
        self.assertEqual(
            result["source_variant_verification"],
            "NOT_AVAILABLE_IN_INSTALLED_PACKAGE"
            if source_repo is None else "VERIFIED_FROM_GIT",
        )

    def test_package_check_is_explicitly_not_git_verified(self):
        result = benchmark_current.check_current(source_repo=None)
        self.assertEqual(
            result["source_variant_verification"],
            "NOT_AVAILABLE_IN_INSTALLED_PACKAGE",
        )
        self.assertFalse(result["current_method_calibrated"])

    def test_pointer_rejects_method_drift(self):
        pointer = json.loads(
            (REPO_ROOT / "benchmarks" / "current.json").read_text(encoding="utf-8")
        )
        pointer["operational_method_identity"][
            "contract_sha256"
        ] = "0" * 64
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "current.json"
            path.write_text(json.dumps(pointer), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "benchmark_current_drift"):
                benchmark_current.check_current(path)


if __name__ == "__main__":
    unittest.main()
