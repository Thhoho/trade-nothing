#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Snapshot-bound claim verification for CandidateScreen evidence.

An LLM verifier may classify semantic support, but it cannot invent the source
text: decisive verdicts require a short exact quote present in a content-hashed
snapshot. State stores manifests and short spans, not full page bodies.
"""
import datetime as dt
import hashlib
import re
from urllib.parse import urlparse

import candidate_screen_engine
import crux_engine
import evidence_snapshot
import opportunity_engine


VERDICTS = {"SUPPORTS", "CONTRADICTS", "INSUFFICIENT"}
MAX_CLAIMS_PER_BATCH = 5
MAX_QUOTE_CHARS = 160
MAX_QUOTE_WORDS = 30
EXCERPT_CHARS = 12_000
MAX_SNAPSHOT_TEXT_CHARS = evidence_snapshot.MAX_TEXT_CHARS


def _text(value):
    return " ".join(str(value or "").split())


def _url_identity(url):
    if not crux_engine.is_concrete_url(url):
        return ""
    parsed = urlparse(url.strip())
    path = re.sub(r"/+", "/", parsed.path or "/").rstrip("/") or "/"
    out = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"
    if parsed.query:
        out += f"?{parsed.query}"
    return out


def claim_id(citation):
    identity = crux_engine.citation_identity(citation)
    if not identity:
        return ""
    return "CL-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12].upper()


def collect_claim_requests(state, seed_id=None):
    """Collect de-duplicated evidence claims from latest THESIS_CANDIDATE screens."""
    requests = {}
    latest = candidate_screen_engine.latest_by_seed(state)
    for current_seed_id, screen in latest.items():
        if seed_id and current_seed_id != seed_id:
            continue
        if screen.get("status") != "THESIS_CANDIDATE":
            continue
        for dimension, combined in screen.get("dimensions", {}).items():
            if combined.get("state") != "SUPPORTED":
                continue
            for side in ("analyst", "skeptic"):
                assessment = combined.get(side, {})
                evidence = assessment.get("fresh_evidence", assessment.get("evidence", []))
                for citation in evidence:
                    cid = claim_id(citation)
                    if not cid:
                        continue
                    item = requests.setdefault(cid, {
                        "claim_id": cid,
                        "citation": dict(citation),
                        "contexts": [],
                    })
                    context = {
                        "seed_id": current_seed_id,
                        "screen_id": screen.get("screen_id"),
                        "dimension": dimension,
                        "side": side,
                    }
                    if context not in item["contexts"]:
                        item["contexts"].append(context)
    return sorted(requests.values(), key=lambda item: item["claim_id"])


def verification_plan(state, seed_id=None):
    requests = collect_claim_requests(state, seed_id)
    latest = latest_verifications(state)
    urls = {}
    for request in requests:
        citation = request["citation"]
        key = _url_identity(citation.get("url", ""))
        item = urls.setdefault(key, {
            "url": citation.get("url"),
            "claim_ids": [],
            "source": citation.get("source"),
        })
        item["claim_ids"].append(request["claim_id"])
    return {
        "claim_count": len(requests),
        "pending_claim_count": sum(
            latest.get(item["claim_id"], {}).get("effective_verdict") != "SUPPORTS"
            for item in requests
        ),
        "snapshot_requests": sorted(urls.values(), key=lambda item: item["url"] or ""),
    }


def _snapshot_id(source_url, final_url, text_sha256):
    return "SS-" + hashlib.sha256(
        f"{source_url}|{final_url}|{text_sha256}".encode("utf-8")
    ).hexdigest()[:12].upper()


def normalize_snapshots(payload):
    payload = payload if isinstance(payload, dict) else {}
    raw = payload.get("snapshots", [])
    raw = raw if isinstance(raw, list) else []
    errors = payload.get("errors", [])
    rejected = [
        {"source_url": item.get("url"), "reason": f"snapshot_fetch_error:{item.get('error', '')}"}
        for item in errors if isinstance(item, dict)
    ] if isinstance(errors, list) else []
    accepted = {}
    for item in raw:
        if not isinstance(item, dict):
            rejected.append({"reason": "snapshot_not_object"})
            continue
        source_url = _text(item.get("source_url"))
        final_url = _text(item.get("final_url") or source_url)
        text = evidence_snapshot.normalize_text(item.get("text"))
        text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        expected_id = _snapshot_id(source_url, final_url, text_sha)
        reason = ""
        try:
            evidence_snapshot.validate_public_url(source_url, resolve_dns=False)
            evidence_snapshot.validate_public_url(final_url, resolve_dns=False)
            public_urls = True
        except (TypeError, ValueError):
            public_urls = False
        try:
            http_status = int(item.get("http_status"))
        except (TypeError, ValueError):
            http_status = 0
        if item.get("status") != "OK":
            reason = "snapshot_status_not_ok"
        elif not public_urls or not _url_identity(source_url) or not _url_identity(final_url):
            reason = "invalid_snapshot_url"
        elif http_status < 200 or http_status >= 300:
            reason = "snapshot_http_status_not_success"
        elif not text:
            reason = "empty_snapshot_text"
        elif len(text) > MAX_SNAPSHOT_TEXT_CHARS:
            reason = "snapshot_text_too_large"
        elif item.get("text_sha256") and item.get("text_sha256") != text_sha:
            reason = "snapshot_text_hash_mismatch"
        elif item.get("snapshot_id") and item.get("snapshot_id") != expected_id:
            reason = "snapshot_id_mismatch"
        if reason:
            rejected.append({"snapshot_id": item.get("snapshot_id"), "source_url": source_url, "reason": reason})
            continue
        normalized = {
            "snapshot_id": expected_id,
            "status": "OK",
            "source_url": source_url,
            "final_url": final_url,
            "retrieved_at": _text(item.get("retrieved_at")),
            "http_status": http_status,
            "content_type": _text(item.get("content_type")),
            "title": _text(item.get("title")),
            "raw_sha256": _text(item.get("raw_sha256")),
            "text_sha256": text_sha,
            "text_length": len(text),
            "text": text,
        }
        accepted[_url_identity(source_url)] = normalized
    return accepted, rejected


def _focus_excerpt(text, citation):
    text = evidence_snapshot.normalize_text(text)
    needles = []
    number = _text(citation.get("number"))
    if number and number.lower() not in {"none", "null", "n/a"}:
        needles.append(number)
    claim = _text(citation.get("claim"))
    needles.extend(re.findall(r"[A-Za-z0-9][A-Za-z0-9_.%/-]{2,}|[一-龥]{3,}", claim))
    lower = text.casefold()
    position = -1
    for needle in sorted(set(needles), key=len, reverse=True):
        position = lower.find(needle.casefold())
        if position >= 0:
            break
    if position < 0:
        start = 0
    else:
        start = max(0, position - EXCERPT_CHARS // 2)
    end = min(len(text), start + EXCERPT_CHARS)
    return {"start": start, "end": end, "text": text[start:end]}


def build_verifier_packet(state, snapshots_payload, seed_id=None, requested_claim_id=None):
    requests = collect_claim_requests(state, seed_id)
    if requested_claim_id:
        requests = [item for item in requests if item["claim_id"] == requested_claim_id]
    else:
        latest = latest_verifications(state)
        pending = [
            item for item in requests
            if latest.get(item["claim_id"], {}).get("effective_verdict") != "SUPPORTS"
        ]
        requests = pending[:MAX_CLAIMS_PER_BATCH]
    snapshots, rejected = normalize_snapshots(snapshots_payload)
    claims, missing = [], []
    packet_snapshots = {}
    for request in requests:
        citation = request["citation"]
        snapshot = snapshots.get(_url_identity(citation.get("url", "")))
        if not snapshot:
            missing.append(request["claim_id"])
            continue
        focus = _focus_excerpt(snapshot["text"], citation)
        packet_snapshots[snapshot["snapshot_id"]] = {
            key: value for key, value in snapshot.items() if key != "text"
        } | {"verification_text": focus["text"], "excerpt_start": focus["start"], "excerpt_end": focus["end"]}
        claims.append({
            **request,
            "snapshot_id": snapshot["snapshot_id"],
        })
    return {
        "claims": claims,
        "snapshots": list(packet_snapshots.values()),
        "missing_snapshot_claim_ids": missing,
        "rejected_snapshots": rejected,
    }


def _verifier_results(payload):
    payload = payload if isinstance(payload, dict) else {}
    out = {}
    for item in payload.get("claim_verifications", []) if isinstance(payload.get("claim_verifications", []), list) else []:
        if isinstance(item, dict) and item.get("claim_id") and item["claim_id"] not in out:
            out[item["claim_id"]] = item
    return out


def _manifest(snapshot):
    return {key: value for key, value in snapshot.items() if key != "text"}


def isolation_receipt_id(receipt):
    content = dict(receipt) if isinstance(receipt, dict) else {}
    content.pop("receipt_id", None)
    return "CVR-" + candidate_screen_engine.payload_sha256(content)[:12].upper()


def verifier_dispatch_record(packet, prompt):
    """Return the immutable surface a host receipt must bind to."""
    packet = packet if isinstance(packet, dict) else {}
    claim_ids = [
        item.get("claim_id") for item in packet.get("claims", [])
        if isinstance(item, dict) and item.get("claim_id")
    ]
    snapshot_ids = [
        item.get("snapshot_id") for item in packet.get("snapshots", [])
        if isinstance(item, dict) and item.get("snapshot_id")
    ]
    core = {
        "claim_ids": claim_ids,
        "snapshot_ids": snapshot_ids,
        "packet_sha256": candidate_screen_engine.payload_sha256(packet),
        "prompt_sha256": hashlib.sha256(str(prompt or "").encode("utf-8")).hexdigest(),
    }
    return {
        "dispatch_id": "CVD-" + candidate_screen_engine.payload_sha256(core)[:10].upper(),
        **core,
    }


def validate_isolation_receipt(state, receipt, verifier_payload):
    """Validate one host-enforced verifier context against a stored dispatch."""
    blockers = []
    receipt = receipt if isinstance(receipt, dict) else {}
    if receipt.get("schema") != "claim-verifier-isolation.v1":
        blockers.append("verifier_isolation_receipt_schema_invalid")
    runner_kind = _text(receipt.get("runner_kind"))
    process_runners = {"agy_separate_process_v1", "claude_separate_process_v1"}
    if runner_kind not in process_runners | {"codex_collaboration_v1"}:
        blockers.append("verifier_isolation_receipt_runner_invalid")
    if receipt.get("host_enforced") is not True:
        blockers.append("verifier_isolation_receipt_not_host_enforced")

    dispatch_id = _text(receipt.get("dispatch_id"))
    dispatch = next((
        item for item in state.get("claim_verifier_dispatches", [])
        if isinstance(item, dict) and item.get("dispatch_id") == dispatch_id
    ), None)
    if dispatch is None:
        blockers.append("verifier_isolation_receipt_dispatch_unknown")
    else:
        if receipt.get("claim_ids") != dispatch.get("claim_ids"):
            blockers.append("verifier_isolation_receipt_claim_ids_mismatch")
        if receipt.get("snapshot_ids") != dispatch.get("snapshot_ids"):
            blockers.append("verifier_isolation_receipt_snapshot_ids_mismatch")

    role = receipt.get("verifier") if isinstance(receipt.get("verifier"), dict) else {}
    if not _text(role.get("invocation_id")):
        blockers.append("verifier_isolation_receipt_invocation_missing")
    if runner_kind in process_runners:
        try:
            process_id = int(role.get("process_id"))
        except (TypeError, ValueError):
            process_id = 0
        if process_id <= 0:
            blockers.append("verifier_isolation_receipt_process_missing")
        if role.get("exit_code") != 0 or role.get("timed_out") is not False:
            blockers.append("verifier_isolation_receipt_process_failed")
    elif runner_kind == "codex_collaboration_v1":
        if not _text(role.get("agent_id")):
            blockers.append("verifier_isolation_receipt_agent_missing")
        if role.get("context_isolation") != "independent_agent_context":
            blockers.append("verifier_isolation_receipt_context_not_isolated")
        if role.get("status") != "completed" or role.get("timed_out") is not False:
            blockers.append("verifier_isolation_receipt_agent_failed")
    expected_prompt = (dispatch or {}).get("prompt_sha256")
    if not expected_prompt or role.get("prompt_sha256") != expected_prompt:
        blockers.append("verifier_isolation_receipt_prompt_hash_mismatch")
    if role.get("payload_sha256") != candidate_screen_engine.payload_sha256(verifier_payload):
        blockers.append("verifier_isolation_receipt_payload_hash_mismatch")
    expected_id = isolation_receipt_id(receipt)
    if receipt.get("receipt_id") != expected_id:
        blockers.append("verifier_isolation_receipt_id_mismatch")
    unique = list(dict.fromkeys(blockers))
    return {
        "status": "verified" if not unique else "invalid",
        "receipt_id": receipt.get("receipt_id") or "",
        "blockers": unique,
    }


def latest_verifications(state):
    out = {}
    for item in state.get("claim_verifications", []):
        if isinstance(item, dict) and item.get("claim_id"):
            out[item["claim_id"]] = item
    return out


def _normalize_result(request, snapshot, result, isolation_status):
    result = result if isinstance(result, dict) else {}
    verdict = _text(result.get("verdict")).upper()
    if verdict not in VERDICTS:
        verdict = "INSUFFICIENT"
    quote = evidence_snapshot.normalize_text(result.get("exact_quote"))
    reason = _text(result.get("reason"))
    flags = []
    if result.get("snapshot_id") != snapshot["snapshot_id"]:
        flags.append("snapshot_id_mismatch")
        verdict = "INSUFFICIENT"
    if verdict != "INSUFFICIENT":
        if not quote:
            flags.append("missing_exact_quote")
            verdict = "INSUFFICIENT"
        elif len(quote) > MAX_QUOTE_CHARS or len(quote.split()) > MAX_QUOTE_WORDS:
            flags.append("exact_quote_too_long")
            verdict = "INSUFFICIENT"
        elif quote not in snapshot["text"]:
            flags.append("exact_quote_not_in_snapshot")
            verdict = "INSUFFICIENT"
        elif not reason:
            flags.append("missing_reason")
            verdict = "INSUFFICIENT"
    if isolation_status != "verified" and verdict in {"SUPPORTS", "CONTRADICTS"}:
        flags.append("verifier_isolation_unverified")
    effective = verdict if isolation_status == "verified" else "INSUFFICIENT"
    return {
        "claim_id": request["claim_id"],
        "citation": request["citation"],
        "contexts": request["contexts"],
        "snapshot_id": snapshot["snapshot_id"],
        "snapshot_manifest": _manifest(snapshot),
        "verdict": verdict,
        "effective_verdict": effective,
        "exact_quote": quote if verdict != "INSUFFICIENT" else "",
        "quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest() if quote else "",
        "locator": _text(result.get("locator")),
        "reason": reason,
        "quality_flags": flags,
        "verifier_isolation": isolation_status,
        "verified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def _recompute_screen_states(state):
    latest = latest_verifications(state)
    for screen in state.get("candidate_screens", []):
        if not isinstance(screen, dict) or screen.get("status") != "THESIS_CANDIDATE":
            continue
        gaps, contradictions, any_support = [], [], False
        for dimension, combined in screen.get("dimensions", {}).items():
            if combined.get("state") != "SUPPORTED":
                continue
            for side in ("analyst", "skeptic"):
                assessment = combined.get(side, {})
                evidence = assessment.get("fresh_evidence", assessment.get("evidence", []))
                verdicts = [
                    latest.get(claim_id(citation), {}).get("effective_verdict")
                    for citation in evidence
                    if claim_id(citation)
                ]
                if "CONTRADICTS" in verdicts:
                    contradictions.append(f"{dimension}:{side}")
                if "SUPPORTS" in verdicts:
                    any_support = True
                else:
                    gaps.append(f"{dimension}:{side}")
        if contradictions:
            status = "CONTRADICTED"
        elif not gaps:
            status = "VERIFIED"
        elif any_support:
            status = "PARTIALLY_VERIFIED"
        else:
            status = "PENDING"
        screen["claim_verification_status"] = status
        screen["claim_verification_gaps"] = gaps
        screen["claim_contradictions"] = contradictions
        packet = screen.get("promotion_packet")
        if packet:
            if status == "VERIFIED":
                packet["status"] = "DRAFT_REQUIRES_HUMAN"
                packet["required_next_step"] = (
                    "页面快照与 claim 已对齐；人工抽查后，以独立 topic 重新运行 -deepthink2；"
                    "不得继承根命题支持度。"
                )
            elif status == "CONTRADICTED":
                packet["status"] = "BLOCKED_CLAIM_CONFLICT"
                packet["required_next_step"] = "先解决来源内容与 claim 的冲突，禁止升级新 Thesis。"
            else:
                packet["status"] = "DRAFT_REQUIRES_SOURCE_VERIFICATION"
                packet["required_next_step"] = "完成页面快照与 claim 对齐后，才可进入人工升级。"


def apply_verifier_results(state, snapshots_payload, verifier_payload, seed_id=None,
                           requested_claim_id=None, isolation_status="unverified",
                           isolation_receipt=None):
    claimed_isolation_status = _text(isolation_status).lower()
    if claimed_isolation_status not in {"verified", "degraded", "unverified"}:
        claimed_isolation_status = "unverified"
    receipt_validation = validate_isolation_receipt(
        state, isolation_receipt, verifier_payload
    )
    # A string supplied beside the verifier payload is self-attestation.  Only
    # a validated host receipt may unlock SUPPORTS/CONTRADICTS as effective.
    isolation_status = (
        "verified" if receipt_validation["status"] == "verified" else "unverified"
    )
    requests = collect_claim_requests(state, seed_id)
    if requested_claim_id:
        requests = [item for item in requests if item["claim_id"] == requested_claim_id]
    request_map = {item["claim_id"]: item for item in requests}
    snapshots, rejected = normalize_snapshots(snapshots_payload)
    results = _verifier_results(verifier_payload)
    stored = state.setdefault("claim_verifications", [])
    by_key = {
        (item.get("claim_id"), item.get("snapshot_id")): i
        for i, item in enumerate(stored) if isinstance(item, dict)
    }
    accepted, missing_snapshot, unknown = 0, [], []
    replayed, conflicts, pending = [], [], []
    for cid, result in results.items():
        request = request_map.get(cid)
        if not request:
            unknown.append(cid)
            continue
        snapshot = snapshots.get(_url_identity(request["citation"].get("url", "")))
        if not snapshot:
            missing_snapshot.append(cid)
            continue
        key = (cid, snapshot["snapshot_id"])
        submission_sha256 = candidate_screen_engine.payload_sha256({
            "schema": "claim-verification-submission.v1",
            "claim_request": request,
            "snapshot_manifest": _manifest(snapshot),
            "verifier_result": result,
            "claimed_isolation_status": claimed_isolation_status,
            "effective_isolation_status": isolation_status,
            "isolation_receipt_binding": {
                "schema": (isolation_receipt or {}).get("schema")
                if isinstance(isolation_receipt, dict) else "",
                "runner_kind": (isolation_receipt or {}).get("runner_kind")
                if isinstance(isolation_receipt, dict) else "",
                "dispatch_id": (isolation_receipt or {}).get("dispatch_id")
                if isinstance(isolation_receipt, dict) else "",
            },
        })
        if key in by_key:
            existing = stored[by_key[key]]
            if existing.get("submission_sha256") == submission_sha256:
                replayed.append(cid)
            else:
                conflicts.append(cid)
        else:
            pending.append((cid, request, snapshot, result, submission_sha256))
    if conflicts:
        return {
            "accepted_verifications": 0,
            "replayed_claim_ids": replayed,
            "conflicting_claim_ids": conflicts,
            "unknown_claim_ids": unknown,
            "missing_snapshot_claim_ids": missing_snapshot,
            "rejected_snapshots": rejected,
            **summary(state),
        }
    for cid, request, snapshot, result, submission_sha256 in pending:
        normalized = _normalize_result(request, snapshot, result, isolation_status)
        normalized.update({
            "claimed_verifier_isolation": claimed_isolation_status,
            "verifier_isolation_receipt_status": receipt_validation["status"],
            "verifier_isolation_receipt_id": receipt_validation["receipt_id"],
            "verifier_isolation_receipt_blockers": receipt_validation["blockers"],
        })
        normalized["submission_sha256"] = submission_sha256
        key = (cid, snapshot["snapshot_id"])
        stored.append(normalized)
        by_key[key] = len(stored) - 1
        accepted += 1
    manifests = state.setdefault("source_snapshots", [])
    manifest_ids = {item.get("snapshot_id") for item in manifests if isinstance(item, dict)}
    for snapshot in snapshots.values():
        if snapshot["snapshot_id"] not in manifest_ids:
            manifests.append(_manifest(snapshot))
            manifest_ids.add(snapshot["snapshot_id"])
    _recompute_screen_states(state)
    opportunity_engine.refresh_candidate_states(state)
    return {
        "accepted_verifications": accepted,
        "replayed_claim_ids": replayed,
        "conflicting_claim_ids": [],
        "unknown_claim_ids": unknown,
        "missing_snapshot_claim_ids": missing_snapshot,
        "rejected_snapshots": rejected,
        "claimed_verifier_isolation": claimed_isolation_status,
        "effective_verifier_isolation": isolation_status,
        "verifier_isolation_receipt_status": receipt_validation["status"],
        "verifier_isolation_receipt_id": receipt_validation["receipt_id"],
        "verifier_isolation_receipt_blockers": receipt_validation["blockers"],
        **summary(state),
    }


def summary(state):
    latest = candidate_screen_engine.latest_by_seed(state)
    counts = {"PENDING": 0, "PARTIALLY_VERIFIED": 0, "VERIFIED": 0, "CONTRADICTED": 0}
    for screen in latest.values():
        if screen.get("status") != "THESIS_CANDIDATE":
            continue
        status = screen.get("claim_verification_status", "PENDING")
        if status in counts:
            counts[status] += 1
    return {
        "claim_verification_count": len(latest_verifications(state)),
        "verified_thesis_candidate_count": counts["VERIFIED"],
        "partially_verified_candidate_count": counts["PARTIALLY_VERIFIED"],
        "contradicted_candidate_count": counts["CONTRADICTED"],
        "pending_verification_candidate_count": counts["PENDING"],
    }
