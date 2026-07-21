import json
import tempfile
import unittest
from pathlib import Path

import benchmark_current


REPO_ROOT = Path(__file__).resolve().parent.parent


class BenchmarkCurrentTests(unittest.TestCase):
    def test_pointer_binds_current_method_and_both_suites(self):
        result = benchmark_current.check_current(source_repo=REPO_ROOT)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(
            result["method_identity"]["contract_sha256"],
            "0e9804b64748aa47f6cfe9d67c7ec9a7f58de77507932e832858d9c5fd173752",
        )
        self.assertEqual(result["closed_packet"]["current_variant"], "c768f81")
        self.assertEqual(result["discovery"]["current_variant"], "c768f81")

    def test_pointer_rejects_method_drift(self):
        pointer = json.loads(
            (REPO_ROOT / "benchmarks" / "current.json").read_text(encoding="utf-8")
        )
        pointer["method_identity"]["contract_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "current.json"
            path.write_text(json.dumps(pointer), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "benchmark_current_drift"):
                benchmark_current.check_current(path)


if __name__ == "__main__":
    unittest.main()
