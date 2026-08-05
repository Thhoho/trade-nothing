#!/usr/bin/env python3
"""Offline regression tests for snapshot-bound claim verification."""
import copy
import os
import tempfile
import unittest

import candidate_screen_engine
import claim_verification_engine as claim_engine
import deepthink_orchestrator_v2 as orchestrator
import evidence_snapshot
import report_v2
import test_candidate_screen_engine as candidate_fixtures


AS_OF = candidate_fixtures.AS_OF


def screened_state():
    st = candidate_fixtures.state_with_seed()
    analyst = candidate_fixtures.payload("Analyst")
    skeptic = candidate_fixtures.payload("Skeptic")
    receipt = candidate_fixtures.install_test_dispatch(st, analyst, skeptic)
    candidate_screen_engine.evaluate_batch(
        st, analyst, skeptic,
        AS_OF,
        isolation_status="verified",
        isolation_receipt=receipt,
    )
    return st


def snapshot_payload(st):
    snapshots = []
    for request in claim_engine.collect_claim_requests(st):
        citation = request["citation"]
        body = (
            f"<html><head><title>{citation['source']}</title></head>"
            f"<body><p>{citation['claim']}</p><script>ignore me</script>"
            f"<p>Additional source context.</p></body></html>"
        ).encode("utf-8")
        snapshots.append(evidence_snapshot.snapshot_from_bytes(
            citation["url"], body, retrieved_at="2026-07-10T00:00:00+00:00"
        ))
    return {"snapshots": snapshots}


def verifier_payload(st, snapshots, overrides=None, quote_override=None):
    overrides = overrides or {}
    by_url = {item["source_url"]: item for item in snapshots["snapshots"]}
    results = []
    for request in claim_engine.collect_claim_requests(st):
        citation = request["citation"]
        verdict = overrides.get(request["claim_id"], "SUPPORTS")
        quote = citation["claim"] if verdict != "INSUFFICIENT" else ""
        if quote_override and request["claim_id"] in quote_override:
            quote = quote_override[request["claim_id"]]
        results.append({
            "claim_id": request["claim_id"],
            "snapshot_id": by_url[citation["url"]]["snapshot_id"],
            "verdict": verdict,
            "exact_quote": quote,
            "locator": "paragraph 1",
            "reason": "The exact sentence aligns with the submitted claim.",
        })
    return {"claim_verifications": results}


def install_verifier_dispatch(st, snapshots):
    packet = claim_engine.build_verifier_packet(st, snapshots)
    dispatch = claim_engine.verifier_dispatch_record(packet, "fixture verifier prompt")
    st["claim_verifier_dispatches"] = [dispatch]
    return dispatch


def verifier_receipt(st, verifier, runner_kind="agy_separate_process_v1"):
    dispatch = st["claim_verifier_dispatches"][-1]
    role = {
        "invocation_id": "fixture-verifier-invocation",
        "process_id": 4242,
        "exit_code": 0,
        "timed_out": False,
        "prompt_sha256": dispatch["prompt_sha256"],
        "payload_sha256": candidate_screen_engine.payload_sha256(verifier),
    }
    receipt = {
        "schema": "claim-verifier-isolation.v1",
        "runner_kind": runner_kind,
        "host_enforced": True,
        "dispatch_id": dispatch["dispatch_id"],
        "claim_ids": dispatch["claim_ids"],
        "snapshot_ids": dispatch["snapshot_ids"],
        "verifier": role,
    }
    receipt["receipt_id"] = claim_engine.isolation_receipt_id(receipt)
    return receipt


def apply_verified(st, snapshots, verifier, **kwargs):
    if not st.get("claim_verifier_dispatches"):
        install_verifier_dispatch(st, snapshots)
    return claim_engine.apply_verifier_results(
        st,
        snapshots,
        verifier,
        isolation_status="verified",
        isolation_receipt=verifier_receipt(st, verifier),
        **kwargs,
    )


