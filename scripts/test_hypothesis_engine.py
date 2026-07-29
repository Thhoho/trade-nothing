#!/usr/bin/env python3
"""Offline regression tests for the non-promotional hypothesis ledger."""

import copy
import math
import unittest

import hypothesis_engine


ARCHETYPES = [
    "DIRECT_CAPTURE",
    "BOTTLENECK_OWNER",
    "ENABLER_OR_INPUT",
    "SUBSTITUTE_OR_AVOIDANCE",
    "ADVERSE_EXPOSURE",
]


def citation(
    domain="alpha.org",
    path="proxy-observation",
    claim="Observed proxy moved before the reported bottleneck.",
    source="Alpha Research Institute",
):
    return {
        "claim": claim,
        "number": "17%",
        "source": source,
        "url": f"https://research.{domain}/reports/{path}",
        "date": "2026-07-09",
        "source_tier": "primary",
    }


def proxy(
    direction="SUPPORTS",
    evidence=None,
    observation="Qualification lead time expands",
    causal_link="Longer qualification delays supply and transfers value",
    **overrides,
):
    item = {
        "proxy": observation,
        "causal_link": causal_link,
        "direction": direction,
        "checkpoint": "next customer qualification update",
    }
    if evidence is not None:
        item["evidence"] = evidence
    item.update(overrides)
    return item


def spark(
    statement="Qualification, not capacity, becomes the binding constraint",
    **overrides,
):
    item = {
        "hypothesis": statement,
        "why_nonconsensus": (
            "Consensus tracks announced capacity rather than qualification time"
        ),
        "causal_chain": [
            "capacity is announced",
            "qualification remains slow",
            "deliverable supply stays scarce",
        ],
        "strongest_alternative_explanation": (
            "The lead-time change is ordinary quarterly mix noise"
        ),
        "value_transfer": "scarcity rent moves to qualified substitutes",
        "falsifier": "qualification lead time falls while repeat orders broaden",
        "catalyst": "customer qualification update",
        "payoff": {
            "upside": 60,
            "downside": 20,
            "unit": "PERCENT_MAGNITUDE",
        },
    }
    item.update(overrides)
    return item


def wild_hypothesis(index, archetype):
    return {
        "hypothesis_id": f"H{index}",
        "origin": "FRAMER",
        "path_id": f"L{index}",
        "linked_crux_id": "C1",
        "archetype": archetype,
        "hypothesis": f"Conditional value-transfer mechanism {index}",
        "hypothesis_status": "HYPOTHESIS_ONLY",
        "why_nonconsensus": f"Ordinary model omits mechanism {index}",
        "surprise_if_true": f"Opportunity map changes through path {index}",
        "strongest_alternative_explanation": (
            f"Ordinary cyclical variation explains mechanism {index}"
        ),
        "scenario_paths": {
            "bull": f"Mechanism {index} compounds",
            "base": f"Mechanism {index} remains ordinary",
            "bear": f"Mechanism {index} fails",
        },
        "value_transfer_chain": [
            "demand shock",
            f"constraint {index}",
            f"economic capture {index}",
            f"asset outcome {index}",
        ],
        "value_transfer": f"Economic rent moves through path {index}",
        "economic_capture_test": f"Observe realized unit economics {index}",
        "pricing_question": f"Is path {index} priced as of the frame date?",
        "cheap_discriminating_test": f"Check primary route {index}",
        "proxy_plan": [{
            "proxy": f"Observable proxy {index}",
            "why_diagnostic": f"Separates mechanism {index} from noise",
            "publisher_class": "REGULATOR_OR_OFFICIAL_DATASET",
            "bounded_query": f"primary bounded query {index}",
        }],
        "catalyst": f"Review checkpoint {index}",
        "expiry_date": "2026-12-31",
        "payoff": {
            "upside": None,
            "downside": None,
            "unit": "UNSPECIFIED_SAME_UNIT",
        },
        "falsifier": f"Observed result falsifies path {index}",
        "search_queries": [
            f"primary source query {index} a",
            f"primary source query {index} b",
        ],
    }


def garden():
    return [
        wild_hypothesis(index, archetype)
        for index, archetype in enumerate(ARCHETYPES, start=1)
    ]


def frame(intent="HYBRID", hypotheses=None):
    return {
        "research_intent": intent,
        "candidate_cruxes": [{"id": "C1", "logic_role": "OPPORTUNITY_PATH"}],
        "hypothesis_garden": {
            "wild_hypotheses": hypotheses if hypotheses is not None else garden()
        },
    }


def state_from(hypotheses=None, intent="HYBRID"):
    raw = [spark()] if hypotheses is None else hypotheses
    normalized = [
        hypothesis_engine.normalize_wild_hypothesis(
            item,
            source_agent="detective",
            round_num=1,
            allow_embedded_proxy_trails=True,
        )["hypothesis"]
        for item in raw
    ]
    ledger = {
        "schema_version": hypothesis_engine.SCHEMA_VERSION,
        "research_intent": intent,
        "garden_source": "TEST_FIXTURE",
        "hypotheses": sorted(
            [item for item in normalized if item],
            key=lambda item: item["hypothesis_id"],
        ),
        "round_audits": [],
        "capability_boundary": copy.deepcopy(
            hypothesis_engine.CAPABILITY_BOUNDARY
        ),
    }
    return {"hypothesis_ledger": ledger}


def only_hypothesis(state):
    return state["hypothesis_ledger"]["hypotheses"][0]


def hypothesis_by_text(state, statement):
    for item in state["hypothesis_ledger"]["hypotheses"]:
        if item["hypothesis"] == statement:
            return item
    raise AssertionError(f"missing hypothesis: {statement}")


