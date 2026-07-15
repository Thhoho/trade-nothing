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
            "1d68e4ace893ad8e91541af12a8f5da32a9c6b4ac003855dab0395697568107e",
        )
        self.assertEqual(result["closed_packet"]["current_variant"], "48e0366")
        self.assertEqual(result["discovery"]["current_variant"], "48e0366")

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
