#!/usr/bin/env python3
"""Release-surface tests for read-only data helpers."""
import os
import unittest
from unittest import mock

import utils
import verified_fetcher


class ProxyBoundaryTests(unittest.TestCase):
    def test_proxy_environment_is_unchanged_without_explicit_opt_in(self):
        with mock.patch.dict(
            os.environ,
            {"HTTPS_PROXY": "http://proxy.invalid", "no_proxy": "localhost"},
            clear=True,
        ):
            self.assertFalse(utils.clean_proxy_env())
            self.assertEqual(os.environ["HTTPS_PROXY"], "http://proxy.invalid")
            self.assertEqual(os.environ["no_proxy"], "localhost")

    def test_explicit_opt_in_disables_proxy(self):
        with mock.patch.dict(
            os.environ,
            {
                "TRADE_NOTHING_DISABLE_PROXY": "1",
                "HTTPS_PROXY": "http://proxy.invalid",
            },
            clear=True,
        ):
            self.assertTrue(utils.clean_proxy_env())
            self.assertNotIn("HTTPS_PROXY", os.environ)
            self.assertEqual(os.environ["no_proxy"], "*")


class ObservationLabelTests(unittest.TestCase):
    def test_market_observation_has_no_numeric_confidence_or_verified_label(self):
        fetcher = verified_fetcher.VerifiedFetcher()
        with mock.patch.object(
            fetcher,
            "_try_yfinance",
            return_value=(22.0, "fixture", "SECONDARY_MARKET_DATA"),
        ):
            result = fetcher.fetch("VIX")
        self.assertNotIn("confidence", result)
        self.assertEqual(result["source_class"], "SECONDARY_MARKET_DATA")
        self.assertEqual(result["status"], "OBSERVED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