def all_keys(value):
    keys = set()
    if isinstance(value, dict):
        keys.update(value)
        for item in value.values():
            keys.update(all_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(all_keys(item))
    return keys


class FrameIntentTests(unittest.TestCase):
    def test_legacy_challenge_frame_remains_optional(self):
        legacy = {
            "question_type": "CAUSAL_CHAIN",
            "candidate_cruxes": [{"id": "C1", "logic_role": "THESIS_HINGE"}],
        }
        self.assertEqual(
            hypothesis_engine.infer_research_intent(legacy),
            "THESIS_CHALLENGE",
        )
        self.assertEqual(hypothesis_engine.validate_frame(legacy), [])
        self.assertIsNone(hypothesis_engine.initialize(legacy))

    def test_legacy_landscape_or_opportunity_path_infers_hybrid(self):
        for legacy in (
            {"landscape_map": {"paths": []}},
            {"hypothesis_garden": {"wild_hypotheses": []}},
            {
                "candidate_cruxes": [
                    {"id": "C1", "logic_role": "OPPORTUNITY_PATH"}
                ]
            },
        ):
            with self.subTest(legacy=legacy):
                self.assertEqual(
                    hypothesis_engine.infer_research_intent(legacy),
                    "HYBRID",
                )
                self.assertIn(
                    "opportunity_intent_requires_hypothesis_garden",
                    hypothesis_engine.validate_frame(legacy),
                )

    def test_question_type_cannot_substitute_for_research_intent(self):
        legacy = {"question_type": "UNIVERSE_SEARCH"}
        self.assertEqual(
            hypothesis_engine.infer_research_intent(legacy),
            "THESIS_CHALLENGE",
        )

    def test_complete_legacy_landscape_map_projects_without_new_field_failures(self):
        paths = []
        for item in garden():
            legacy = copy.deepcopy(item)
            legacy["hypothesis_status"] = "HYPOTHESIS"
            for field in (
                "hypothesis_id",
                "why_nonconsensus",
                "surprise_if_true",
                "scenario_paths",
                "cheap_discriminating_test",
                "proxy_plan",
                "catalyst",
                "expiry_date",
                "payoff",
            ):
                legacy.pop(field, None)
            paths.append(legacy)
        raw = {
            "question_type": "UNIVERSE_SEARCH",
            "candidate_cruxes": [{"id": "C1", "logic_role": "OPPORTUNITY_PATH"}],
            "landscape_map": {"paths": paths},
        }
        self.assertEqual(hypothesis_engine.validate_frame(raw), [])
        ledger = hypothesis_engine.initialize(raw)
        self.assertEqual(ledger["garden_source"], "LEGACY_LANDSCAPE_MAP")
        self.assertEqual(len(ledger["hypotheses"]), 5)
        self.assertEqual(
            {item["state"] for item in ledger["hypotheses"]},
            {"HYPOTHESIS_ONLY"},
        )
        self.assertTrue(
            all(not item["proxy_trails"] for item in ledger["hypotheses"])
        )

    def test_explicit_discovery_requires_garden(self):
        raw = {"research_intent": "OPPORTUNITY_DISCOVERY"}
        self.assertIn(
            "opportunity_intent_requires_hypothesis_garden",
            hypothesis_engine.validate_frame(raw),
        )
        self.assertIsNone(hypothesis_engine.initialize(raw))

    def test_complete_five_path_garden_is_valid_and_starts_untraced(self):
        raw = frame("OPPORTUNITY_DISCOVERY")
        self.assertEqual(hypothesis_engine.validate_frame(raw), [])
        ledger = hypothesis_engine.initialize(raw)
        self.assertEqual(
            {
                item["context"]["origin_crux"]
                for item in ledger["hypotheses"]
            },
            {"C1"},
        )
        self.assertEqual(ledger["research_intent"], "OPPORTUNITY_DISCOVERY")
        self.assertEqual(len(ledger["hypotheses"]), 5)
        self.assertEqual(
            {item["state"] for item in ledger["hypotheses"]},
            {"HYPOTHESIS_ONLY"},
        )
        self.assertTrue(all(item["proxy_plan"] for item in ledger["hypotheses"]))
        self.assertTrue(
            all(not item["proxy_trails"] for item in ledger["hypotheses"])
        )

    def test_frame_rejects_proxy_plan_origin_mismatched_to_hypothesis(self):
        hypotheses = garden()
        hypotheses[0]["proxy_plan"][0]["origin_crux"] = "C2"
        issues = hypothesis_engine.validate_frame(
            frame("OPPORTUNITY_DISCOVERY", hypotheses=hypotheses)
        )
        self.assertIn(
            "wild_hypothesis_1_proxy_plan_1_origin_crux_mismatch",
            issues,
        )

    def test_framer_cannot_preload_observed_proxy_trails(self):
        raw = frame("HYBRID")
        raw["as_of_date"] = "2026-07-20"
        raw["hypothesis_garden"]["wild_hypotheses"][0][
            "proxy_trails"
        ] = [
            proxy(evidence=citation(domain="frame-a.org")),
            proxy(
                observation="Second preloaded observation",
                causal_link="Second preloaded causal link",
                evidence=citation(domain="frame-b.net"),
            ),
        ]
        issues = hypothesis_engine.validate_frame(raw)
        self.assertIn(
            "wild_hypothesis_1_framer_proxy_trails_forbidden",
            issues,
        )
        ledger = hypothesis_engine.initialize(raw)
        first = next(
            item
            for item in ledger["hypotheses"]
            if item["spark_id"] == "H1"
        )
        self.assertEqual(first["state"], "HYPOTHESIS_ONLY")
        self.assertEqual(first["proxy_trails"], [])
        self.assertEqual(
            ledger["initialization_audit"]["rejected_reasons"][
                "frame_embedded_proxy_trails_ignored"
            ],
            2,
        )

    def test_expiry_must_be_iso_and_after_frame_as_of(self):
        raw = frame("HYBRID")
        raw["as_of_date"] = "2026-07-20"
        raw["hypothesis_garden"]["wild_hypotheses"][0][
            "expiry_date"
        ] = "2026-07-20"
        self.assertIn(
            "wild_hypothesis_1_expiry_date_must_follow_as_of",
            hypothesis_engine.validate_frame(raw),
        )
        raw["hypothesis_garden"]["wild_hypotheses"][0][
            "expiry_date"
        ] = "July 2026"
        self.assertIn(
            "wild_hypothesis_1_expiry_date_requires_iso_date",
            hypothesis_engine.validate_frame(raw),
        )

    def test_top_level_alias_is_supported_with_same_strict_contract(self):
        raw = {
            "research_intent": "OPPORTUNITY_DISCOVERY",
            "candidate_cruxes": [{"id": "C1"}],
            "wild_hypotheses": garden(),
        }
        self.assertEqual(hypothesis_engine.validate_frame(raw), [])
        self.assertEqual(len(hypothesis_engine.initialize(raw)["hypotheses"]), 5)

    def test_garden_count_and_archetype_coverage_are_enforced(self):
        raw = frame(hypotheses=garden()[:4])
        issues = hypothesis_engine.validate_frame(raw)
        self.assertIn(
            "hypothesis_garden_requires_5_to_7_hypotheses",
            issues,
        )
        self.assertTrue(
            any(issue.startswith("hypothesis_garden_missing_archetypes:")
                for issue in issues)
        )

    def test_scenarios_chain_proxy_plan_and_queries_are_enforced(self):
        hypotheses = garden()
        broken = hypotheses[0]
        broken["scenario_paths"].pop("bear")
        broken["value_transfer_chain"] = ["shock", "capture"]
        broken["proxy_plan"] = []
        broken["search_queries"] = ["same", "same"]
        issues = hypothesis_engine.validate_frame(frame(hypotheses=hypotheses))
        self.assertIn(
            "wild_hypothesis_1_scenario_paths_missing_bear",
            issues,
        )
        self.assertIn(
            "wild_hypothesis_1_value_transfer_chain_requires_3_to_6_nodes",
            issues,
        )
        self.assertIn(
            "wild_hypothesis_1_proxy_plan_requires_1_to_3_routes",
            issues,
        )
        self.assertIn(
            "wild_hypothesis_1_search_queries_require_exactly_2_distinct",
            issues,
        )

    def test_framer_proxy_plan_needs_no_direction(self):
        self.assertEqual(hypothesis_engine.validate_frame(frame()), [])

    def test_invalid_intent_and_forbidden_authority_are_visible(self):
        hypotheses = garden()
        hypotheses[0]["position_size"] = "25%"
        issues = hypothesis_engine.validate_frame(
            frame("MAKE_MONEY", hypotheses)
        )
        self.assertIn("invalid_research_intent", issues)
        self.assertIn(
            "wild_hypothesis_1_forbidden_field:position_size",
            issues,
        )


class BreakEvenThresholdTests(unittest.TestCase):
    def test_explicit_magnitudes_compute_formula(self):
        result = hypothesis_engine.break_even_threshold(60, 20)
        self.assertEqual(result["status"], "KNOWN")
        self.assertEqual(result["p_star"], 0.25)
        self.assertEqual(result["p_star_percent"], 25.0)
        self.assertIn("not an estimated probability", result["semantics"])

    def test_numeric_strings_are_deterministic(self):
        self.assertEqual(
            hypothesis_engine.break_even_threshold("60.000", "20.0")[
                "p_star"
            ],
            0.25,
        )

    def test_missing_invalid_and_zero_total_are_unknown(self):
        cases = [
            (None, 20, "missing_upside"),
            (-1, 2, "invalid_upside"),
            (math.nan, 2, "invalid_upside"),
            (math.inf, 2, "invalid_upside"),
            (True, 2, "invalid_upside"),
            (0, 0, "zero_total_payoff_magnitude"),
        ]
        for upside, downside, reason in cases:
            with self.subTest(upside=upside, downside=downside):
                result = hypothesis_engine.break_even_threshold(
                    upside, downside
                )
                self.assertEqual(result["status"], "UNKNOWN")
                self.assertIn(reason, result["reason"])

    def test_zero_on_one_side_follows_formula(self):
        self.assertEqual(
            hypothesis_engine.break_even_threshold(0, 20)["p_star"], 1.0
        )
        self.assertEqual(
            hypothesis_engine.break_even_threshold(20, 0)["p_star"], 0.0
        )

    def test_extreme_exponents_fail_closed_without_decimal_exception(self):
        for value in ("1e100", "1e1000000"):
            with self.subTest(value=value):
                result = hypothesis_engine.break_even_threshold(value, 1)
                self.assertEqual(result["status"], "UNKNOWN")
                self.assertIn("out_of_range_upside", result["reason"])

    def test_symmetric_scenario_paths_are_typed_and_bounded(self):
        paths = [
            {
                "path_type": path_type,
                "summary": f"{path_type} summary",
                "trigger_event": f"{path_type} trigger",
                "transmission_chain": "A -> B -> C",
                "timeline": "2026-09 checkpoint",
                "monitor_anchor": f"{path_type} monitor",
                "falsifier": f"{path_type} falsifier",
                "payoff_magnitude": magnitude,
                "payoff_unit": "PERCENT_MAGNITUDE",
                "evidence": [],
            }
            for path_type, magnitude in (
                ("BULL_SURPRISE", 60),
                ("BASE", None),
                ("BEAR_FAILURE", 20),
            )
        ]
        result = hypothesis_engine.normalize_scenario_paths(paths)
        self.assertEqual(result["status"], "VALID")
        self.assertEqual(
            [item["path_type"] for item in result["paths"]],
            list(hypothesis_engine.SCENARIO_PATH_TYPES),
        )
        self.assertEqual(
            result["break_even_threshold"]["p_star_percent"], 25.0
        )

    def test_scenario_bad_date_evidence_is_invalid(self):
        paths = [
            {
                "path_type": path_type,
                "summary": "summary",
                "trigger_event": "trigger",
                "transmission_chain": "A -> B -> C",
                "timeline": "2026-09",
                "monitor_anchor": "monitor",
                "falsifier": "falsifier",
                "payoff_magnitude": None,
                "payoff_unit": "UNSPECIFIED_SAME_UNIT",
                "evidence": (
                    [{**citation(), "date": "not-a-date"}]
                    if path_type == "BASE" else []
                ),
            }
            for path_type in hypothesis_engine.SCENARIO_PATH_TYPES
        ]
        result = hypothesis_engine.normalize_scenario_paths(paths)
        self.assertEqual(result["status"], "INVALID")
        self.assertIn(
            "scenario_path_2_contains_invalid_evidence", result["issues"]
        )

    def test_scenario_payoff_units_compare_case_insensitively(self):
        paths = [
            {
                "path_type": path_type,
                "summary": "summary",
                "trigger_event": "trigger",
                "transmission_chain": "A -> B -> C",
                "timeline": "2026-09",
                "monitor_anchor": "monitor",
                "falsifier": "falsifier",
                "payoff_magnitude": magnitude,
                "payoff_unit": unit,
                "evidence": [],
            }
            for path_type, magnitude, unit in (
                ("BULL_SURPRISE", 60, "USD"),
                ("BASE", None, "USD"),
                ("BEAR_FAILURE", 20, "usd"),
            )
        ]
        result = hypothesis_engine.normalize_scenario_paths(paths)
        self.assertEqual(
            result["break_even_threshold"]["status"], "KNOWN"
        )
        self.assertEqual(
            result["break_even_threshold"]["p_star_percent"], 25.0
        )

    def test_scenario_future_evidence_is_rejected_at_frozen_as_of(self):
        paths = [
            {
                "path_type": path_type,
                "summary": "summary",
                "trigger_event": "trigger",
                "transmission_chain": "A -> B -> C",
                "timeline": "2026-09",
                "monitor_anchor": "monitor",
                "falsifier": "falsifier",
                "payoff_magnitude": None,
                "payoff_unit": "UNSPECIFIED_SAME_UNIT",
                "evidence": (
                    [{**citation(), "date": "2027-01-01"}]
                    if path_type == "BULL_SURPRISE" else []
                ),
            }
            for path_type in hypothesis_engine.SCENARIO_PATH_TYPES
        ]
        result = hypothesis_engine.normalize_scenario_paths(
            paths, as_of_date="2026-07-10"
        )
        self.assertEqual(result["status"], "INVALID")
        self.assertIn(
            "scenario_path_1_evidence_after_as_of", result["issues"]
        )
        self.assertEqual(result["paths"][0]["evidence"], [])


class NormalizationTests(unittest.TestCase):
    def test_submitted_state_cannot_self_promote(self):
        item = hypothesis_engine.normalize_wild_hypothesis(
            spark(state="EVIDENCE_BACKED", status="EVIDENCE_BACKED")
        )["hypothesis"]
        self.assertEqual(item["state"], "HYPOTHESIS_ONLY")

    def test_identifier_is_stable_under_whitespace_and_cosmetic_punctuation(self):
        first = hypothesis_engine.normalize_wild_hypothesis({
            "hypothesis": "Qualification, not capacity, binds."
        })["hypothesis"]
        second = hypothesis_engine.normalize_wild_hypothesis({
            "hypothesis": "  Qualification not capacity binds  "
        })["hypothesis"]
        self.assertEqual(first["hypothesis_id"], second["hypothesis_id"])

    def test_identifier_preserves_meaning_bearing_operators(self):
        pairs = [
            ("gross margin > 20%", "gross margin < 20%"),
            ("A+B drives value", "A-B drives value"),
            ("x/y expands", "x*y expands"),
        ]
        for left, right in pairs:
            with self.subTest(left=left, right=right):
                left_item = hypothesis_engine.normalize_wild_hypothesis(
                    {"hypothesis": left}
                )["hypothesis"]
                right_item = hypothesis_engine.normalize_wild_hypothesis(
                    {"hypothesis": right}
                )["hypothesis"]
                self.assertNotEqual(
                    left_item["hypothesis_id"],
                    right_item["hypothesis_id"],
                )

    def test_identifier_preserves_decimal_and_ratio_punctuation(self):
        pairs = [
            ("Gross margin reaches 1.5%", "Gross margin reaches 15%"),
            ("Odds are 1:5", "Odds are 15"),
        ]
        for left, right in pairs:
            with self.subTest(left=left, right=right):
                left_id = hypothesis_engine.normalize_wild_hypothesis(
                    spark(statement=left)
                )["hypothesis"]["hypothesis_id"]
                right_id = hypothesis_engine.normalize_wild_hypothesis(
                    spark(statement=right)
                )["hypothesis"]["hypothesis_id"]
                self.assertNotEqual(left_id, right_id)

    def test_role_spark_schema_maps_aliases_and_fallback_fields(self):
        raw = {
            "spark_id": "HS-D-1-1",
            "origin_crux": "C1",
            "landscape_path_id": "L1",
            "status": "HYPOTHESIS_ONLY",
            "observation": "Orders rose while announced capacity did not",
            "hypothesis": "Qualification creates a hidden bottleneck",
            "surprise_if_true": "Nominal capacity is the wrong supply metric",
            "causal_chain": "orders -> qualification queue -> scarcity",
            "strongest_alternative_explanation": "Seasonal order batching",
            "disconfirming_observation": "Queue falls without delivery gains",
            "cheap_discriminating_test": "Inspect qualification timestamps",
            "evidence": [],
        }
        item = hypothesis_engine.normalize_wild_hypothesis(
            raw, allow_embedded_proxy_trails=True
        )["hypothesis"]
        self.assertEqual(item["spark_id"], "HS-D-1-1")
        self.assertIn("HS-D-1-1", item["spark_ids"])
        self.assertEqual(item["why_nonconsensus"], raw["surprise_if_true"])
        self.assertEqual(item["falsifier"], raw["disconfirming_observation"])
        self.assertEqual(
            item["causal_chain"],
            ["orders", "qualification queue", "scarcity"],
        )
        self.assertEqual(
            item["strongest_alternative_explanation"],
            "Seasonal order batching",
        )

    def test_role_proxy_schema_defaults_ambiguous_and_preserves_route(self):
        raw = spark(proxy_trails=[{
            "trail_id": "PT-D-1-1",
            "proxy": "Qualification timestamps",
            "why_diagnostic": "Separates true queues from order batching",
            "next_source_class": "CUSTOMER_OR_COUNTERPARTY",
            "bounded_query": "customer qualification timestamps",
            "stop_condition": "No timestamp record exists",
            "evidence": [],
        }])
        item = hypothesis_engine.normalize_wild_hypothesis(
            raw, allow_embedded_proxy_trails=True
        )["hypothesis"]
        trail = item["proxy_trails"][0]
        self.assertEqual(item["state"], "TRACED")
        self.assertEqual(trail["direction"], "AMBIGUOUS")
        self.assertEqual(trail["why_diagnostic"], raw["proxy_trails"][0][
            "why_diagnostic"
        ])
        self.assertEqual(
            trail["next_source_class"],
            "CUSTOMER_OR_COUNTERPARTY",
        )

    def test_public_frame_normalizer_ignores_embedded_proxy_trails(self):
        result = hypothesis_engine.normalize_wild_hypothesis(
            spark(proxy_trails=[proxy(evidence=citation())])
        )
        self.assertEqual(
            result["hypothesis"]["state"], "HYPOTHESIS_ONLY"
        )
        self.assertEqual(result["hypothesis"]["proxy_trails"], [])
        self.assertEqual(
            result["audit"]["rejected_reasons"][
                "frame_embedded_proxy_trails_ignored"
            ],
            1,
        )

    def test_one_evidenced_trail_remains_traced(self):
        item = hypothesis_engine.normalize_wild_hypothesis(
            spark(proxy_trails=[proxy(evidence=citation())]),
            allow_embedded_proxy_trails=True,
        )["hypothesis"]
        self.assertEqual(item["state"], "TRACED")
        self.assertEqual(
            item["maturity_basis"]["evidence_bearing_proxy_trail_count"],
            1,
        )

    def test_two_trails_from_same_publisher_remain_traced(self):
        item = hypothesis_engine.normalize_wild_hypothesis(
            spark(
                proxy_trails=[
                    proxy(evidence=citation(path="one")),
                    proxy(
                        observation="Customer acceptance cadence",
                        causal_link=(
                            "Acceptance cadence tests qualification scarcity"
                        ),
                        evidence=citation(path="two"),
                    ),
                ],
            ),
            allow_embedded_proxy_trails=True,
        )["hypothesis"]
        self.assertEqual(item["state"], "TRACED")
        self.assertEqual(
            item["maturity_basis"]["independent_publisher_domain_count"],
            1,
        )

    def test_two_trails_two_domains_and_alternative_are_evidence_backed(self):
        item = hypothesis_engine.normalize_wild_hypothesis(
            spark(
                proxy_trails=[
                    proxy(evidence=citation(domain="alpha.org")),
                    proxy(
                        direction="CONTRADICTS",
                        observation="Customer acceptance cadence",
                        causal_link=(
                            "Acceptance cadence tests qualification scarcity"
                        ),
                        evidence=citation(
                            domain="beta.net",
                            claim="Acceptance cadence accelerated.",
                            source="Beta Standards Lab",
                        ),
                    ),
                ],
            ),
            allow_embedded_proxy_trails=True,
        )["hypothesis"]
        self.assertEqual(item["state"], "EVIDENCE_BACKED")
        basis = item["maturity_basis"]
        self.assertEqual(basis["evidence_bearing_proxy_trail_count"], 2)
        self.assertEqual(basis["independent_publisher_domain_count"], 2)

    def test_same_planned_diagnostic_cannot_fake_second_maturity_trail(self):
        item = hypothesis_engine.normalize_wild_hypothesis(
            spark(
                proxy_trails=[
                    proxy(
                        observation="Observed value rose 10%",
                        planned_proxy="Frozen diagnostic slot A",
                        causal_link="Frozen causal diagnostic A",
                        evidence=citation(domain="alpha.org"),
                    ),
                    proxy(
                        observation="Observed value rose 12%",
                        planned_proxy="Frozen diagnostic slot A",
                        causal_link="Frozen causal diagnostic A",
                        evidence=citation(domain="beta.net"),
                    ),
                ],
            ),
            allow_embedded_proxy_trails=True,
        )["hypothesis"]
        self.assertEqual(item["state"], "TRACED")
        self.assertEqual(
            item["maturity_basis"][
                "evidence_bearing_proxy_trail_count"
            ],
            1,
        )
        self.assertEqual(
            item["maturity_basis"][
                "independent_publisher_domain_count"
            ],
            2,
        )

    def test_missing_alternative_blocks_evidence_backed_state(self):
        raw = spark(
            strongest_alternative_explanation="",
            proxy_trails=[
                proxy(evidence=citation(domain="alpha.org")),
                proxy(
                    observation="Customer acceptance cadence",
                    causal_link="Acceptance cadence tests qualification scarcity",
                    evidence=citation(domain="beta.net"),
                ),
            ],
        )
        item = hypothesis_engine.normalize_wild_hypothesis(
            raw, allow_embedded_proxy_trails=True
        )["hypothesis"]
        self.assertEqual(item["state"], "TRACED")
        self.assertFalse(
            item["maturity_basis"][
                "strongest_alternative_explanation_preserved"
            ]
        )

    def test_shared_citation_gate_rejects_placeholder_homepage_and_wrapper(self):
        invalid_urls = [
            "https://example.com/reports/fake",
            "https://alpha.org/",
            "https://www.google.com/url?q=https://alpha.org/reports/one",
            (
                "https://vertexaisearch.cloud.google.com/"
                "grounding-api-redirect/abc"
            ),
        ]
        for url in invalid_urls:
            with self.subTest(url=url):
                invalid = citation()
                invalid["url"] = url
                result = hypothesis_engine.normalize_wild_hypothesis(
                    spark(proxy_trails=[proxy(evidence=invalid)]),
                    allow_embedded_proxy_trails=True,
                )
                self.assertEqual(result["hypothesis"]["state"], "TRACED")
                self.assertEqual(
                    result["hypothesis"]["proxy_trails"][0]["evidence"],
                    [],
                )
                self.assertEqual(
                    result["audit"]["rejected_reasons"][
                        "proxy_evidence_invalid_url"
                    ],
                    1,
                )

    def test_duplicate_proxy_and_evidence_are_deduplicated(self):
        cited = citation()
        raw = spark(proxy_trails=[
            proxy(evidence=[cited, copy.deepcopy(cited)]),
            proxy(direction="CONTRADICTS", evidence=cited),
        ])
        result = hypothesis_engine.normalize_wild_hypothesis(
            raw, allow_embedded_proxy_trails=True
        )
        item = result["hypothesis"]
        self.assertEqual(len(item["proxy_trails"]), 1)
        self.assertEqual(len(item["proxy_trails"][0]["evidence"]), 1)
        self.assertEqual(item["proxy_trails"][0]["direction"], "AMBIGUOUS")
        self.assertTrue(
            item["proxy_trails"][0]["direction_contested"]
        )
        self.assertEqual(
            {
                binding["direction"]
                for binding in item["proxy_trails"][0][
                    "direction_bindings"
                ]
            },
            {"SUPPORTS", "CONTRADICTS"},
        )
        self.assertEqual(result["audit"]["duplicate_proxy_trails"], 1)
        self.assertGreaterEqual(result["audit"]["duplicate_evidence"], 1)

    def test_forbidden_spark_is_not_normalized(self):
        result = hypothesis_engine.normalize_wild_hypothesis(
            spark(trade_action="BUY")
        )
        self.assertIsNone(result["hypothesis"])
        self.assertEqual(
            result["audit"]["rejected_reasons"][
                "hypothesis_spark_forbidden_field:trade_action"
            ],
            1,
        )


class RoundIngestionTests(unittest.TestCase):
    def test_future_proxy_evidence_cannot_raise_maturity(self):
        state = state_from()
        state["hypothesis_ledger"]["as_of_date"] = "2026-07-10"
        hypothesis_id = state["hypothesis_ledger"]["hypotheses"][0][
            "hypothesis_id"
        ]
        future = {**citation(), "date": "2027-01-01"}
        audit = hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "proxy_trails": [
                    {
                        "hypothesis_id": hypothesis_id,
                        **proxy(
                            observation="First future proxy",
                            causal_link="First future causal diagnostic",
                            evidence=[future],
                        ),
                    },
                    {
                        "hypothesis_id": hypothesis_id,
                        **proxy(
                            observation="Second future proxy",
                            causal_link="Second future causal diagnostic",
                            evidence=[{
                                **future,
                                "url": (
                                    "https://research.beta.net/"
                                    "reports/future-proxy"
                                ),
                            }],
                        ),
                    },
                ]
            },
            inquisitor={},
        )
        self.assertEqual(
            audit["rejected_reasons"]["proxy_evidence_after_as_of"], 2
        )
        self.assertEqual(audit["accepted_evidence"], 0)
        hypothesis = state["hypothesis_ledger"]["hypotheses"][0]
        self.assertEqual(hypothesis["state"], "TRACED")
        self.assertEqual(
            hypothesis["maturity_basis"][
                "evidence_bearing_proxy_trail_count"
            ],
            0,
        )

    def test_same_month_imprecise_date_fails_closed_before_month_end(self):
        state = state_from()
        state["hypothesis_ledger"]["as_of_date"] = "2026-07-10"
        hypothesis_id = state["hypothesis_ledger"]["hypotheses"][0][
            "hypothesis_id"
        ]
        monthly = {**citation(), "date": "2026-07"}
        audit = hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "proxy_trails": [{
                    "hypothesis_id": hypothesis_id,
                    **proxy(evidence=[monthly]),
                }]
            },
            inquisitor={},
        )
        self.assertEqual(
            audit["rejected_reasons"]["proxy_evidence_after_as_of"], 1
        )
        self.assertEqual(audit["accepted_evidence"], 0)

    def test_empty_host_scope_rejects_all_new_hypothesis_sparks(self):
        state = state_from()
        state["cruxes"] = {"C1": {}}
        before = len(state["hypothesis_ledger"]["hypotheses"])
        audit = hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "hypothesis_sparks": [
                    spark(
                        statement="Out-of-dispatch hypothesis",
                        origin_crux="C1",
                    )
                ]
            },
            inquisitor={},
            allowed_crux_ids=[],
        )
        self.assertEqual(
            len(state["hypothesis_ledger"]["hypotheses"]), before
        )
        self.assertEqual(
            audit["rejected_reasons"][
                "detective_hypothesis_spark_unknown_origin_crux"
            ],
            1,
        )

    def test_unknown_origin_is_rejected_inside_nonempty_host_scope(self):
        state = state_from()
        state["cruxes"] = {"C1": {}}
        audit = hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "hypothesis_sparks": [
                    spark(
                        statement="Unknown-origin hypothesis",
                        origin_crux="C9",
                    )
                ]
            },
            inquisitor={},
            allowed_crux_ids=["C1"],
        )
        self.assertEqual(
            audit["rejected_reasons"][
                "detective_hypothesis_spark_unknown_origin_crux"
            ],
            1,
        )

    def test_new_spark_and_standalone_proxy_resolve_by_spark_id_same_payload(self):
        state = state_from()
        statement = "A new counter-mechanism appears"
        payload = {
            "hypothesis_sparks": [{
                "spark_id": "HS-D-1-NEW",
                "origin_crux": "C1",
                "observation": "A physical flow diverged",
                "hypothesis": statement,
                "surprise_if_true": "Value moves to a substitute",
                "causal_chain": "flow -> constraint -> substitution",
                "strongest_alternative_explanation": "Measurement noise",
                "disconfirming_observation": "Flow restates to normal",
                "cheap_discriminating_test": "Check official flow series",
                "evidence": [],
            }],
            "proxy_trails": [{
                "trail_id": "PT-D-1-NEW",
                "spark_id": "HS-D-1-NEW",
                "proxy": "Official physical flow",
                "why_diagnostic": "Separates substitution from measurement noise",
                "next_source_class": "REGULATOR_OR_OFFICIAL_DATASET",
                "bounded_query": "official physical flow series",
                "stop_condition": "Series is discontinued",
                "evidence": [],
            }],
        }
        audit = hypothesis_engine.ingest_round(
            state, 1, detective=payload, inquisitor={}
        )
        item = hypothesis_by_text(state, statement)
        self.assertEqual(item["state"], "TRACED")
        self.assertIn("HS-D-1-NEW", item["spark_ids"])
        self.assertEqual(audit["accepted_new_hypotheses"], 1)
        self.assertEqual(audit["accepted_new_proxy_trails"], 1)

    def test_role_rounds_merge_two_independent_trails_then_replay_dedupes(self):
        state = state_from()
        stored = only_hypothesis(state)
        first = {
            "proxy_trails": [{
                "hypothesis_id": stored["hypothesis_id"],
                **proxy(evidence=citation(domain="alpha.org")),
            }]
        }
        first_audit = hypothesis_engine.ingest_round(
            state, 1, detective=first, inquisitor={}
        )
        self.assertEqual(only_hypothesis(state)["state"], "TRACED")
        self.assertEqual(first_audit["accepted_new_proxy_trails"], 1)

        second = {
            "proxy_trails": [{
                "spark_id": stored["spark_id"],
                **proxy(
                    observation="Customer acceptance cadence",
                    causal_link="Acceptance cadence tests qualification scarcity",
                    evidence=citation(
                        domain="beta.net",
                        claim="Acceptance cadence accelerated.",
                        source="Beta Standards Lab",
                    ),
                ),
            }]
        }
        hypothesis_engine.ingest_round(
            state, 2, detective={}, inquisitor=second
        )
        self.assertEqual(
            only_hypothesis(state)["state"],
            "EVIDENCE_BACKED",
        )
        replay = hypothesis_engine.ingest_round(
            state, 3, detective={}, inquisitor=second
        )
        self.assertEqual(len(only_hypothesis(state)["proxy_trails"]), 2)
        self.assertGreaterEqual(replay["duplicate_evidence"], 1)

    def test_duplicate_round_replay_cannot_reacquire_role_budget(self):
        state = state_from()
        hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "hypothesis_sparks": [
                    spark(statement="First bounded round idea")
                ]
            },
            inquisitor={},
        )
        count = len(state["hypothesis_ledger"]["hypotheses"])
        replay = hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "hypothesis_sparks": [
                    spark(statement="Replay budget bypass")
                ]
            },
            inquisitor={},
        )
        self.assertEqual(
            len(state["hypothesis_ledger"]["hypotheses"]), count
        )
        self.assertEqual(replay["reason"], "round_already_ingested")
        self.assertEqual(
            replay["rejected_reasons"]["duplicate_round_ingest_rejected"],
            1,
        )

    def test_same_diagnostic_across_cruxes_is_one_trace(self):
        state = state_from()
        state["cruxes"] = {"C1": {}, "C2": {}}
        stored = only_hypothesis(state)
        shared = {
            "hypothesis_id": stored["hypothesis_id"],
            "proxy": "Shared diagnostic observation",
            "causal_link": "Tests one identical causal link",
            "direction": "SUPPORTS",
        }
        hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "proxy_trails": [{
                    **shared,
                    "origin_crux": "C1",
                    "evidence": citation(domain="alpha.org"),
                }]
            },
            inquisitor={
                "proxy_trails": [{
                    **shared,
                    "origin_crux": "C2",
                    "evidence": citation(domain="beta.net"),
                }]
            },
        )
        item = only_hypothesis(state)
        self.assertEqual(len(item["proxy_trails"]), 1)
        self.assertEqual(
            item["proxy_trails"][0]["origin_cruxes"], ["C1", "C2"]
        )
        self.assertEqual(item["state"], "TRACED")

    def test_conflicting_executable_routes_require_reviewed_design(self):
        state = state_from()
        state["cruxes"] = {"C1": {}}
        stored = only_hypothesis(state)
        shared = {
            "hypothesis_id": stored["hypothesis_id"],
            "origin_crux": "C1",
            "proxy": "Shared physical-flow diagnostic",
            "causal_link": "Tests the same physical constraint",
            "direction": "AMBIGUOUS",
        }
        hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "proxy_trails": [{
                    **shared,
                    "next_source_class": "REGULATOR_DATA",
                    "bounded_query": "official physical flow",
                    "stop_condition": "one official series checked",
                }]
            },
            inquisitor={
                "proxy_trails": [{
                    **shared,
                    "next_source_class": "ISSUER_FILING",
                    "bounded_query": "issuer physical flow",
                    "stop_condition": "one issuer filing checked",
                }]
            },
            allowed_crux_ids=["C1"],
        )
        trail = only_hypothesis(state)["proxy_trails"][0]
        self.assertTrue(trail["next_source_class_contested"])
        self.assertTrue(trail["bounded_query_contested"])
        action = hypothesis_engine.exploration_action(state)
        self.assertEqual(
            action["authorization_state"], "NEEDS_ACTION_DESIGN"
        )
        report_proxy = hypothesis_engine.report_view(state)[
            "hypotheses"
        ][0]["proxy_trails"][0]
        self.assertIn(
            "bounded_query", report_proxy["route_contested_fields"]
        )
        self.assertEqual(
            len(report_proxy["route_field_variants"]["bounded_query"]), 2
        )

    def test_alias_canonical_collision_is_ambiguous(self):
        alpha = spark(statement="Alpha canonical mechanism")
        alpha_id = hypothesis_engine.normalize_wild_hypothesis(
            alpha
        )["hypothesis"]["hypothesis_id"]
        beta = spark(
            statement="Beta alias mechanism",
            spark_id=alpha_id,
        )
        state = state_from([alpha, beta])
        audit = hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "proxy_trails": [{
                    "hypothesis_id": alpha_id,
                    **proxy(),
                }]
            },
            inquisitor={},
        )
        self.assertEqual(
            audit["rejected_reasons"][
                "detective_proxy_trail_ambiguous_hypothesis_alias"
            ],
            1,
        )

    def test_conflicting_payoffs_are_contested_and_role_order_invariant(self):
        statement = "A contested payoff mechanism"
        optimistic = spark(
            statement=statement,
            payoff={
                "upside": 80,
                "downside": 20,
                "unit": "PERCENT_MAGNITUDE",
            },
        )
        conservative = spark(
            statement=statement,
            payoff={
                "upside": 40,
                "downside": 40,
                "unit": "PERCENT_MAGNITUDE",
            },
        )

        outcomes = []
        for detective, inquisitor in (
            (optimistic, conservative),
            (conservative, optimistic),
        ):
            state = state_from([
                spark(statement=statement, payoff={})
            ])
            hypothesis_engine.ingest_round(
                state,
                1,
                detective={"hypothesis_sparks": [detective]},
                inquisitor={"hypothesis_sparks": [inquisitor]},
            )
            item = only_hypothesis(state)
            outcomes.append({
                "payoff": item["payoff"],
                "payoff_contested": item["payoff_contested"],
                "variants": item["field_variants"]["payoff"],
                "threshold": item["break_even_threshold"],
                "asymmetry_interest": item["exploration_priority"][
                    "components"
                ]["asymmetry_interest"],
            })

        self.assertEqual(outcomes[0], outcomes[1])
        self.assertTrue(outcomes[0]["payoff_contested"])
        self.assertEqual(
            outcomes[0]["threshold"]["reason"],
            "conflicting_explicit_payoffs",
        )
        self.assertEqual(outcomes[0]["asymmetry_interest"], 0)

    def test_payoff_unit_case_does_not_create_false_contest(self):
        statement = "A payoff unit case normalization mechanism"
        state = state_from([
            spark(
                statement=statement,
                payoff={"upside": 80, "downside": 20, "unit": "PERCENT"},
            )
        ])
        hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "hypothesis_sparks": [
                    spark(
                        statement=statement,
                        payoff={
                            "upside": 80,
                            "downside": 20,
                            "unit": "percent",
                        },
                    )
                ]
            },
            inquisitor={},
        )
        item = only_hypothesis(state)
        self.assertFalse(item.get("payoff_contested", False))
        self.assertEqual(item["break_even_threshold"]["status"], "KNOWN")

    def test_conflicting_alternatives_block_evidence_backed_maturity(self):
        raw = spark(
            statement="Contested alternative mechanism",
            proxy_trails=[
                proxy(
                    observation="Trace one",
                    causal_link="First causal trace",
                    evidence=citation(domain="alpha.org"),
                ),
                proxy(
                    observation="Trace two",
                    causal_link="Second causal trace",
                    evidence=citation(domain="beta.net"),
                ),
            ],
        )
        state = state_from([raw])
        self.assertEqual(only_hypothesis(state)["state"], "EVIDENCE_BACKED")
        hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "hypothesis_sparks": [{
                    **raw,
                    "strongest_alternative_explanation": "Seasonal mix",
                }]
            },
            inquisitor={
                "hypothesis_sparks": [{
                    **raw,
                    "strongest_alternative_explanation": "Measurement drift",
                }]
            },
        )
        item = only_hypothesis(state)
        self.assertTrue(
            item["strongest_alternative_explanation_contested"]
        )
        self.assertEqual(item["state"], "TRACED")

    def test_top_level_proxy_can_resolve_hypothesis_statement(self):
        state = state_from()
        statement = only_hypothesis(state)["hypothesis"]
        audit = hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "proxy_trails": [{"hypothesis": statement, **proxy()}]
            },
            inquisitor={},
        )
        self.assertEqual(audit["accepted_new_proxy_trails"], 1)
        self.assertEqual(only_hypothesis(state)["state"], "TRACED")

    def test_unknown_hypothesis_proxy_is_rejected(self):
        state = state_from()
        audit = hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "proxy_trails": [{
                    "spark_id": "HS-DOES-NOT-EXIST",
                    **proxy(),
                }]
            },
            inquisitor={},
        )
        self.assertEqual(
            audit["rejected_reasons"][
                "detective_proxy_trail_unknown_hypothesis"
            ],
            1,
        )
        self.assertEqual(only_hypothesis(state)["state"], "HYPOTHESIS_ONLY")

    def test_duplicate_role_alias_is_ambiguous_without_exact_statement(self):
        state = state_from()
        alpha = spark(
            statement="Alpha alias mechanism",
            spark_id="DUPLICATE-ALIAS",
        )
        beta = spark(
            statement="Beta alias mechanism",
            spark_id="DUPLICATE-ALIAS",
        )
        audit = hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "hypothesis_sparks": [alpha, beta],
                "proxy_trails": [{
                    "spark_id": "DUPLICATE-ALIAS",
                    **proxy(),
                }],
            },
            inquisitor={},
        )
        self.assertEqual(
            audit["rejected_reasons"][
                "detective_proxy_trail_ambiguous_hypothesis_alias"
            ],
            1,
        )
        self.assertEqual(
            hypothesis_by_text(state, "Alpha alias mechanism")["state"],
            "HYPOTHESIS_ONLY",
        )
        self.assertEqual(
            hypothesis_by_text(state, "Beta alias mechanism")["state"],
            "HYPOTHESIS_ONLY",
        )

    def test_exact_statement_disambiguates_duplicate_role_alias(self):
        state = state_from()
        alpha = spark(
            statement="Alpha exact mechanism",
            spark_id="DUPLICATE-ALIAS",
        )
        beta = spark(
            statement="Beta exact mechanism",
            spark_id="DUPLICATE-ALIAS",
        )
        audit = hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "hypothesis_sparks": [alpha, beta],
                "proxy_trails": [{
                    "spark_id": "DUPLICATE-ALIAS",
                    "hypothesis": "Alpha exact mechanism",
                    **proxy(),
                }],
            },
            inquisitor={},
        )
        self.assertEqual(audit["accepted_new_proxy_trails"], 1)
        self.assertEqual(
            hypothesis_by_text(state, "Alpha exact mechanism")["state"],
            "TRACED",
        )
        self.assertEqual(
            hypothesis_by_text(state, "Beta exact mechanism")["state"],
            "HYPOTHESIS_ONLY",
        )

    def test_identifier_and_statement_mismatch_is_rejected(self):
        state = state_from()
        stored = only_hypothesis(state)
        audit = hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "hypothesis_sparks": [
                    spark(statement="Second mismatch mechanism")
                ],
                "proxy_trails": [{
                    "hypothesis_id": stored["hypothesis_id"],
                    "hypothesis": "Second mismatch mechanism",
                    **proxy(),
                }],
            },
            inquisitor={},
        )
        self.assertEqual(
            audit["rejected_reasons"][
                "detective_proxy_trail_hypothesis_reference_mismatch"
            ],
            1,
        )
        self.assertEqual(stored["state"], "HYPOTHESIS_ONLY")

    def test_role_spark_cannot_bypass_top_level_proxy_cap(self):
        state = state_from()
        embedded = spark(
            statement="Embedded proxy bypass attempt",
            proxy_trails=[
                proxy(
                    observation=f"Embedded observation {index}",
                    causal_link=f"Embedded causal link {index}",
                    evidence=citation(
                        domain=f"embedded-{index}.org",
                        path=f"embedded-{index}",
                    ),
                )
                for index in range(10)
            ],
        )
        audit = hypothesis_engine.ingest_round(
            state,
            1,
            detective={"hypothesis_sparks": [embedded]},
            inquisitor={},
        )
        item = hypothesis_by_text(
            state, "Embedded proxy bypass attempt"
        )
        self.assertEqual(item["state"], "HYPOTHESIS_ONLY")
        self.assertEqual(item["proxy_trails"], [])
        self.assertEqual(audit["submitted_proxy_trails"], 10)
        self.assertEqual(
            audit["rejected_reasons"][
                "detective_embedded_proxy_trails_ignored"
            ],
            10,
        )

    def test_per_role_spark_and_proxy_caps_are_host_enforced(self):
        state = state_from()
        stored = only_hypothesis(state)
        sparks = [
            spark(statement=f"Bounded new mechanism {index}")
            for index in range(4)
        ]
        trails = [
            {
                "hypothesis_id": stored["hypothesis_id"],
                **proxy(
                    observation=f"Distinct proxy observation {index}",
                    causal_link=f"Distinct causal diagnostic {index}",
                ),
            }
            for index in range(4)
        ]
        audit = hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "hypothesis_sparks": sparks,
                "proxy_trails": trails,
            },
            inquisitor={},
        )
        self.assertEqual(audit["submitted_sparks"], 4)
        self.assertEqual(audit["accepted_new_hypotheses"], 3)
        self.assertEqual(audit["submitted_proxy_trails"], 4)
        self.assertEqual(audit["accepted_new_proxy_trails"], 3)
        self.assertEqual(
            audit["rejected_reasons"][
                "detective_hypothesis_sparks_round_limit_exceeded"
            ],
            1,
        )
        self.assertEqual(
            audit["rejected_reasons"][
                "detective_proxy_trails_round_limit_exceeded"
            ],
            1,
        )

    def test_uninitialized_track_is_noop(self):
        state = {}
        audit = hypothesis_engine.ingest_round(
            state,
            1,
            detective={"hypothesis_sparks": [spark()]},
            inquisitor={},
        )
        self.assertFalse(audit["enabled"])
        self.assertEqual(audit["reason"], "hypothesis_track_not_initialized")
        self.assertNotIn("hypothesis_ledger", state)

    def test_round_must_be_positive_integer(self):
        state = state_from()
        for invalid in (0, -1, 1.5, True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    hypothesis_engine.ingest_round(state, invalid, {}, {})


class PriorityActionAndReportTests(unittest.TestCase):
    def evidence_backed_spark(self, statement="Sourced mechanism"):
        return spark(
            statement=statement,
            proxy_trails=[
                proxy(evidence=citation(domain="alpha.org")),
                proxy(
                    observation="Customer acceptance cadence",
                    causal_link="Acceptance cadence tests qualification scarcity",
                    evidence=citation(
                        domain="beta.net",
                        source="Beta Standards Lab",
                    ),
                ),
            ],
        )

    def test_traced_asymmetric_testable_hypothesis_is_explore_now(self):
        item = hypothesis_engine.normalize_wild_hypothesis(
            spark(
                payoff={"upside": 80, "downside": 20, "unit": "PERCENT"},
                proxy_trails=[proxy()],
            ),
            allow_embedded_proxy_trails=True,
        )["hypothesis"]
        priority = item["exploration_priority"]
        self.assertEqual(item["state"], "TRACED")
        self.assertEqual(priority["band"], "EXPLORE_NOW")
        self.assertEqual(priority["components"]["asymmetry_interest"], 3)
        self.assertIn("not a probability", priority["semantics"])

    def test_second_proxy_action_skips_consumed_frame_route(self):
        route_a = {
            "proxy": "Route A observable",
            "why_diagnostic": "Route A causal diagnostic",
            "publisher_class": "ISSUER_PRIMARY",
            "bounded_query": "route A exact query",
            "stop_condition": "one query",
            "direction": "SUPPORTS",
        }
        route_b = {
            "proxy": "Route B observable",
            "why_diagnostic": "Route B causal diagnostic",
            "publisher_class": "CUSTOMER_OR_COUNTERPARTY",
            "bounded_query": "route B exact query",
            "stop_condition": "one query",
            "direction": "CONTRADICTS",
        }
        state = state_from([
            spark(
                proxy_plan=[route_a, route_b],
                proxy_trails=[{
                    **route_a,
                    "causal_link": route_a["why_diagnostic"],
                    "next_source_class": route_a["publisher_class"],
                    "evidence": citation(domain="route-a.org"),
                }],
            )
        ])
        action = hypothesis_engine.exploration_action(state)
        self.assertEqual(
            action["action_code"], "COLLECT_SECOND_PROXY_EVIDENCE"
        )
        self.assertEqual(
            action["route_spec"]["proxy"], route_b["proxy"]
        )
        self.assertEqual(
            action["bounded_query"], route_b["bounded_query"]
        )

    def test_qualitative_optionality_prioritizes_research_not_promotion(self):
        item = hypothesis_engine.normalize_wild_hypothesis(
            spark(
                payoff={},
                asymmetry_case={
                    "upside_shape": "OUTSIZED",
                    "convexity": "OPTION_LIKE",
                    "downside_shape": "LIMITED",
                    "time_to_signal": "NEAR",
                    "basis": (
                        "small qualification cost tests access to a much "
                        "larger scarcity-rent path"
                    ),
                },
            )
        )["hypothesis"]
        priority = item["exploration_priority"]
        self.assertEqual(priority["band"], "EXPLORE_NOW")
        self.assertEqual(
            priority["components"]["qualitative_asymmetry_interest"], 3
        )
        self.assertEqual(
            priority["components"]["time_to_signal"], 1
        )
        self.assertEqual(item["state"], "HYPOTHESIS_ONLY")
        self.assertIn("not", priority["semantics"])

    def test_unknown_asymmetry_case_can_be_enriched_without_contest(self):
        statement = "Late qualitative asymmetry enrichment"
        state = state_from([spark(statement=statement)])
        hypothesis_engine.ingest_round(
            state,
            1,
            detective={
                "hypothesis_sparks": [
                    spark(
                        statement=statement,
                        asymmetry_case={
                            "upside_shape": "OUTSIZED",
                            "convexity": "OPTION_LIKE",
                            "downside_shape": "LIMITED",
                            "time_to_signal": "NEAR",
                            "basis": "one cheap test opens a convex path",
                        },
                    )
                ]
            },
            inquisitor={},
        )
        item = only_hypothesis(state)
        self.assertFalse(
            item.get("asymmetry_case_contested", False)
        )
        self.assertEqual(
            item["exploration_priority"]["components"][
                "qualitative_asymmetry_interest"
            ],
            3,
        )

    def test_payoff_without_explicit_common_unit_cannot_rank_as_asymmetry(self):
        for unit in (None, "unspecified_same_unit", "UNKNOWN", "TBD", "n/a"):
            with self.subTest(unit=unit):
                payoff = {"upside": 80, "downside": 20}
                if unit is not None:
                    payoff["unit"] = unit
                item = hypothesis_engine.normalize_wild_hypothesis(
                    spark(
                        payoff=payoff,
                        proxy_trails=[proxy()],
                    )
                )["hypothesis"]
                self.assertEqual(
                    item["break_even_threshold"]["status"], "UNKNOWN"
                )
                self.assertEqual(
                    item["break_even_threshold"]["reason"],
                    "missing_explicit_same_unit",
                )
                self.assertEqual(
                    item["exploration_priority"]["components"][
                        "asymmetry_interest"
                    ],
                    0,
                )

    def test_actions_follow_maturity_gaps_without_promotion(self):
        cases = [
            (spark(), "DESIGN_PROXY_TRAIL"),
            (
                spark(
                    strongest_alternative_explanation="",
                    proxy_trails=[proxy()],
                ),
                "ARTICULATE_STRONGEST_ALTERNATIVE",
            ),
            (
                spark(proxy_trails=[proxy(evidence=citation())]),
                "COLLECT_SECOND_PROXY_EVIDENCE",
            ),
            (
                self.evidence_backed_spark(),
                "SEEK_DISCONFIRMING_PROXY",
            ),
        ]
        for raw, expected in cases:
            with self.subTest(expected=expected):
                action = hypothesis_engine.exploration_action(
                    state_from([raw])
                )
                self.assertEqual(action["action_code"], expected)
                self.assertEqual(
                    action["authority"],
                    "RESEARCH_ONLY_NO_PROMOTION",
                )
                self.assertEqual(action["action_type"], action["action_code"])
                self.assertEqual(action["authorization_state"], "NEEDS_ACTION_DESIGN")
                self.assertFalse(action["requires_human_authorization"])
                self.assertFalse(action["authorization_ready"])
                self.assertFalse(action["executable_after_authorization"])
                self.assertIsNone(action["execution_receipt"])
                self.assertTrue(action["question"])
                self.assertTrue(action["success_condition"])
                self.assertTrue(action["stop_condition"])
                self.assertEqual(
                    action["budget_boundary"]["max_bounded_queries"],
                    1,
                )
                self.assertFalse(
                    action["budget_boundary"]["automatic_follow_on"]
                )
                self.assertEqual(
                    action["budget_boundary"]["max_documents_read"],
                    3,
                )

    def test_route_complete_action_is_proposed_but_not_authorized(self):
        raw = spark(
            proxy_trails=[proxy(evidence=citation())],
            proxy_plan=[{
                "proxy": "Distinct official physical-flow series",
                "why_diagnostic": "Separates qualification from mix noise",
                "publisher_class": "REGULATOR_OR_OFFICIAL_DATASET",
                "bounded_query": "official qualification physical flow",
            }],
        )
        action = hypothesis_engine.exploration_action(state_from([raw]))
        self.assertEqual(action["action_code"], "COLLECT_SECOND_PROXY_EVIDENCE")
        self.assertEqual(action["authorization_state"], "PROPOSED_NOT_AUTHORIZED")
        self.assertTrue(action["authorization_ready"])
        self.assertTrue(action["requires_human_authorization"])
        self.assertTrue(action["executable_after_authorization"])
        self.assertEqual(
            action["source_class"], "REGULATOR_OR_OFFICIAL_DATASET"
        )
        self.assertEqual(
            action["bounded_query"], "official qualification physical flow"
        )

    def test_summary_separates_three_maturity_states(self):
        state = state_from([
            spark(statement="First wild idea"),
            spark(
                statement="Second traced idea",
                proxy_trails=[proxy()],
            ),
            self.evidence_backed_spark("Third sourced idea"),
        ])
        result = hypothesis_engine.summary(state)
        self.assertEqual(result["hypothesis_count"], 3)
        self.assertEqual(result["state_counts"]["HYPOTHESIS_ONLY"], 1)
        self.assertEqual(result["state_counts"]["TRACED"], 1)
        self.assertEqual(result["state_counts"]["EVIDENCE_BACKED"], 1)
        self.assertEqual(result["proxy_trail_count"], 3)
        self.assertEqual(result["evidence_backed_proxy_count"], 2)

    def test_cited_spark_observation_stays_unpromoted_without_proxy_trail(self):
        raw = spark(
            observation="A dated physical-flow observation",
            evidence=[citation()],
        )
        state = state_from([raw])
        item = only_hypothesis(state)
        view = hypothesis_engine.report_view(state)["hypotheses"][0]
        self.assertEqual(item["state"], "HYPOTHESIS_ONLY")
        self.assertEqual(view["observation_status"], "CITED_OBSERVATION")
        self.assertEqual(len(view["observation_evidence"]), 1)

    def test_report_view_is_ranked_limited_and_keeps_only_valid_evidence(self):
        state = state_from([
            spark(statement="Low information idea", payoff={}),
            spark(
                statement="High priority trace",
                payoff={"upside": 80, "downside": 20},
                proxy_trails=[proxy(evidence=citation())],
            ),
            self.evidence_backed_spark("Mature trace"),
        ])
        result = hypothesis_engine.report_view(state, limit=2)
        self.assertEqual(len(result["hypotheses"]), 2)
        scores = [
            item["priority"]["score"] for item in result["hypotheses"]
        ]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertIn("summary", result)
        self.assertIn("exploration_action", result)
        for item in result["hypotheses"]:
            self.assertIn("observation", item)
            self.assertIn("observation_status", item)
            self.assertIn("observation_evidence", item)
            self.assertIn("inference", item)
            self.assertIn("surprise_if_true", item)
            self.assertIn("strongest_alternative_explanation", item)
            self.assertIn("cheap_discriminating_test", item)
            self.assertEqual(item["hypothesis_id"], item["id"])
            self.assertEqual(
                item["break_even_threshold"], item["break_even"]
            )
            self.assertEqual(
                item["exploration_priority"], item["priority"]
            )
            for trail in item["proxy_trails"]:
                self.assertEqual(trail["proxy_id"], trail["id"])
                self.assertEqual(
                    trail["causal_link"], trail["why_diagnostic"]
                )
                self.assertIn("alternative_explanation", trail)
                self.assertTrue(all(
                    hypothesis_engine.valid_citation(evidence)
                    for evidence in trail["evidence"]
                ))
        forbidden = {
            "opportunity_seed",
            "opportunity_seeds",
            "candidate_screen",
            "candidate_screens",
            "trade",
            "position",
            "position_size",
        }
        self.assertTrue(forbidden.isdisjoint(all_keys(result)))

    def test_report_view_limit_validation_and_empty_track(self):
        for invalid in (-1, 1.5, True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    hypothesis_engine.report_view({}, invalid)
        result = hypothesis_engine.report_view({})
        self.assertEqual(result["hypotheses"], [])
        self.assertFalse(result["summary"]["exploration_enabled"])

    def test_empty_track_action_is_explicit(self):
        self.assertEqual(
            hypothesis_engine.exploration_action({})["action_code"],
            "NO_EXPLORATION_TRACK",
        )
        ledger = {
            "schema_version": hypothesis_engine.SCHEMA_VERSION,
            "research_intent": "THESIS_CHALLENGE",
            "hypotheses": [],
            "round_audits": [],
        }
        self.assertEqual(
            hypothesis_engine.exploration_action(ledger)["action_code"],
            "NO_HYPOTHESIS_AVAILABLE",
        )


if __name__ == "__main__":
    unittest.main()
