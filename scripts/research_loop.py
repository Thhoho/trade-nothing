#!/usr/bin/env python3
"""Thin ActionIntent-driven runtime for the Trade Nothing research core."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import research_core
import research_io
import research_report
import research_registry


REPORT_BUNDLE_SCHEMA = "trade-nothing.report-bundle.v2"
REPORT_RENDERER_VERSION = "research-report.v2"


def _json_load(value):
    if not value:
        return {}
    if os.path.isfile(value):
        with open(value, encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(value)


def _context(run_id):
    context = research_registry.load_manifest(run_id)
    research_registry.bind_context(context)
    return context


def _load(run_id, *, require_written_snapshot=False):
    context = _context(run_id)
    run = research_io.load_json(context["state_path"], default=None)
    if not isinstance(run, dict):
        raise research_core.ResearchContractError(["run.state_missing"])
    research_core.validate_persisted_run(run, require_written_snapshot=False)
    if run["run_ledger"].get("method_identity") != context.get("method_identity"):
        raise research_core.ResearchContractError(["run.method_identity_mismatch"])
    if run["task_spec"].get("question") != context.get("topic"):
        raise research_core.ResearchContractError(["run.question_manifest_mismatch"])
    if run["task_spec"].get("as_of") != context.get("as_of_date"):
        raise research_core.ResearchContractError(["run.as_of_manifest_mismatch"])
    if run["run_ledger"].get("execution_mode") != context.get(
        "requested_execution_mode"
    ):
        raise research_core.ResearchContractError([
            "run.execution_mode_manifest_mismatch"
        ])
    if require_written_snapshot:
        research_core.validate_persisted_run(run)
    return context, run


def _save(context, run, *, create=False):
    return research_io.save_run_cas(
        context["state_path"], run,
        expected_revision=run["run_ledger"].get("state_revision", 0),
        create=create,
    )


def _hash_payload(payload):
    return hashlib.sha256(
        research_core.canonical_json(payload).encode("utf-8")
    ).hexdigest()


def _renderer_sha256():
    return hashlib.sha256(Path(research_report.__file__).read_bytes()).hexdigest()


def verify_report_bundle(run_id, bundle_path):
    """Recompute every state, renderer and artifact binding before delivery."""
    context, run = _load(run_id, require_written_snapshot=True)
    if run["run_ledger"].get("next_call") != "REPORT":
        raise research_core.ResearchContractError(["report.run_not_stopped"])
    bundle_file = Path(bundle_path).expanduser().resolve()
    artifact_root = (research_registry.run_dir(run_id) / "artifacts").resolve()
    try:
        bundle_file.relative_to(artifact_root)
    except ValueError as exc:
        raise ValueError("report_bundle_outside_run_artifacts") from exc
    bundle_bytes = bundle_file.read_bytes()
    bundle_sha256 = hashlib.sha256(bundle_bytes).hexdigest()
    if bundle_file.name != f"report-bundle-{bundle_sha256[:16]}.json":
        raise ValueError("report_bundle_content_address_mismatch")
    if bundle_file.stat().st_mode & 0o222:
        raise ValueError("report_bundle_not_read_only")
    try:
        bundle = json.loads(bundle_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("report_bundle_invalid_json") from exc
    expected_fields = {
        "schema_version", "run_id", "state_revision", "task_spec_sha256",
        "evidence_store_sha256", "decision_snapshot_sha256",
        "run_ledger_sha256", "research_run_sha256", "method_identity_sha256",
        "renderer_version", "renderer_sha256",
        "views",
    }
    if not isinstance(bundle, dict) or set(bundle) != expected_fields:
        raise ValueError("report_bundle_fields_invalid")
    if bundle_bytes != (
        research_registry.canonical_json(bundle) + "\n"
    ).encode("utf-8"):
        raise ValueError("report_bundle_not_canonical")
    expected = {
        "schema_version": REPORT_BUNDLE_SCHEMA,
        "run_id": run_id,
        "state_revision": run["run_ledger"].get("state_revision"),
        "task_spec_sha256": research_core.stable_hash(run["task_spec"]),
        "evidence_store_sha256": research_core.stable_hash(run["evidence_store"]),
        "decision_snapshot_sha256": research_core.snapshot_hash(
            run["decision_snapshot"]
        ),
        "run_ledger_sha256": research_core.stable_hash(run["run_ledger"]),
        "research_run_sha256": research_core.stable_hash(run),
        "method_identity_sha256": research_core.stable_hash(
            run["run_ledger"]["method_identity"]
        ),
        "renderer_version": REPORT_RENDERER_VERSION,
        "renderer_sha256": _renderer_sha256(),
    }
    for field, value in expected.items():
        if bundle.get(field) != value:
            raise ValueError(f"report_bundle_binding_mismatch:{field}")
    views = bundle.get("views")
    if not isinstance(views, dict) or set(views) != {"user", "audit"}:
        raise ValueError("report_bundle_views_invalid")
    rendered_views = {
        "user": research_report.render(run, view="user").encode("utf-8"),
        "audit": research_report.render(run, view="audit").encode("utf-8"),
    }
    for view, expected_bytes in rendered_views.items():
        meta = views.get(view)
        if not isinstance(meta, dict) or set(meta) != {"path", "sha256", "bytes"}:
            raise ValueError(f"report_bundle_view_metadata_invalid:{view}")
        path = Path(meta["path"]).expanduser().resolve()
        try:
            path.relative_to(artifact_root)
        except ValueError as exc:
            raise ValueError(f"report_bundle_view_outside_run:{view}") from exc
        actual = path.read_bytes()
        actual_sha = hashlib.sha256(actual).hexdigest()
        if path.name != f"report-{view}-{actual_sha[:16]}.md":
            raise ValueError(f"report_bundle_view_content_address_mismatch:{view}")
        if (
            actual != expected_bytes
            or meta.get("sha256") != actual_sha
            or meta.get("bytes") != len(actual)
        ):
            raise ValueError(f"report_bundle_view_content_mismatch:{view}")
        if path.stat().st_mode & 0o222:
            raise ValueError(f"report_bundle_view_not_read_only:{view}")
    return {
        "status": "report_bundle_verified",
        "run_id": context["run_id"],
        "bundle_path": str(bundle_file),
        "bundle_sha256": bundle_sha256,
        "renderer_sha256": expected["renderer_sha256"],
    }


def _lead_prompt(working_set, *, resolution=False):
    mode = "CHALLENGE_RESOLUTION" if resolution else "RESEARCH"
    evidence_writes_allowed = working_set.get("next_call") == "LEAD_RESEARCH"
    contract = {
        "action_intent": {
            "action_type": "RESOLUTION" if resolution else "RESEARCH",
            "target_snapshot_field": "allowed field",
            "current_uncertainty": "uncertainty",
            "evidence_needed": "needed evidence",
            "expected_decision_delta": "possible decision change",
            "stop_condition": "completion condition",
            "cost_bound": "bounded cost",
        },
        "evidence_items": [{
            "evidence_id": "EV-...",
            "claim": "sourced claim without measure values",
            "number": None,
            "measures": [{
                "measure_id": "MEASURE-...", "metric": "financing_amount",
                "value": 1.0, "unit": "CNY_100M", "dimension": "CURRENCY",
                "subject_id": "E1 or 300001@XSHE",
                "as_of": "YYYY-MM-DD", "period": "POINT_IN_TIME",
                "basis": "DISCLOSURE_REPORTED",
            }],
            "document_facts": [],
            "roles": ["CURRENT_REALITY", "ECONOMIC_EXPOSURE"],
            "source": "publisher",
            "url": "concrete URL",
            "date": "YYYY-MM-DD",
            "source_tier": "PRIMARY",
            "boundary": "FACT",
            "decision_impact": "HIGH",
            "entity_ids": ["E1"],
            "security_ids": ["300001@XSHE"],
            "fact_surface": "TaskSpec surface",
            "claim_ids": ["CORE-1"],
        }] if evidence_writes_allowed else [],
        "source_checks": [{
            "source_check_id": "SC-...",
            "entity_id": "E1",
            "security_id": "300001@XSHE or empty",
            "fact_surface": "TaskSpec surface",
            "window_start": "YYYY-MM-DD",
            "window_end": "as-of date",
            "window_basis": "LATEST_PERIODIC_REPORT_OR_120D or empty",
            "latest_periodic_report_date": "YYYY-MM-DD or empty",
            "index_item_count": 0,
            "index_entries": [{
                "title": "every index title",
                "url": "announcement URL",
                "date": "YYYY-MM-DD",
                "disposition": "OPENED_RELEVANT/REVIEWED_NOT_MATERIAL/DISMISSED_BY_TITLE",
                "reason": "specific reason",
            }],
            "queries": ["actual query"],
            "official_index_url": "index URL or empty",
            "checked_document_urls": ["document URL"],
            "acquisition_receipt_ids": ["adapter receipt SHA-256"],
            "enumeration_complete": False,
            "outcome": "FOUND/NO_RESULT/INSUFFICIENT",
            "evidence_ids": ["EV-..."],
            "negative_scope": "NO_RESULT scope",
            "limitation": "limitation",
        }] if evidence_writes_allowed else [],
        "decision_snapshot": {
            "schema_version": research_core.SNAPSHOT_SCHEMA,
            "version": int(working_set["decision_snapshot"].get("version", 0)) + 1,
            "base_snapshot_sha256": working_set["base_snapshot_sha256"],
            "as_of": working_set["task_spec"]["as_of"],
            "decision_status": "RESEARCH_INCOMPLETE",
            "core_judgment": {
                "claim_id": "CORE-1", "summary": "answer", "boundary": "FACT",
                "evidence_ids": ["EV-..."],
            },
            "boundary": "explicit limitation",
            "material_changes": [],
            "open_material_gaps": [{
                "gap_id": "stable id from material_gap_requirements",
                "description": "gap", "evidence_ids": [],
            }],
            "agenda_answers": [{
                "question_id": "RQ1", "question": "question", "status": "PARTIAL",
                "answer": "answer", "boundary": "FACT", "evidence_ids": [],
                "self_countercase": "Lead countercase", "missing_information": "gap",
                "next_test_availability": "SEARCH_NOW",
            }],
            "value_transfer_paths": [{
                "path_id": "VP-1", "constraint_change": "fact-to-constraint",
                "profit_pool_shift": "who captures value", "economic_exposure": "company exposure",
                "market_carrier": "trading carrier", "boundary": "INFERENCE",
                "evidence_ids": ["EV-..."],
            }],
            "market_by_horizon": [{
                "market_view_id": "MV-1", "horizon": "EVENT_DAYS",
                "current_state": "market state", "mechanism": "trading mechanism",
                "switch_condition": "state change", "boundary": "INFERENCE",
                "evidence_ids": ["EV-..."],
            }],
            "market_carriers_by_horizon": [{
                "horizon": "EVENT_DAYS", "carriers": [{
                    "claim_id": "CARRIER-1", "name": "observed security",
                    "ticker": "ticker", "exchange": "exchange",
                    "market_role": "trading role", "why_traded": "market logic",
                    "closest_alternative": "UNKNOWN or ticker@MIC",
                    "switch_condition": "switch",
                    "boundary": "INFERENCE",
                    "market_evidence_ids": ["EV-..."],
                    "alternative_evidence_ids": [],
                    "evidence_ids": ["EV-..."]
                }]
            }],
            "candidates_by_horizon": [{
                "horizon": "EVENT_DAYS", "candidates": [{
                    "claim_id": "CAND-1", "stance": "WATCH",
                    "name": "company", "ticker": "ticker", "exchange": "exchange",
                    "economic_exposure": "exposure", "market_role": "trading role",
                    "why_now": "reason", "closest_alternative": "UNKNOWN or ticker@MIC",
                    "switch_condition": "switch", "trigger": "trigger",
                    "invalidation": "invalidation", "price_crowding_boundary": "boundary",
                    "boundary": "INFERENCE",
                    "value_path_ids": ["VP-1"],
                    "exposure_evidence_ids": ["EV-..."],
                    "market_evidence_ids": ["EV-..."],
                    "alternative_evidence_ids": [],
                    "evidence_ids": ["EV-..."]
                }]
            }],
            "self_countercases": [],
            "challenge_resolutions": ([{
                "challenge_id": "receipt-backed challenge only",
                "challenge_packet_sha256": "exact latest_challenge_packet_sha256",
                "target_claim_ids": ["CORE-1"],
                "resolution": "PARTIAL", "summary": "countercase",
                "lead_response": "Lead resolution",
                "evidence_ids": []
            }] if resolution else []),
            "unresolved_questions": [],
            "lowest_cost_next_validation": [],
            "consumed_evidence_ids": ["exact visible evidence union"],
            "non_material_evidence_dispositions": [{
                "evidence_id": "EV-...",
                "decision_dimension": "one WORKING SET material decision dimension",
                "reason": "specific reason this does not change the decision",
                "reversal_condition": "observable condition that requires reassessment",
            }],
        },
        "challenge_request": None if resolution else {
            "challenge_id": "stable ID", "target_claim_ids": ["CORE-1"],
            "question": "attack request", "why_load_bearing": "decision effect",
        },
        "continue_research": False,
        "stop_reason": "why stop",
    }
    instructions = [
        f"You are the Trade Nothing Value Lead in {mode} mode.",
        "You are the only semantic writer of DecisionSnapshot.",
        "Use tools only for a justified ActionIntent; keep no parallel semantic state.",
        "Reality first: use the host official index before thematic search and open every potentially HIGH listed-company event. Without it, preserve a material gap.",
        "A SourceCheck is complete only when it records actual queries and concrete checked URLs. NO_RESULT requires a bounded negative scope.",
        "Bind every new EvidenceItem by evidence_id to a same-packet SourceCheck; evidence dumps are rejected.",
        "OFFICIAL_DISCLOSURE_INDEX and document_facts are host-only. Never author body excerpts or claim host acquisition; use WorkingSet host facts.",
        "Account every HIGH or marker-title EvidenceItem in one outcome: material_changes, open_material_gaps, or reasoned non_material_evidence_disposition. Marker evidence needs host document facts. One event family is one aggregate, never one per document.",
        "No unit-bearing numeric prose. Put raw values only in typed measures; the deterministic renderer owns display.",
        "Use only WORKING SET.measure_contract metrics and bases. Omit definition; the registry supplies it. Every measure has one explicit subject_id.",
        "Self-countercase is not Challenger output. In Codex use one native child Challenger; CLI processes are optional. Add challenge_resolutions only during Lead resolution.",
        "The Snapshot is a full replacement, not a patch. Preserve still-valid prior semantics, but update stale conclusions.",
        "If last_contract_rejection is present, repair each listed contract error; do not repeat the rejected payload shape or invent semantic state to bypass validation.",
        "Use the exact version, base hash and as-of supplied below. consumed_evidence_ids must equal the union of all evidence IDs visible in the Snapshot.",
        "If material_gap_requirements remain, use their stable gap_id in open_material_gaps and use MATERIAL_FACT_GAP (or RUNTIME_DEGRADED after a real failure). Runtime obligation IDs are not user semantics.",
        "Candidate stances are exactly CONDITIONAL_PRIORITY, WATCH, EXPLORE, or NO_SETUP; AVOID, SHORT, BUY, and SELL are invalid. WATCH and EXPLORE are research states, not recommendations.",
        "Name market carriers even without a qualified candidate. WATCH requires a concrete security plus role-qualified industry-exposure and market evidence, why-now, trigger, invalidation and crowding boundary. CONDITIONAL_PRIORITY additionally requires a connected value path and DECISION_READY.",
        "Represent no setup with an empty candidates list (preferred) or a completely empty NO_SETUP sentinel; never attach another ticker or borrowed evidence to NO_SETUP.",
        "Request Challenger only for a load-bearing claim that could change the Snapshot and only when remaining budget is available.",
        "Return one JSON object matching OUTPUT CONTRACT; no prose.",
    ]
    if not evidence_writes_allowed:
        instructions.insert(
            3,
            "This is a no-search synthesis/resolution call: do not browse, call data tools, or add EvidenceItems/SourceChecks. Use only the supplied EvidenceStore and ChallengePacket.",
        )
    return "\n".join(instructions) + "\n\nWORKING SET:\n" + json.dumps(
        working_set, ensure_ascii=False, separators=(",", ":")
    ) + "\n\nOUTPUT CONTRACT:\n" + json.dumps(
        contract, ensure_ascii=False, separators=(",", ":")
    )


def _challenger_prompt(working_set):
    request = working_set.get("pending_challenge_request") or {}
    contract = {
        "challenge_id": request.get("challenge_id"),
        "target_claim_ids": request.get("target_claim_ids", []),
        "evidence_items": [{
            "evidence_id": "EV-...",
            "claim": "source-supported qualitative counterevidence",
            "number": None,
            "measures": [{
                "measure_id": "MEASURE-...", "metric": "financing_amount",
                "value": 1.0, "unit": "CNY", "dimension": "CURRENCY",
                "subject_id": "E1 or 300001@XSHE",
                "as_of": "YYYY-MM-DD", "period": "POINT_IN_TIME/SESSION/5D/etc",
                "basis": "DISCLOSURE_REPORTED",
            }],
            "document_facts": [],
            "roles": ["CURRENT_REALITY/RISK/MARKET_STATE/etc"],
            "source": "publisher",
            "url": "concrete URL",
            "date": "YYYY-MM-DD no later than as-of",
            "source_tier": "PRIMARY/OFFICIAL/etc",
            "boundary": "FACT/SINGLE_SOURCE/INFERENCE/HYPOTHESIS",
            "decision_impact": "HIGH/MEDIUM/LOW",
            "entity_ids": ["E1"],
            "security_ids": ["300001@XSHE when this evidence is security-specific"],
            "fact_surface": "surface from TaskSpec",
            "claim_ids": ["exact target claim ID"],
        }],
        "source_checks": [{
            "source_check_id": "SC-...",
            "entity_id": "E1",
            "security_id": "ticker@MIC when security-specific",
            "fact_surface": "surface from TaskSpec",
            "window_start": "YYYY-MM-DD",
            "window_end": "as-of date",
            "window_basis": "",
            "latest_periodic_report_date": "",
            "index_item_count": 0,
            "index_entries": [],
            "queries": ["actual query"],
            "official_index_url": "",
            "checked_document_urls": ["exact EvidenceItem URL"],
            "acquisition_receipt_ids": [],
            "enumeration_complete": False,
            "outcome": "FOUND/NO_RESULT/INSUFFICIENT",
            "evidence_ids": ["EV-..."],
            "negative_scope": "required for NO_RESULT",
            "limitation": "bounded limitation",
        }],
        "attacks": [{
            "target_claim_id": "exact target claim ID",
            "argument": "strongest evidence-bounded countercase",
            "evidence_ids": ["EV-..."],
            "severity": "LOAD_BEARING",
        }],
        "strongest_countercase": "single clearest countercase",
    }
    return "\n".join([
        "You are the bounded Trade Nothing Targeted Challenger assigned its own host context.",
        "Attack only the supplied load-bearing claims. Do not redo the whole topic, rank a new universe, or write DecisionSnapshot.",
        "You may find new evidence. Every fact requires publisher, concrete URL and date no later than as-of.",
        "Never write a unit-bearing numeric value in prose, including claims, attacks, definitions or basis. Put the raw value only in a typed measure; the deterministic renderer owns display.",
        "Use only WORKING SET.measure_contract metrics and bases. Omit definition; the registry supplies it. Every measure has one explicit subject_id.",
        "Every new EvidenceItem must be bound to a SourceCheck in this same packet. document_facts are host-input-only and must remain empty. If no new evidence is needed, return both arrays empty.",
        "Return exactly one JSON ChallengePacket. Do not claim that the Lead accepted your attack.",
        "",
        "WORKING SET:",
        json.dumps(working_set, ensure_ascii=False, separators=(",", ":")),
        "",
        "OUTPUT CONTRACT:",
        json.dumps(contract, ensure_ascii=False, separators=(",", ":")),
    ])


def dispatch(run):
    working_set = research_core.compile_working_set(run)
    next_call = working_set["next_call"]
    if next_call in {"LEAD_RESEARCH", "LEAD_SYNTHESIS"}:
        role = "LEAD"
        prompt = _lead_prompt(working_set, resolution=False)
    elif next_call == "CHALLENGER":
        role = "CHALLENGER"
        prompt = _challenger_prompt(working_set)
    elif next_call == "LEAD_RESOLUTION":
        role = "LEAD"
        prompt = _lead_prompt(working_set, resolution=True)
    elif next_call == "REPORT":
        return {
            "status": "ready_for_report",
            "working_set": working_set,
            "instruction": "Render the current DecisionSnapshot; do not start another research loop without explicit authorization.",
        }
    else:
        raise research_core.ResearchContractError([f"dispatch.next_call_invalid:{next_call}"])
    return {
        "status": "dispatch_model",
        "role": role,
        "call_mode": next_call,
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "working_set": working_set,
        "instruction": f"Invoke exactly one {role} call for {next_call}; submit its JSON with a host receipt.",
    }


def _dispatch_and_bind(context, run, *, persist=False, create=False):
    result = dispatch(run)
    bound = run
    if result.get("status") == "dispatch_model":
        bound = research_core.bind_dispatch(
            run,
            call_mode=result["call_mode"],
            role=result["role"],
            prompt_sha256=result["prompt_sha256"],
        )
    if create or persist or bound != run:
        bound = _save(context, bound, create=create)
    return result, bound


def cmd_start(topic, raw_spec, *, frame=None, round_budget=1,
              run_purpose="PRODUCTION_RESEARCH", execution_mode=None):
    execution_mode = research_core.text(execution_mode).upper()
    if not execution_mode:
        raise research_core.ResearchContractError([
            "start.execution_mode_required"
        ])
    seed_evidence = list(raw_spec.get("seed_evidence_items", [])) if isinstance(
        raw_spec, dict
    ) and isinstance(raw_spec.get("seed_evidence_items"), list) else []
    seed_checks = list(raw_spec.get("seed_source_checks", [])) if isinstance(
        raw_spec, dict
    ) and isinstance(raw_spec.get("seed_source_checks"), list) else []
    if frame:
        raw_spec = research_core.task_spec_from_frame(
            frame, question=topic, round_budget=round_budget
        )
    if not isinstance(raw_spec, dict) or not isinstance(
        raw_spec.get("primary_entities"), list
    ) or not raw_spec.get("primary_entities") or not isinstance(
        raw_spec.get("questions"), list
    ) or not raw_spec.get("questions"):
        raise research_core.ResearchContractError([
            "start.explicit_primary_entities_and_questions_required"
        ])
    spec = research_core.normalize_task_spec(
        raw_spec, fallback_question=topic, round_budget=round_budget
    )
    context = research_registry.create_manifest(
        spec["question"], as_of_date=spec["as_of"],
        requested_execution_mode=execution_mode, run_purpose=run_purpose,
    )
    run = research_core.new_research_run(
        spec, context["method_identity"], execution_mode=execution_mode
    )
    if seed_evidence or seed_checks:
        run = research_core.seed_research_run(run, seed_evidence, seed_checks)
    result, run = _dispatch_and_bind(context, run, create=True)
    result.update({
        "run_id": context["run_id"],
        "state_path": context["state_path"],
        "delivery_state": research_core.delivery_state(run),
    })
    return result


def cmd_dispatch(run_id):
    context, run = _load(run_id)
    result, run = _dispatch_and_bind(context, run)
    result.update({
        "run_id": run_id,
        "state_path": context["state_path"],
        "delivery_state": research_core.delivery_state(run),
    })
    return result


def cmd_submit_lead(run_id, packet, receipt):
    context, run = _load(run_id)
    resolution = run["run_ledger"].get("next_call") == "LEAD_RESOLUTION"
    try:
        updated = research_core.apply_lead_packet(
            run, packet, receipt, resolution=resolution
        )
    except research_core.ResearchContractError as exc:
        try:
            rejected = research_core.record_contract_rejection(
                run, packet, receipt, exc.errors
            )
        except research_core.ResearchContractError:
            pass
        else:
            _save(context, rejected)
        raise
    result, updated = _dispatch_and_bind(context, updated, persist=True)
    result.update({
        "run_id": run_id,
        "accepted_payload_sha256": _hash_payload(packet),
        "delivery_state": research_core.delivery_state(updated),
    })
    return result


def cmd_submit_challenge(run_id, packet, receipt):
    context, run = _load(run_id)
    try:
        updated = research_core.apply_challenge_packet(run, packet, receipt)
    except research_core.ResearchContractError as exc:
        try:
            rejected = research_core.record_contract_rejection(
                run, packet, receipt, exc.errors
            )
        except research_core.ResearchContractError:
            pass
        else:
            _save(context, rejected)
        raise
    result, updated = _dispatch_and_bind(context, updated, persist=True)
    result.update({
        "run_id": run_id,
        "accepted_payload_sha256": _hash_payload(packet),
        "delivery_state": research_core.delivery_state(updated),
    })
    return result


def cmd_register_host_invocation(run_id, record):
    context, run = _load(run_id)
    updated = research_io.save_host_invocation_cas(
        context["state_path"], record,
        expected_revision=run["run_ledger"].get("state_revision", 0),
    )
    return {
        "status": "host_invocation_registered",
        "run_id": run_id,
        "invocation_id": record.get("invocation_id"),
        "delivery_state": research_core.delivery_state(updated),
    }


def cmd_ingest_host(run_id, fragment, *, input_id=""):
    context, run = _load(run_id)
    fragment = fragment if isinstance(fragment, dict) else {}
    updated = research_core.ingest_host_evidence(
        run,
        fragment.get("evidence_items", []),
        fragment.get("source_checks", []),
        input_id=input_id or fragment.get("input_id", ""),
    )
    result, updated = _dispatch_and_bind(context, updated, persist=True)
    result.update({
        "status": result.get("status"),
        "run_id": run_id,
        "delivery_state": research_core.delivery_state(updated),
    })
    return result


def cmd_report(run_id):
    context, run = _load(run_id, require_written_snapshot=False)
    if run["run_ledger"].get("next_call") != "REPORT":
        raise research_core.ResearchContractError(["report.run_not_stopped"])
    research_core.validate_persisted_run(run, require_written_snapshot=True)
    user_markdown = research_report.render(run, view="user")
    audit_markdown = research_report.render(run, view="audit")
    user_artifact = research_registry.save_derived_artifact(
        run_id, "report-user", user_markdown, suffix=".md"
    )
    audit_artifact = research_registry.save_derived_artifact(
        run_id, "report-audit", audit_markdown, suffix=".md"
    )
    bundle_body = {
        "schema_version": REPORT_BUNDLE_SCHEMA,
        "run_id": run_id,
        "state_revision": run["run_ledger"].get("state_revision"),
        "task_spec_sha256": research_core.stable_hash(run["task_spec"]),
        "evidence_store_sha256": research_core.stable_hash(run["evidence_store"]),
        "decision_snapshot_sha256": research_core.snapshot_hash(
            run["decision_snapshot"]
        ),
        "run_ledger_sha256": research_core.stable_hash(run["run_ledger"]),
        "research_run_sha256": research_core.stable_hash(run),
        "method_identity_sha256": research_core.stable_hash(
            run["run_ledger"]["method_identity"]
        ),
        "renderer_version": REPORT_RENDERER_VERSION,
        "renderer_sha256": _renderer_sha256(),
        "views": {
            "user": user_artifact,
            "audit": audit_artifact,
        },
    }
    bundle = research_registry.save_derived_artifact(
        run_id, "report-bundle", bundle_body, suffix=".json"
    )
    verification = verify_report_bundle(run_id, bundle["path"])
    return {
        "status": "report_data_ready",
        "run_id": run_id,
        "topic": context["topic"],
        "as_of_date": run["task_spec"]["as_of"],
        "report_markdown": user_markdown,
        "report_sha256": user_artifact["sha256"],
        "report_path": user_artifact["path"],
        "report_bytes": user_artifact["bytes"],
        "audit_report_sha256": audit_artifact["sha256"],
        "audit_report_path": audit_artifact["path"],
        "report_bundle_sha256": bundle["sha256"],
        "report_bundle_path": bundle["path"],
        "delivery_verified": True,
        "bundle_verification": verification,
        "delivery_state": research_core.delivery_state(run),
        "rendering_mode": "PURE_DECISION_SNAPSHOT_USER_AND_AUDIT",
        "instruction": (
            "Deliver report_markdown exactly. User and audit artifacts are content-addressed, "
            "read-only views whose state and renderer bindings passed verification; do not "
            "prepend, patch, or replace values."
        ),
    }


def cmd_status(run_id):
    context, run = _load(run_id)
    return {
        "status": "run_status",
        "run_id": run_id,
        "topic": context["topic"],
        "state_path": context["state_path"],
        "delivery_state": research_core.delivery_state(run),
        "method_identity": run["run_ledger"]["method_identity"],
    }


def cmd_authorize(run_id, extra_loops):
    context, run = _load(run_id)
    updated = research_io.save_authorization_cas(
        context["state_path"], extra_loops,
        expected_revision=run["run_ledger"].get("state_revision", 0),
    )
    result, updated = _dispatch_and_bind(context, updated)
    result.update({
        "status": result.get("status"),
        "run_id": run_id,
        "delivery_state": research_core.delivery_state(updated),
    })
    return result


def cmd_runtime_failure(run_id, role, reason, receipt_id=""):
    context, run = _load(run_id)
    updated = research_core.record_runtime_failure(
        run, role=role, reason=reason, receipt_id=receipt_id
    )
    updated = _save(context, updated)
    return {
        "status": "runtime_failure_recorded",
        "run_id": run_id,
        "delivery_state": research_core.delivery_state(updated),
        "instruction": "Deliver a degraded report if a Lead-authored Snapshot exists; do not auto-retry.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--topic", required=True)
    start.add_argument("--task-spec-json", default="")
    start.add_argument("--frame-json", default="")
    start.add_argument("--round-budget", type=int, default=1)
    start.add_argument("--run-purpose", default="PRODUCTION_RESEARCH",
                       choices=sorted(research_registry.RUN_PURPOSES))
    start.add_argument(
        "--execution-mode", required=True,
        choices=sorted(research_core.EXECUTION_MODES),
    )

    for name in ("dispatch", "report", "status"):
        command = sub.add_parser(name)
        command.add_argument("--run-id", required=True)

    verify_report = sub.add_parser("verify-report")
    verify_report.add_argument("--run-id", required=True)
    verify_report.add_argument("--bundle", required=True)

    submit_lead = sub.add_parser("submit-lead")
    submit_lead.add_argument("--run-id", required=True)
    submit_lead.add_argument("--packet", required=True)
    submit_lead.add_argument("--receipt", required=True)

    submit_challenge = sub.add_parser("submit-challenge")
    submit_challenge.add_argument("--run-id", required=True)
    submit_challenge.add_argument("--packet", required=True)
    submit_challenge.add_argument("--receipt", required=True)

    ingest_host = sub.add_parser("ingest-host")
    ingest_host.add_argument("--run-id", required=True)
    ingest_host.add_argument("--fragment", required=True)
    ingest_host.add_argument("--input-id", default="")

    authorize = sub.add_parser("authorize")
    authorize.add_argument("--run-id", required=True)
    authorize.add_argument("--extra-loops", required=True, type=int)

    failure = sub.add_parser("runtime-failure")
    failure.add_argument("--run-id", required=True)
    failure.add_argument("--role", required=True)
    failure.add_argument("--reason", required=True)
    failure.add_argument("--receipt-id", default="")

    args = parser.parse_args()
    try:
        if args.command == "start":
            raw_spec = _json_load(args.task_spec_json) if args.task_spec_json else {}
            frame = _json_load(args.frame_json) if args.frame_json else None
            result = cmd_start(
                args.topic, raw_spec, frame=frame, round_budget=args.round_budget,
                run_purpose=args.run_purpose, execution_mode=args.execution_mode,
            )
        elif args.command == "dispatch":
            result = cmd_dispatch(args.run_id)
        elif args.command == "submit-lead":
            result = cmd_submit_lead(
                args.run_id, _json_load(args.packet), _json_load(args.receipt)
            )
        elif args.command == "submit-challenge":
            result = cmd_submit_challenge(
                args.run_id, _json_load(args.packet), _json_load(args.receipt)
            )
        elif args.command == "ingest-host":
            result = cmd_ingest_host(
                args.run_id, _json_load(args.fragment), input_id=args.input_id
            )
        elif args.command == "report":
            result = cmd_report(args.run_id)
        elif args.command == "status":
            result = cmd_status(args.run_id)
        elif args.command == "verify-report":
            result = verify_report_bundle(args.run_id, args.bundle)
        elif args.command == "authorize":
            result = cmd_authorize(args.run_id, args.extra_loops)
        elif args.command == "runtime-failure":
            result = cmd_runtime_failure(
                args.run_id, args.role, args.reason, args.receipt_id
            )
    except (research_core.ResearchContractError, ValueError, OSError, json.JSONDecodeError) as exc:
        errors = exc.errors if isinstance(exc, research_core.ResearchContractError) else [str(exc)]
        result = {
            "status": "contract_rejected",
            "errors": errors,
            "instruction": "Repair the submitted artifact; do not retry the same failed call automatically.",
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