class EvidenceSnapshotTests(unittest.TestCase):
    def test_html_snapshot_is_deterministic_and_excludes_script(self):
        body = b"<html><head><title>Source</title></head><body><p>Revenue was 10.</p><script>fake 99</script></body></html>"
        a = evidence_snapshot.snapshot_from_bytes(
            "https://fixture-research.org/filing/a", body, retrieved_at="2026-07-10T00:00:00+00:00"
        )
        b = evidence_snapshot.snapshot_from_bytes(
            "https://fixture-research.org/filing/a", body, retrieved_at="2026-07-11T00:00:00+00:00"
        )
        self.assertEqual(a["snapshot_id"], b["snapshot_id"])
        self.assertEqual(a["text_sha256"], b["text_sha256"])
        self.assertIn("Revenue was 10.", a["text"])
        self.assertNotIn("fake 99", a["text"])

    def test_private_network_url_is_rejected(self):
        with self.assertRaises(ValueError):
            evidence_snapshot.validate_public_url("http://127.0.0.1/private", resolve_dns=False)
        with self.assertRaises(ValueError):
            evidence_snapshot.validate_public_url("http://169.254.169.254/metadata", resolve_dns=False)


class ClaimVerificationEngineTests(unittest.TestCase):
    def test_tampered_snapshot_hash_is_rejected(self):
        st = screened_state()
        snapshots = snapshot_payload(st)
        snapshots["snapshots"][0]["text"] += " tampered"
        packet = claim_engine.build_verifier_packet(st, snapshots)
        self.assertTrue(packet["rejected_snapshots"])
        self.assertIn("snapshot_text_hash_mismatch", {
            item["reason"] for item in packet["rejected_snapshots"]
        })

    def test_private_final_url_snapshot_is_rejected(self):
        st = screened_state()
        snapshots = snapshot_payload(st)
        snapshots["snapshots"][0]["final_url"] = "http://127.0.0.1/private"
        packet = claim_engine.build_verifier_packet(st, snapshots)
        self.assertIn("invalid_snapshot_url", {
            item["reason"] for item in packet["rejected_snapshots"]
        })

    def test_snapshot_fetch_errors_are_not_silently_dropped(self):
        st = screened_state()
        packet = claim_engine.build_verifier_packet(
            st, {"snapshots": [], "errors": [{"url": "https://fixture-research.org/fail", "error": "timeout"}]}
        )
        self.assertIn("snapshot_fetch_error:timeout", {
            item["reason"] for item in packet["rejected_snapshots"]
        })

    def test_exact_snapshot_spans_unlock_human_draft(self):
        st = screened_state()
        snapshots = snapshot_payload(st)
        audit = apply_verified(st, snapshots, verifier_payload(st, snapshots))
        screen = st["candidate_screens"][0]
        self.assertEqual(screen["claim_verification_status"], "VERIFIED")
        self.assertEqual(screen["promotion_packet"]["status"], "DRAFT_REQUIRES_HUMAN")
        self.assertEqual(audit["verified_thesis_candidate_count"], 1)
        self.assertEqual(st["opportunity_seeds"][0]["candidate_state"], "VERIFIED_FOR_HUMAN")
        self.assertEqual(st["opportunity_seeds"][0]["promotion_eligibility"], "VERIFIED_FOR_HUMAN")
        self.assertTrue(st["source_snapshots"])
        self.assertNotIn("text", st["source_snapshots"][0])
        self.assertNotIn("text", st["claim_verifications"][0]["snapshot_manifest"])

    def test_exact_verifier_replay_is_idempotent(self):
        st = screened_state()
        snapshots = snapshot_payload(st)
        verifier = verifier_payload(st, snapshots)
        apply_verified(st, snapshots, verifier)
        original = copy.deepcopy(st["claim_verifications"])
        replay = apply_verified(st, snapshots, verifier)
        self.assertEqual(replay["accepted_verifications"], 0)
        self.assertEqual(
            sorted(replay["replayed_claim_ids"]),
            sorted(item["claim_id"] for item in original),
        )
        self.assertEqual(st["claim_verifications"], original)

    def test_changed_verifier_payload_conflicts_without_overwrite(self):
        st = screened_state()
        snapshots = snapshot_payload(st)
        verifier = verifier_payload(st, snapshots)
        apply_verified(st, snapshots, verifier)
        original_verifications = copy.deepcopy(st["claim_verifications"])
        original_screen = copy.deepcopy(st["candidate_screens"][0])
        first = claim_engine.collect_claim_requests(st)[0]["claim_id"]
        changed = verifier_payload(st, snapshots, overrides={first: "CONTRADICTS"})
        conflict = apply_verified(st, snapshots, changed)
        self.assertEqual(conflict["accepted_verifications"], 0)
        self.assertEqual(conflict["conflicting_claim_ids"], [first])
        self.assertEqual(st["claim_verifications"], original_verifications)
        self.assertEqual(st["candidate_screens"][0], original_screen)

    def test_invented_quote_is_physically_rejected(self):
        st = screened_state()
        snapshots = snapshot_payload(st)
        first = claim_engine.collect_claim_requests(st)[0]["claim_id"]
        payload = verifier_payload(st, snapshots, quote_override={first: "This sentence is not in the page."})
        apply_verified(st, snapshots, payload, requested_claim_id=first)
        verification = claim_engine.latest_verifications(st)[first]
        self.assertEqual(verification["effective_verdict"], "INSUFFICIENT")
        self.assertIn("exact_quote_not_in_snapshot", verification["quality_flags"])

    def test_unverified_verifier_cannot_unlock_draft(self):
        st = screened_state()
        snapshots = snapshot_payload(st)
        claim_engine.apply_verifier_results(st, snapshots, verifier_payload(st, snapshots))
        screen = st["candidate_screens"][0]
        self.assertEqual(screen["claim_verification_status"], "PENDING")
        self.assertEqual(screen["promotion_packet"]["status"], "DRAFT_REQUIRES_SOURCE_VERIFICATION")

    def test_verified_label_without_bound_receipt_cannot_unlock_draft(self):
        st = screened_state()
        snapshots = snapshot_payload(st)
        audit = claim_engine.apply_verifier_results(
            st,
            snapshots,
            verifier_payload(st, snapshots),
            isolation_status="verified",
        )
        screen = st["candidate_screens"][0]
        self.assertEqual(audit["effective_verifier_isolation"], "unverified")
        self.assertEqual(audit["verifier_isolation_receipt_status"], "invalid")
        self.assertEqual(screen["claim_verification_status"], "PENDING")
        self.assertEqual(
            screen["promotion_packet"]["status"],
            "DRAFT_REQUIRES_SOURCE_VERIFICATION",
        )

    def test_snapshot_bound_contradiction_blocks_promotion(self):
        st = screened_state()
        snapshots = snapshot_payload(st)
        first = claim_engine.collect_claim_requests(st)[0]["claim_id"]
        payload = verifier_payload(st, snapshots, overrides={first: "CONTRADICTS"})
        apply_verified(st, snapshots, payload)
        screen = st["candidate_screens"][0]
        self.assertEqual(screen["claim_verification_status"], "CONTRADICTED")
        self.assertEqual(screen["promotion_packet"]["status"], "BLOCKED_CLAIM_CONFLICT")


class ClaimVerificationOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_scratch = os.environ.get("TRADE_NOTHING_SCRATCH_DIR")
        os.environ["TRADE_NOTHING_SCRATCH_DIR"] = self.tmp.name

    def tearDown(self):
        if self.old_scratch is None:
            os.environ.pop("TRADE_NOTHING_SCRATCH_DIR", None)
        else:
            os.environ["TRADE_NOTHING_SCRATCH_DIR"] = self.old_scratch
        self.tmp.cleanup()

    def test_plan_dispatch_submit_and_report(self):
        topic = "claim verification integration"
        st = screened_state()
        snapshots = snapshot_payload(st)
        orchestrator._save(topic, st)
        plan = orchestrator.cmd_verification_plan(topic)
        self.assertEqual(plan["status"], "need_source_snapshots")
        self.assertGreater(plan["claim_count"], 0)
        dispatch = orchestrator.cmd_verify_claims(topic, snapshots)
        self.assertEqual(dispatch["status"], "dispatch_claim_verifier")
        self.assertLessEqual(len(dispatch["claim_ids"]), claim_engine.MAX_CLAIMS_PER_BATCH)
        stored_before_submit = orchestrator._load(topic)
        verifier = verifier_payload(stored_before_submit, snapshots)
        receipt = verifier_receipt(stored_before_submit, verifier)
        result = orchestrator.cmd_submit_verification(
            topic,
            snapshots,
            verifier,
            isolation_status="verified",
            isolation_receipt=receipt,
        )
        stored = orchestrator._load(topic)
        self.assertEqual(result["verified_thesis_candidate_count"], 1)
        self.assertEqual(stored["candidate_screens"][0]["claim_verification_status"], "VERIFIED")
        md = report_v2.render(stored)
        self.assertIn("P2 VERIFIED", md)
        self.assertIn("页面快照与 claim 对齐账本", md)
        self.assertIn("DRAFT_REQUIRES_HUMAN", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
