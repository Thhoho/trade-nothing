#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trade Nothing v0.13.0 — Crux Orchestrator  (-deepthink2; the only research pipeline)

Deterministic state machine. Control flow lives in code; the LLM only produces content.

Flow:
  --frame  TOPIC                       -> emit Framer prompt (DEEP). Parent runs framer.md inline.
  --init   TOPIC --frame-json J        -> ingest frame; No-Edge early-exit OR create crux state
                                          + emit Round-1 dispatch (Detective+Inquisitor on all cruxes).
  --submit TOPIC --det J --inq J --judge J
                                       -> add any new cruxes; engine.submit_round(judge signals);
                                          decide: dispatch ONLY open cruxes, or ready_for_report.
  --report TOPIC                       -> emit compact formal report only after convergence.
  --resolution-memo TOPIC              -> emit non-formal memo + compact continuation packet.
  --resume-blocked TOPIC               -> explicitly extend a fuse-broken run after user approval.
  --record-exploration-design TOPIC    -> write one target/revision-bound design; no search.
  --plan-exploration TOPIC             -> freeze one idempotent, unauthorized attempt.
  --cancel-exploration-action TOPIC    -> cancel only an unapproved plan with a reason.
  --authorize-exploration TOPIC        -> record caller-attested authority for one action ID.
  --submit-exploration-result TOPIC    -> validate one bounded receipt or typed runtime failure.
  --screen TOPIC                       -> dispatch isolated Candidate Analyst + Skeptic on eligible seeds.
  --plan-candidate-gaps TOPIC          -> create bounded evidence tasks for blocked candidates.
  --submit-gap-evidence TOPIC          -> append one content-addressed evidence supplement.
  --close-gap-task TOPIC               -> terminate a bounded task without changing the seed.
  --submit-screen TOPIC                -> deterministic two-sided candidate gate.
  --verification-plan TOPIC            -> list source snapshots required for thesis candidates.
  --verify-claims TOPIC                 -> emit snapshot-bound Claim Verifier prompt.
  --submit-verification TOPIC           -> validate exact spans and update promotion gate.
  --runtime-failure TOPIC               -> emit a bounded non-formal host failure receipt.

Model tiering (see model_tiers.py): research, adversarial, screening, Judge, and synthesis = DEEP.
Detective & Inquisitor each round are scoped to OPEN cruxes only
(crux-scoping) -> fewer searches, faster convergence.
"""
import os, sys, re, json, argparse, hashlib
from copy import deepcopy
from datetime import date
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import crux_engine
import hypothesis_engine
import landscape_engine
import method_identity
import opportunity_engine
import candidate_gap_engine
import candidate_screen_engine
import claim_verification_engine
import framing_feasibility
import tracking_engine
import research_output
import run_registry
import research_start_packet
import temporal_contract
from utils import (
    CrossPlatformFileLock,
    get_scratch_dir,
    get_output_dir,
    get_evolution_path,
    load_json_safe,
    save_json_revision_cas,
)
try:
    from model_tiers import model_for
except Exception:
    def model_for(t): return "deep"



def _frame_artifact_policy():
    return {
        "mode": "inline_only",
        "allowed_persistence_roots": [get_scratch_dir(), get_output_dir()],
        "external_or_cloud_write": "requires_explicit_user_opt_in",
    }


def _present(value):
    return bool(str(value or "").strip())


LOGIC_RELATIONS = {
    "REQUIRED_FOR", "ALTERNATIVE_PATH", "CAUSAL_PRECEDES", "COMPARED_ON", "PRICING_FOR",
}


def _validate_logic_graph(graph, crux_roles):
    """Require an explicit, connected map so decision logic cannot infer topology from prose."""
    crux_ids = set(crux_roles)
    if not isinstance(graph, dict):
        return ["logic_graph_required"]
    issues = []
    root_id = str(graph.get("root_id", "")).strip()
    if not root_id:
        issues.append("logic_graph_root_id_required")
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        issues.append("logic_graph_nodes_required")
        nodes = []
    node_ids = set()
    node_types = {}
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            issues.append(f"logic_graph_node_{index + 1}_must_be_object")
            continue
        node_id = str(node.get("id", "")).strip()
        if not node_id:
            issues.append(f"logic_graph_node_{index + 1}_missing_id")
        elif node_id in node_ids:
            issues.append(f"logic_graph_duplicate_node_{node_id}")
        node_ids.add(node_id)
        node_type = str(node.get("node_type", "")).upper()
        node_types[node_id] = node_type
        if node_type not in {"QUESTION", "CRUX"}:
            issues.append(f"logic_graph_node_{index + 1}_invalid_type")
    if root_id and root_id not in node_ids:
        issues.append("logic_graph_root_missing_from_nodes")
    elif root_id and node_types.get(root_id) != "QUESTION":
        issues.append("logic_graph_root_must_be_question")
    missing_cruxes = sorted(set(crux_ids) - node_ids)
    if missing_cruxes:
        issues.append("logic_graph_missing_crux_nodes:" + ",".join(missing_cruxes))
    wrong_crux_types = sorted(cid for cid in crux_ids if node_types.get(cid) not in {None, "CRUX"})
    if wrong_crux_types:
        issues.append("logic_graph_crux_nodes_must_be_crux:" + ",".join(wrong_crux_types))

    edges = graph.get("edges")
    if not isinstance(edges, list):
        issues.append("logic_graph_edges_required")
        edges = []
    if crux_ids and not edges:
        issues.append("logic_graph_edges_required_for_cruxes")
    adjacency = {}
    relations_by_source = {}
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            issues.append(f"logic_graph_edge_{index + 1}_must_be_object")
            continue
        source = str(edge.get("from", "")).strip()
        target = str(edge.get("to", "")).strip()
        relation = str(edge.get("relation", "")).upper()
        if not source or not target:
            issues.append(f"logic_graph_edge_{index + 1}_missing_endpoint")
            continue
        if source not in node_ids or target not in node_ids:
            issues.append(f"logic_graph_edge_{index + 1}_unknown_node")
        if source == target:
            issues.append(f"logic_graph_edge_{index + 1}_self_loop")
        if relation not in LOGIC_RELATIONS:
            issues.append(f"logic_graph_edge_{index + 1}_invalid_relation")
        adjacency.setdefault(source, set()).add(target)
        relations_by_source.setdefault(source, set()).add(relation)

    def reaches_root(start):
        frontier, seen = [start], set()
        while frontier:
            current = frontier.pop()
            if current == root_id:
                return True
            if current in seen:
                continue
            seen.add(current)
            frontier.extend(adjacency.get(current, ()))
        return False

    disconnected = sorted(cid for cid in crux_ids if root_id and not reaches_root(cid))
    if disconnected:
        issues.append("logic_graph_cruxes_not_connected_to_root:" + ",".join(disconnected))
    expected_relations = {
        "THESIS_HINGE": {"REQUIRED_FOR", "CAUSAL_PRECEDES"},
        "OPPORTUNITY_PATH": {"ALTERNATIVE_PATH"},
        "PRICING": {"PRICING_FOR"},
        "COMPARISON_AXIS": {"COMPARED_ON"},
    }
    for cid, role in crux_roles.items():
        expected = expected_relations.get(role, set())
        if expected and not (relations_by_source.get(cid, set()) & expected):
            issues.append(f"logic_graph_relation_mismatch:{cid}:{role}")
    return issues


def _compact_text(value, limit=4000):
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[TRUNCATED_FOR_CONTEXT_BUDGET]"


def _bind_hypotheses_to_landscape(state):
    """Attach deterministic WH ids to the corresponding immutable path."""
    ledger = state.get("hypothesis_ledger")
    landscape = state.get("landscape_map")
    if not isinstance(ledger, dict) or not isinstance(landscape, dict):
        return
    by_statement = {
        " ".join(str(item.get("hypothesis") or "").lower().split()): item
        for item in ledger.get("hypotheses", [])
        if isinstance(item, dict) and item.get("hypothesis_id")
    }
    for path in landscape.get("paths", []):
        if not isinstance(path, dict):
            continue
        key = " ".join(str(path.get("hypothesis") or "").lower().split())
        hypothesis = by_statement.get(key)
        if not hypothesis:
            continue
        path["hypothesis_id"] = hypothesis["hypothesis_id"]
        context = hypothesis.setdefault("context", {})
        context.setdefault("landscape_path_id", path.get("path_id"))
        context.setdefault("origin_crux", path.get("linked_crux_id"))
        context["landscape_path_ids"] = sorted({
            str(value)
            for value in (
                *(context.get("landscape_path_ids") or []),
                path.get("path_id"),
            )
            if value
        })
        context["origin_cruxes"] = sorted({
            str(value)
            for value in (
                *(context.get("origin_cruxes") or []),
                path.get("linked_crux_id"),
            )
            if value
        })


def _validate_frame(frame):
    """Reject frames that can silently launder unsupported premises into the debate."""
    if not isinstance(frame, dict):
        return ["frame_must_be_json_object"]
    issues = []
    for field in ("decision_question", "horizon", "as_of_date", "unit_of_analysis", "thesis_seed"):
        if not _present(frame.get(field)):
            issues.append(f"missing_{field}")
    frame_as_of = None
    try:
        frame_as_of = date.fromisoformat(str(frame.get("as_of_date", "")))
    except ValueError:
        issues.append("as_of_date_requires_iso_date")
    try:
        temporal_contract.validate_question({
            "decision_question": frame.get("decision_question"),
            "horizon": frame.get("horizon"),
            "as_of_date": frame.get("as_of_date"),
            "forecast_target_date": frame.get("forecast_target_date"),
        }, prefix="frame")
    except temporal_contract.TemporalContractError as exc:
        issues.append(
            "temporal_contract_invalid:"
            + re.sub(r"\s+", "_", str(exc)).lower()
        )
    question_type = str(frame.get("question_type", "")).upper()
    if question_type not in crux_engine.QUESTION_TYPES:
        issues.append("invalid_question_type")

    premises = frame.get("premise_audit")
    if not isinstance(premises, list) or not premises:
        issues.append("premise_audit_required")
        premises = []
    premise_by_id = {}
    for index, premise in enumerate(premises):
        prefix = f"premise_{index + 1}"
        if not isinstance(premise, dict):
            issues.append(f"{prefix}_must_be_object")
            continue
        pid = str(premise.get("id", "")).strip()
        if not pid:
            issues.append(f"{prefix}_missing_id")
        elif pid in premise_by_id:
            issues.append(f"duplicate_premise_id_{pid}")
        else:
            premise_by_id[pid] = premise
        if not _present(premise.get("claim")):
            issues.append(f"{prefix}_missing_claim")
        status = str(premise.get("status", "")).upper()
        if status not in {"HYPOTHESIS", "URL_CLAIMED_UNVERIFIED"}:
            issues.append(f"{prefix}_invalid_status")
        elif status == "URL_CLAIMED_UNVERIFIED":
            if not crux_engine.is_concrete_url(premise.get("source_url")):
                issues.append(f"{prefix}_url_claim_requires_concrete_url")
            if str(premise.get("as_of", "")).strip().upper() in {"", "UNKNOWN"}:
                issues.append(f"{prefix}_url_claim_requires_as_of")
            if not _present(premise.get("required_primary_source")):
                issues.append(f"{prefix}_url_claim_requires_source_plan")
        else:
            if premise.get("source_url") not in (None, ""):
                issues.append(f"{prefix}_hypothesis_must_not_claim_source")
            if not _present(premise.get("required_primary_source")):
                issues.append(f"{prefix}_hypothesis_requires_source_plan")

    pre = frame.get("no_edge_precheck")
    if not isinstance(pre, dict):
        issues.append("no_edge_precheck_required")
        pre = {}
    if not isinstance(pre.get("is_researchable"), bool):
        issues.append("no_edge_precheck_requires_boolean")
    if not _present(pre.get("reason")):
        issues.append("no_edge_precheck_requires_reason")
    basis_type = str(pre.get("basis_type", "")).upper()
    if basis_type != "TESTABILITY":
        issues.append("no_edge_precheck_invalid_basis_type")
    basis_ids = pre.get("basis_claim_ids")
    if not isinstance(basis_ids, list) or not basis_ids:
        issues.append("no_edge_precheck_requires_basis_claim_ids")
        basis_ids = []
    unknown_basis = [pid for pid in basis_ids if pid not in premise_by_id]
    if unknown_basis:
        issues.append("no_edge_precheck_unknown_basis_claim_ids")
    cruxes = frame.get("candidate_cruxes")
    if not isinstance(cruxes, list):
        issues.append("candidate_cruxes_must_be_list")
        cruxes = []
    researchable = pre.get("is_researchable") is True
    if researchable and not 2 <= len(cruxes) <= 5:
        issues.append("researchable_frame_requires_2_to_5_cruxes")
    elif not researchable and len(cruxes) > 5:
        issues.append("candidate_cruxes_max_5")
    crux_ids = set()
    crux_roles = []
    crux_role_by_id = {}
    catalyst_basis_ids = set()
    for index, crux in enumerate(cruxes):
        prefix = f"crux_{index + 1}"
        if not isinstance(crux, dict):
            issues.append(f"{prefix}_must_be_object")
            continue
        cid = str(crux.get("id", "")).strip()
        if not cid:
            issues.append(f"{prefix}_missing_id")
        elif cid in crux_ids:
            issues.append(f"duplicate_crux_id_{cid}")
        crux_ids.add(cid)
        role = str(crux.get("logic_role", "")).upper()
        if role not in crux_engine.CRUX_ROLES:
            issues.append(f"{prefix}_invalid_logic_role")
        else:
            crux_roles.append(role)
            if cid:
                crux_role_by_id[cid] = role
        for field in ("label", "definition", "monitor_anchor", "falsifier"):
            if not _present(crux.get(field)):
                issues.append(f"{prefix}_missing_{field}")
        catalyst = crux.get("catalyst_window")
        if not isinstance(catalyst, dict):
            issues.append(f"{prefix}_catalyst_window_required")
        else:
            if not _present(catalyst.get("event")):
                issues.append(f"{prefix}_catalyst_event_required")
            date_status = str(catalyst.get("date_status", "")).upper()
            if date_status not in {"REVIEW_CHECKPOINT", "DATE_CLAIMED_UNVERIFIED"}:
                issues.append(f"{prefix}_catalyst_invalid_date_status")
            basis_claim_id = str(catalyst.get("basis_claim_id", "")).strip()
            if not basis_claim_id:
                issues.append(f"{prefix}_catalyst_basis_claim_id_required")
            elif basis_claim_id not in premise_by_id:
                issues.append(f"{prefix}_catalyst_unknown_basis_claim_id")
            else:
                catalyst_basis_ids.add(basis_claim_id)
            expected_by = str(catalyst.get("expected_by", "")).strip()
            if not expected_by or expected_by.upper() == "UNKNOWN":
                issues.append(f"{prefix}_catalyst_expected_by_required")
            else:
                try:
                    catalyst_date = date.fromisoformat(expected_by)
                except ValueError:
                    issues.append(f"{prefix}_catalyst_expected_by_requires_iso_date")
                else:
                    if frame_as_of:
                        days = (catalyst_date - frame_as_of).days
                        if days <= 0:
                            issues.append(f"{prefix}_catalyst_must_be_future")
                        if str(frame.get("horizon", "")).upper() == "3-6M" and days > 190:
                            issues.append(f"{prefix}_catalyst_outside_3_to_6m_horizon")
    if researchable and not catalyst_basis_ids.issubset(set(basis_ids)):
        issues.append("no_edge_basis_must_cover_catalysts")
    if researchable and question_type in {"CONJUNCTIVE", "CAUSAL_CHAIN"}:
        if "THESIS_HINGE" not in crux_roles:
            issues.append("question_type_requires_thesis_hinge")
    if researchable and question_type == "DISJUNCTIVE":
        if crux_roles.count("OPPORTUNITY_PATH") < 2:
            issues.append("disjunctive_requires_two_opportunity_paths")
    if researchable and question_type == "COMPARATIVE":
        if crux_roles.count("COMPARISON_AXIS") < 2:
            issues.append("comparative_requires_two_comparison_axes")
    if researchable and question_type == "UNIVERSE_SEARCH":
        if "OPPORTUNITY_PATH" not in crux_roles:
            issues.append("universe_search_requires_opportunity_path")
        if "PRICING" not in crux_roles:
            issues.append("universe_search_requires_pricing_crux")
    issues.extend(_validate_logic_graph(frame.get("logic_graph"), crux_role_by_id))
    issues.extend(hypothesis_engine.validate_frame(frame))
    issues.extend(landscape_engine.validate_frame(frame))
    issues.extend(framing_feasibility.validate_frame(frame))
    return sorted(set(issues))


def _frame_quality_status(frame):
    statuses = {
        str(p.get("status", "")).upper()
        for p in frame.get("premise_audit", []) if isinstance(p, dict)
    }
    return ("PROVISIONAL_URL_CLAIMED" if "URL_CLAIMED_UNVERIFIED" in statuses
            else "PROVISIONAL_UNVERIFIED")


def _legacy_slug(topic):
    codes = re.findall(r"\d{6}", topic or "")
    pre = f"{codes[0]}_" if codes else ""
    words = re.findall(r"[一-龥\w]+", (topic or "").lower())
    cleaned = [w for w in words if w not in {"研究","分析","关于","价格","走势","标的"}] or ["general"]
    return (pre + "_".join(cleaned))[:40].rstrip("_")


def _slug(topic):
    """Readable slug plus a topic hash, preventing truncation collisions."""
    base = _legacy_slug(topic)[:30].rstrip("_") or "general"
    digest = hashlib.sha256((topic or "").encode("utf-8")).hexdigest()[:10]
    return f"{base}-{digest}"


def _state_dir():
    return os.path.join(get_scratch_dir(), "v2-state")

def _path(topic):
    override = os.environ.get("TRADE_NOTHING_STATE_PATH", "").strip()
    if override:
        return os.path.abspath(os.path.expanduser(override))
    return os.path.join(_state_dir(), f"{_slug(topic)}_v2_state.json")


def _load(topic):
    p = _path(topic)
    if os.path.exists(p):
        state = load_json_safe(p, default=None)
        if isinstance(state, dict) and state.get("method_identity"):
            method_identity.validate_method_identity(state["method_identity"])
        if isinstance(state, dict):
            state.setdefault("runtime", {}).setdefault("state_revision", 0)
        return state
    return None

def _save(topic, state):
    expected_revision = state.get("runtime", {}).get("state_revision")
    state.setdefault("runtime", {})["state_path"] = _path(topic)
    if os.environ.get("TRADE_NOTHING_RUN_ID"):
        state["runtime"]["run_id"] = os.environ["TRADE_NOTHING_RUN_ID"]
    if os.environ.get("TRADE_NOTHING_RUN_PURPOSE"):
        requested_purpose = run_registry.normalize_run_purpose(
            os.environ["TRADE_NOTHING_RUN_PURPOSE"]
        )
        frozen_purpose = str(state["runtime"].get("run_purpose") or "").strip().upper()
        if frozen_purpose and frozen_purpose != requested_purpose:
            raise ValueError("run_purpose_drift")
        state["runtime"]["run_purpose"] = requested_purpose
    save_json_revision_cas(
        _path(topic), state, expected_revision=expected_revision
    )


def _active_memory(topic):
    """Load Evolution constraints for v2 without making memory availability fatal."""
    try:
        from deepthink_pipeline import extract_active_memory
        return extract_active_memory(topic, get_evolution_path())[:8000]
    except Exception as exc:
        return f"Active memory unavailable: {type(exc).__name__}"


def _agent_has_evidence(detective, inquisitor):
    """Judge may only score evidence that exists in the isolated agent outputs."""
    det = detective if isinstance(detective, dict) else {}
    inq = inquisitor if isinstance(inquisitor, dict) else {}
    return any([
        bool(det.get("crux_evidence")),
        bool(det.get("evidence_chain")),
        bool(det.get("rebuttals")),
        bool(det.get("supply_chain_map")),
        bool(inq.get("crux_attacks")),
        bool(inq.get("lethal_attack_vectors")),
        bool(inq.get("recommended_kill_switch")),
    ])


def _agent_supported_cruxes(detective, inquisitor):
    """Return crux ids with structured agent evidence, or None for legacy payloads."""
    det = detective if isinstance(detective, dict) else {}
    inq = inquisitor if isinstance(inquisitor, dict) else {}
    structured_present = "crux_evidence" in det or "crux_attacks" in inq
    if not structured_present:
        return None
    supported = set()
    for group in det.get("crux_evidence", []):
        if isinstance(group, dict) and group.get("crux_id") and group.get("evidence"):
            supported.add(group["crux_id"])
    for group in inq.get("crux_attacks", []):
        if isinstance(group, dict) and group.get("crux_id") and group.get("attacks"):
            supported.add(group["crux_id"])
    return supported


def _agent_evidence_by_crux(detective, inquisitor):
    """Map citation identities to original agent evidence; None means legacy payload."""
    det = detective if isinstance(detective, dict) else {}
    inq = inquisitor if isinstance(inquisitor, dict) else {}
    structured_present = "crux_evidence" in det or "crux_attacks" in inq
    if not structured_present:
        return None
    out = {}
    for group in det.get("crux_evidence", []):
        if not isinstance(group, dict) or not group.get("crux_id"):
            continue
        bucket = out.setdefault(group["crux_id"], {})
        for evidence in group.get("evidence", []):
            key = crux_engine.citation_identity(evidence)
            if key:
                bucket[key] = evidence
    for group in inq.get("crux_attacks", []):
        if not isinstance(group, dict) or not group.get("crux_id"):
            continue
        bucket = out.setdefault(group["crux_id"], {})
        for evidence in group.get("attacks", []):
            key = crux_engine.citation_identity(evidence)
            if key:
                bucket[key] = evidence
    return out


def _backfill_seen_agent_evidence_keys(state):
    """Rebuild the role-evidence novelty ledger for resumable legacy states.

    Older states only remembered citations selected by the Judge. If a Judge
    omitted its citation array, the same role evidence looked "new" forever and
    evidence exhaustion could never advance. Raw role payloads already stored in
    each immutable round are sufficient to derive this bookkeeping field.
    """
    by_crux = {cid: set() for cid in state.get("cruxes", {})}
    for record in state.get("rounds") or []:
        if not isinstance(record, dict):
            continue
        evidence = _agent_evidence_by_crux(
            record.get("detective_raw"), record.get("inquisitor_raw")
        ) or {}
        for cid, bucket in evidence.items():
            if cid not in by_crux or not isinstance(bucket, dict):
                continue
            by_crux[cid].update(
                key for key, citation in bucket.items()
                if key and crux_engine.valid_citation(citation)
            )
    added = 0
    for cid, cx in state.get("cruxes", {}).items():
        existing = set(cx.get("seen_agent_evidence_keys") or [])
        existing.update(cx.get("seen_evidence_keys") or [])
        rebuilt = existing | by_crux.get(cid, set())
        added += len(rebuilt - existing)
        cx["seen_agent_evidence_keys"] = sorted(rebuilt)
    return added


def _role_probe_ids(payload, groups_field):
    """Return crux ids explicitly probed by one isolated role."""
    payload = payload if isinstance(payload, dict) else {}
    groups = payload.get(groups_field, [])
    return {
        str(group.get("crux_id", "")).strip()
        for group in groups if isinstance(groups, list) and isinstance(group, dict)
        and str(group.get("crux_id", "")).strip()
    }


def _crux_probe_audit(state, detective, inquisitor, dispatch_cruxes):
    """Build a host-side bilateral-probe receipt for evidence exhaustion.

    Role payload presence establishes that the role probed a crux. Citation
    identities establish novelty. Judge prose and exploration objects are
    intentionally ignored. Only cruxes explicitly dispatched by the host to
    both roles this round are eligible; raw role payloads cannot expand scope.
    """
    allowed = {
        str(crux_id).strip()
        for crux_id in dispatch_cruxes
        if str(crux_id).strip()
    }
    detective_ids = _role_probe_ids(detective, "crux_evidence")
    inquisitor_ids = _role_probe_ids(inquisitor, "crux_attacks")
    evidence_by_crux = _agent_evidence_by_crux(detective, inquisitor) or {}
    audit = {}
    for cid, cx in state.get("cruxes", {}).items():
        if cid not in allowed:
            continue
        if cid not in detective_ids and cid not in inquisitor_ids:
            continue
        seen = set(cx.get("seen_agent_evidence_keys") or [])
        seen.update(cx.get("seen_evidence_keys") or [])
        valid_keys = {
            key for key, citation in evidence_by_crux.get(cid, {}).items()
            if key and crux_engine.valid_citation(citation)
        }
        new_keys = valid_keys - seen
        cx["seen_agent_evidence_keys"] = sorted(seen | valid_keys)
        audit[cid] = {
            "detective_probed": cid in detective_ids,
            "inquisitor_probed": cid in inquisitor_ids,
            "new_valid_evidence_count": len(new_keys),
            "valid_agent_evidence_count": len(valid_keys),
        }
    return audit


def _sanitize_judge_for_agent_support(judge, detective, inquisitor):
    """Prevent a Judge from inventing citations after thin/empty agent rounds."""
    if not isinstance(judge, dict):
        return {}
    out = json.loads(json.dumps(judge, ensure_ascii=False))
    supported = _agent_supported_cruxes(detective, inquisitor)
    evidence_by_crux = _agent_evidence_by_crux(detective, inquisitor)
    if supported is None and _agent_has_evidence(detective, inquisitor):
        return out
    supported = supported or set()
    for cid, sig in out.get("crux_signals", {}).items():
        if not isinstance(sig, dict):
            continue
        flags = sig.get("quality_flags", [])
        if not isinstance(flags, list):
            flags = []
        if evidence_by_crux is not None:
            submitted = sig.get("citations", []) if isinstance(sig.get("citations", []), list) else []
            allowed = evidence_by_crux.get(cid, {})
            accepted, reworded = [], 0
            for candidate in submitted:
                matched = crux_engine.match_agent_citation(allowed, candidate)
                if matched is None:
                    continue
                if crux_engine.citation_identity(candidate) != crux_engine.citation_identity(matched):
                    reworded += 1
                accepted.append(json.loads(json.dumps(matched, ensure_ascii=False)))
            if len(accepted) < len(submitted):
                flags.append(f"dropped_judge_invented_citations:{len(submitted) - len(accepted)}")
            if reworded:
                flags.append(f"judge_citation_rebound_by_source_url:{reworded}")
            sig["citations"] = accepted
        try:
            nonzero = float(sig.get("signal", 0.0)) != 0.0
        except Exception:
            nonzero = False
        if nonzero and cid not in supported:
            sig["signal"] = 0.0
            flags.append("signal_zeroed_missing_agent_evidence_for_crux")
        if nonzero and evidence_by_crux is not None and not sig.get("citations"):
            sig["signal"] = 0.0
            flags.append("signal_zeroed_no_agent_backed_citation")
        if flags:
            sig["quality_flags"] = sorted(set(flags))
    return out


# ── prompt assembly ──────────────────────────────────────────────────────────
def _open_cruxes(state):
    return [cid for cid, cx in state["cruxes"].items() if not cx["retired"]]


def _last_scored_round(state, crux_id):
    for round_record in reversed(state.get("rounds", [])):
        judge = round_record.get("judge_raw") if isinstance(round_record, dict) else {}
        signals = judge.get("crux_signals", {}) if isinstance(judge, dict) else {}
        if crux_id in signals:
            return int(round_record.get("round") or 0)
    return 0


def _dispatch_cruxes(state, open_ids, limit=2):
    """Bound each round while preventing untested or stale crux starvation."""
    try:
        configured = int(state.get("config", {}).get("MAX_CRUXES_PER_ROUND", limit))
    except (TypeError, ValueError):
        configured = limit
    configured = max(1, min(3, configured))
    pending_landscape_cruxes = {
        str(item.get("linked_crux_id") or "")
        for item in state.get("landscape_map", {}).get("paths", [])
        if isinstance(item, dict)
        and item.get("state", "UNPROBED") == "UNPROBED"
        and item.get("linked_crux_id")
    }
    ranked = sorted(
        open_ids,
        key=lambda cid: (
            0 if cid in pending_landscape_cruxes else 1,
            0 if state["cruxes"][cid].get("first_contested") is None else 1,
            _last_scored_round(state, cid),
            abs(float(state["cruxes"][cid].get("p_history", [0.5])[-1]) - 0.5),
            cid,
        ),
    )
    return ranked[:configured]


def _round_policy(state, round_num):
    open_ids = _open_cruxes(state)
    untested = [cid for cid in open_ids if state["cruxes"][cid].get("first_contested") is None]
    dispatch_ids = _dispatch_cruxes(state, open_ids)
    try:
        max_rounds = int(state.get("config", {}).get("MAX_ROUNDS", crux_engine.MAX_ROUNDS))
    except (TypeError, ValueError):
        max_rounds = crux_engine.MAX_ROUNDS
    new_crux_cutoff = max(0, max_rounds - crux_engine.DRY_ROUNDS)
    return {
        "open_cruxes": open_ids,
        "dispatch_cruxes": dispatch_ids,
        "deferred_open_cruxes": [cid for cid in open_ids if cid not in dispatch_ids],
        "untested_cruxes": untested,
        "free_roam_allowed": not untested and round_num < max_rounds,
        "new_cruxes_allowed": round_num <= new_crux_cutoff,
        "new_crux_cutoff_round": new_crux_cutoff,
        "configured_max_rounds": max_rounds,
    }


def _new_crux_issues(state, crux):
    if not isinstance(crux, dict):
        return ["new_crux_must_be_object"]
    issues = []
    for field in ("id", "label", "definition", "monitor_anchor", "falsifier"):
        if not _present(crux.get(field)):
            issues.append(f"new_crux_missing_{field}")
    if str(crux.get("logic_role", "")).upper() not in crux_engine.CRUX_ROLES:
        issues.append("new_crux_invalid_logic_role")
    catalyst = crux.get("catalyst_window")
    if not isinstance(catalyst, dict):
        issues.append("new_crux_missing_catalyst_window")
        return issues
    for field in ("event", "expected_by", "date_status", "basis_claim_id"):
        if not _present(catalyst.get(field)):
            issues.append(f"new_crux_catalyst_missing_{field}")
    status = str(catalyst.get("date_status", "")).upper()
    if status not in {"REVIEW_CHECKPOINT", "DATE_CLAIMED_UNVERIFIED"}:
        issues.append("new_crux_catalyst_invalid_date_status")
    premise_ids = {
        str(item.get("id", "")).strip()
        for item in state.get("frame_contract", {}).get("premise_audit", [])
        if isinstance(item, dict)
    }
    if str(catalyst.get("basis_claim_id", "")).strip() not in premise_ids:
        issues.append("new_crux_catalyst_unknown_basis_claim_id")
    try:
        expected = date.fromisoformat(str(catalyst.get("expected_by", "")))
        as_of = date.fromisoformat(str(state.get("frame_contract", {}).get("as_of_date", "")))
    except ValueError:
        issues.append("new_crux_catalyst_requires_iso_dates")
    else:
        days = (expected - as_of).days
        if days <= 0:
            issues.append("new_crux_catalyst_must_be_future")
        if str(state.get("horizon", "")).upper() == "3-6M" and days > 190:
            issues.append("new_crux_catalyst_outside_root_horizon")
    return sorted(set(issues))


def _admit_new_cruxes(state, proposed, round_num, policy, inquisitor=None):
    admitted, deferred = [], []
    proposed = proposed if isinstance(proposed, list) else []
    inquisitor_evidence = _agent_evidence_by_crux({}, inquisitor) or {}
    for item in proposed:
        issues = _new_crux_issues(state, item)
        if not policy["new_cruxes_allowed"]:
            issues.append("new_crux_introduced_after_cutoff")
        cid = str(item.get("id", "")).strip() if isinstance(item, dict) else ""
        if cid in state.get("cruxes", {}):
            issues.append("new_crux_id_already_exists")
        source_crux_id = (
            str(item.get("source_attack_crux_id", "")).strip()
            if isinstance(item, dict) else ""
        )
        supporting_citation = (
            item.get("supporting_citation")
            if isinstance(item, dict) else None
        )
        if not source_crux_id:
            issues.append("new_crux_missing_source_attack_crux_id")
        elif source_crux_id not in set(policy.get("dispatch_cruxes", [])):
            issues.append("new_crux_source_attack_outside_round_scope")
        elif source_crux_id not in inquisitor_evidence:
            issues.append("new_crux_source_attack_not_in_inquisitor_round")
        if not isinstance(supporting_citation, dict):
            issues.append("new_crux_missing_supporting_citation")
        else:
            citation_key = crux_engine.citation_identity(supporting_citation)
            matched = inquisitor_evidence.get(source_crux_id, {}).get(citation_key)
            if (
                not matched
                or not _present(matched.get("attack"))
                or not crux_engine.valid_citation(matched)
            ):
                issues.append("new_crux_citation_not_backed_by_admissible_attack")
        if issues:
            deferred_item = {
                "round": round_num,
                "id": cid or None,
                "label": item.get("label") if isinstance(item, dict) else None,
                "reason_codes": sorted(set(issues)),
            }
            state.setdefault("deferred_cruxes", []).append(deferred_item)
            deferred.append(deferred_item)
            continue
        crux_engine.add_crux(state, item, round_num)
        matched_citation = json.loads(json.dumps(
            inquisitor_evidence[source_crux_id][
                crux_engine.citation_identity(supporting_citation)
            ],
            ensure_ascii=False,
        ))
        state["cruxes"][cid]["citations"] = [matched_citation]
        state["cruxes"][cid]["seen_evidence_keys"] = [
            crux_engine.citation_identity(matched_citation)
        ]
        state["cruxes"][cid]["admission_receipt"] = {
            "round": int(round_num),
            "source_attack_crux_id": source_crux_id,
            "supporting_citation_identity": crux_engine.citation_identity(
                matched_citation
            ),
        }
        graph = state.setdefault("logic_graph", {})
        root_id = str(graph.get("root_id", "Q1"))
        graph.setdefault("nodes", []).append({
            "id": cid, "node_type": "CRUX", "label": item.get("label", cid),
        })
        relation = {
            "PRICING": "PRICING_FOR",
            "OPPORTUNITY_PATH": "ALTERNATIVE_PATH",
            "COMPARISON_AXIS": "COMPARED_ON",
            "THESIS_HINGE": "REQUIRED_FOR",
        }[str(item.get("logic_role")).upper()]
        graph.setdefault("edges", []).append({"from": cid, "to": root_id, "relation": relation})
        admitted.append(cid)
    return admitted, deferred


def _enforce_round_scope(judge, state, policy, admitted_ids):
    allowed = set(policy.get("dispatch_cruxes", policy["open_cruxes"])) | set(admitted_ids)
    reopen_candidates = []
    if policy["free_roam_allowed"]:
        for cid, signal in judge.get("crux_signals", {}).items():
            if cid in allowed or cid not in state.get("cruxes", {}):
                continue
            try:
                value = float(signal.get("signal", 0.0)) if isinstance(signal, dict) else 0.0
            except (TypeError, ValueError):
                value = 0.0
            if state["cruxes"][cid].get("retired") and value <= -0.5:
                reopen_candidates.append(cid)
        if reopen_candidates:
            allowed.add(sorted(reopen_candidates)[0])
    for cid, signal in judge.get("crux_signals", {}).items():
        if cid in allowed or not isinstance(signal, dict):
            continue
        try:
            nonzero = float(signal.get("signal", 0.0)) != 0.0
        except (TypeError, ValueError):
            nonzero = False
        if nonzero:
            signal["signal"] = 0.0
            flags = signal.get("quality_flags", []) if isinstance(signal.get("quality_flags"), list) else []
            flags.append("signal_zeroed_outside_round_scope")
            signal["quality_flags"] = sorted(set(flags))
    return sorted(allowed)

def frame_prompt(topic, start_context=None, briefing_context=None):
    prompt = ("[HOST EXECUTION CONTRACT — MANDATORY]\n"
            "Execute the Framer inline in the current parent context. Do not call "
            "define_subagent, invoke_subagent, Task, delegate, context-fork, or any equivalent "
            "sub-agent mechanism. Do not browse or call tools during framing.\n"
            f"[Framer · framer.md] Topic: {topic}\n"
            "立题：输出 decision_question / question_type / logic_graph / horizon / as_of_date / "
            "forecast_target_date / "
            "research_intent / unit_of_analysis / thesis_seed / premise_audit / "
            "2–5 candidate_cruxes(每条带 "
            "logic_role、monitor_anchor、falsifier、evidence_plan、catalyst_window) / "
            "forbidden_consensus / no_edge_precheck / suggested_max_rounds。"
            "OPPORTUNITY_DISCOVERY 或 HYBRID 还必须输出 5–7 路 entity-agnostic "
            "hypothesis_garden；THESIS_CHALLENGE 可省略。严格按 framer.md 的 JSON 输出。"
            "只返回内联 JSON；禁止创建 Markdown、Google Drive、云文档或自选输出路径。")
    if start_context:
        prompt += (
            "\n[HUMAN-SELECTED LESSON CONSTRAINTS]\n"
            + json.dumps(start_context, ensure_ascii=False, indent=2)
            + "\nThese Lessons are framing constraints, not evidence, prior verdicts, scores, "
              "candidate states, or actionability signals. Translate each into an explicit "
              "premise audit, falsifier, comparison axis, or failure mode. Do not pre-decide "
              "any crux or reuse prior evidence. Copy this exact binding into the Framer JSON "
              "as research_start_binding: "
            + json.dumps({
                "packet_id": start_context["packet_id"],
                "payload_sha256": start_context["payload_sha256"],
            }, ensure_ascii=False)
        )
    if briefing_context:
        prompt += (
            "\n[USER BRIEFING — 背景上下文，不是证据]\n"
            + json.dumps(briefing_context, ensure_ascii=False, indent=2)
            + "\n使用 briefing 中的信息来定义更精准的 crux、evidence_plan 和"
            "hypothesis_garden。所有 briefing 内容仍必须在 premise_audit 中标记为"
            "HYPOTHESIS。briefing 中的 URL 不能直接当作 SOURCED 引用。"
        )
    return prompt

def _exploration_summary_table(state, max_rows=20):
    """Compress the hypothesis ledger into a compact markdown table for prompts.

    Full JSON dumps of 35+ hypotheses consume ~5,600 tokens per round (45% of the
    Detective prompt).  A summary table with one row per hypothesis cuts this to
    ~700 tokens while keeping enough information for agents to reference existing
    hypotheses when creating sparks and proxy trails.
    """
    ledger = state.get("hypothesis_ledger", {})
    hypotheses = ledger.get("hypotheses", []) if isinstance(ledger, dict) else []
    if not isinstance(hypotheses, list) or not hypotheses:
        return "（尚无探索假说）"
    rows = []
    for item in hypotheses[:max_rows]:
        if not isinstance(item, dict):
            continue
        hid = item.get("hypothesis_id", "?")
        hypothesis_text = _compact_text(item.get("hypothesis", ""), limit=40)
        state_label = item.get("state", "HYPOTHESIS_ONLY")
        priority = (item.get("exploration_priority") or {}).get("band", "—")
        proxy_count = len([
            t for t in item.get("proxy_trails", [])
            if isinstance(t, dict)
        ])
        rows.append(
            f"| `{hid}` | {hypothesis_text} | `{state_label}` | {priority} | "
            f"{proxy_count} 条 |"
        )
    header = (
        "| 假说ID | 猜想 (≤40字) | 状态 | 优先级 | ProxyTrail |\n"
        "|--------|-------------|------|--------|------------|\n"
    )
    trailer = ""
    if len(hypotheses) > max_rows:
        trailer = f"\n（另有 {len(hypotheses) - max_rows} 条假说，见 state.json → hypothesis_ledger）"
    return header + "\n".join(rows) + trailer


def _crux_scope_compact(state, open_ids):
    """Compact crux scope display: key facts only, no full evidence_plan JSON."""
    lines = []
    for cid in open_ids:
        cx = state["cruxes"][cid]
        catalyst = cx.get("catalyst_window", {})
        catalyst_text = ""
        if isinstance(catalyst, dict) and catalyst.get("event"):
            catalyst_text = (
                f"{catalyst.get('event', '—')} @ {catalyst.get('expected_by', '—')} "
                f"[{catalyst.get('date_status', 'REVIEW_CHECKPOINT')}]"
            )
        # Summarise pending evidence routes instead of dumping full JSON.
        plan = cx.get("evidence_plan", [])
        if isinstance(plan, list) and plan:
            pending_routes = [
                r.get("publisher_class", "?") for r in plan
                if isinstance(r, dict)
            ]
            route_text = "、".join(pending_routes[:3]) if pending_routes else "—"
        else:
            route_text = "—"
        lines.append(
            f"- **[{cid}] {cx['label']}** ({cx.get('logic_role', 'THESIS_HINGE')})\n"
            f"  对方最强(bear): {cx.get('best_bear') or '（暂无）'}\n"
            f"  我方最强(bull): {cx.get('best_bull') or '（暂无）'}\n"
            f"  监控: {cx.get('monitor_anchor', '')}\n"
            f"  反证: {cx.get('falsifier', '')}\n"
            f"  催化: {catalyst_text}\n"
            f"  待查路线: {route_text}"
        )
    return "\n".join(lines)


def dispatch_prompts(state, round_num):
    """Generate round-scoped dispatch prompts with static directives moved to agent.md.

    v0.13 change: budget rules, chain-check rules, opportunity harvest rules,
    exploration rules, landscape rules, and evidence-format constraints now live
    permanently in detective.md / inquisitor.md.  The round prompt carries only
    dynamic state: which cruxes to probe, what's been established, the current
    exploration summary, and this round's scheduling contract.
    """
    policy = _round_policy(state, round_num)
    open_ids = policy["dispatch_cruxes"]
    landscape_plan = landscape_engine.ensure_round_plan(
        state, round_num, dispatch_cruxes=open_ids
    )
    fc = state.get("forbidden_consensus", [])
    scope = _crux_scope_compact(state, open_ids)
    resolved = [
        f"{cid}({state['cruxes'][cid]['label']})"
        for cid, cx in state["cruxes"].items()
        if cx["retired"] and cx["status"].startswith("RESOLVED")
    ]
    # Retired crux context (for supply-chain cross-reference only).
    retired_ctx = ""
    retired_cruxes = [
        (cid, cx) for cid, cx in state["cruxes"].items() if cx["retired"]
    ]
    if retired_cruxes:
        rc_lines = [
            f"  - {cid}({cx['label']}): {cx['status']}, "
            f"support={int(cx['p_history'][-1]*100)}/100, "
            f"bull={cx.get('best_bull') or '?'}, bear={cx.get('best_bear') or '?'}"
            for cid, cx in retired_cruxes
        ]
        retired_ctx = (
            "\n📋 已收敛 crux 上下文（不需重辩，供产业链交叉引用）:\n"
            + "\n".join(rc_lines)
        )
    # Exploration summary table (compact, not full JSON).
    exploration_table = _exploration_summary_table(state)
    exploration_directive = (
        "\n✨ 假说探索轨（现有假说摘要，引用时使用 hypothesis_id）:\n"
        f"{exploration_table}\n"
        "规则见 detective.md / inquisitor.md §探索轨。"
    )
    # Landscape assignments.
    landscape_by_id = {
        item.get("path_id"): item
        for item in state.get("landscape_map", {}).get("paths", [])
        if isinstance(item, dict)
    }

    def landscape_directive(role):
        assigned = landscape_plan.get("assignments", {}).get(role, [])
        if not assigned:
            return "\n🗺 Landscape: 本轮无路径分配；输出 landscape_findings=[]。"
        packets = [
            landscape_by_id[pid] for pid in assigned if pid in landscape_by_id
        ]
        return (
            "\n🗺 Landscape 路径质证（硬分配）:\n"
            f"{json.dumps(packets, ensure_ascii=False)}\n"
            "规则见 detective.md / inquisitor.md §Landscape。"
        )
    # Scheduling contract (the only per-round policy that changes).
    scope_directive = (
        f"\n🎯 本轮调度: free_roam={str(policy['free_roam_allowed']).lower()}, "
        f"new_cruxes={str(policy['new_cruxes_allowed']).lower()}, "
        f"cutoff_round={policy['new_crux_cutoff_round']}。\n"
        f"本轮处理: {policy['dispatch_cruxes']}；延后: "
        f"{policy['deferred_open_cruxes']}。\n"
        "未检验 crux 永远优先。"
    )
    # ── Assemble the common dynamic section ──
    common = (
        f"决策问题: {state['decision_question']} | 视野: {state['horizon']} | "
        f"as-of: {state.get('frame_contract', {}).get('as_of_date', '—')}\n"
        f"分析单元: {state.get('frame_contract', {}).get('unit_of_analysis', '—')} | "
        f"立题状态: {state.get('frame_contract', {}).get('quality_status', 'UNVERIFIED')}\n"
        "立题前提（HYPOTHESIS 非事实）:\n"
        f"{json.dumps(state.get('frame_contract', {}).get('premise_audit', []), ensure_ascii=False)}\n"
        f"本轮重点质证以下 OPEN crux:\n{scope}\n"
        f"{retired_ctx}\n"
        f"历史负面先验（必须显式检查）:\n"
        f"{_compact_text(state.get('negative_priors','（无）'))}\n"
        f"平庸共识禁区: {fc}\n"
        f"{exploration_directive}\n"
        f"{scope_directive}"
    )
    # ── Role-specific prompts ──
    det = (
        f"[Detective · detective.md · model={model_for('detective')}] Round {round_num}\n"
        f"{common}\n"
        f"{landscape_directive('detective')}\n"
        "任务: 对每个 OPEN crux 用带URL的硬数据加固多头/反驳空头。\n"
        "输出 detective.md 的 JSON（含 supply_chain_map）。"
    )
    free_roam_text = (
        f"⭐ FREE-ROAM(最多1个): 可攻击已收敛 crux: {resolved or '（暂无）'}。"
        if policy["free_roam_allowed"]
        else "⛔ FREE-ROAM 禁用（存在未检验 crux 或临近轮次上限）。"
    )
    new_crux_text = (
        "发现全新攻击面时，按 inquisitor.md 完整 schema 提出 new_crux。"
        if policy["new_cruxes_allowed"]
        else "本轮禁止新增 crux；潜在线索留在叙事中，不得阻塞当前 run。"
    )
    inq = (
        f"[Inquisitor · inquisitor.md · model={model_for('inquisitor')}] Round {round_num}\n"
        f"{common}\n"
        f"{landscape_directive('inquisitor')}\n"
        f"任务: 对每个 OPEN crux 发起带数据的致命攻击。{new_crux_text}\n"
        f"{free_roam_text}\n"
        "输出 inquisitor.md 的 JSON（含 scenario_paths 和 odds_calibration）。"
    )
    judge = (
        f"[Judge · judge.md · model={model_for('judge_scoring')}] Round {round_num}\n"
        f"读 Detective/Inquisitor 两份 JSON，对 OPEN crux {open_ids} 各打一个 "
        f"signal∈[-1,1]+引用，free-roam={policy['free_roam_allowed']}，"
        f"new_cruxes={policy['new_cruxes_allowed']}。"
        "完全忽略 hypothesis_sparks、proxy_trails 与所有 HYPOTHESIS_ONLY 内容；"
        "它们不得进入 signal、citations 或 new_cruxes。"
        "严格按 judge.md 的 JSON 输出。"
    )
    return {
        "open_cruxes": policy["open_cruxes"],
        "dispatch_cruxes": open_ids,
        "round_policy": policy,
        "landscape_assignments": landscape_plan.get("assignments", {}),
        "detective_prompt": det,
        "inquisitor_prompt": inq,
        "judge_prompt": judge,
    }


def candidate_screen_prompts(state, seeds, as_of_date):
    selection = candidate_screen_engine.selection_audit(seeds)
    latest = candidate_screen_engine.latest_by_seed(state)
    rescreen_context = []
    for seed in seeds:
        previous = latest.get(seed.get("seed_id"))
        if not previous:
            continue
        gaps = previous.get("gaps", []) if isinstance(previous.get("gaps"), list) else []
        first_core_gap = next(
            (dimension for dimension in candidate_screen_engine.CORE_DIMENSIONS if dimension in gaps),
            "",
        )
        rescreen_context.append({
            "seed_id": seed.get("seed_id"),
            "previous_screen_id": previous.get("screen_id"),
            "previous_as_of_date": previous.get("as_of_date"),
            "previous_status": previous.get("status"),
            "first_core_gap": first_core_gap,
            "gap_codes": gaps,
        })
    packet = [{
        "seed_id": seed.get("seed_id"),
        "candidate": seed.get("candidate"),
        "ticker": seed.get("ticker"),
        "asset_type": seed.get("asset_type"),
        "relation_type": seed.get("relation_type"),
        "origin_crux": seed.get("origin_crux"),
        "causal_path": seed.get("causal_path"),
        "economic_exposure": seed.get("economic_exposure"),
        "why_market_may_miss": seed.get("why_market_may_miss"),
        "pricing_anchor": seed.get("pricing_anchor", {}),
        "catalyst": seed.get("catalyst"),
        "catalyst_window": seed.get("catalyst_window", {}),
        "falsifier": seed.get("falsifier"),
        "evidence": seed.get("evidence", []),
    } for seed in seeds]
    common = (
        f"as_of_date: {as_of_date}\n"
        f"research_horizon: {state.get('horizon', '3-6M')}\n"
        "前次筛选缺口（仅是工作流路由，不是证据，不得引用或继承答案）:\n"
        + json.dumps(rescreen_context, ensure_ascii=False, indent=2) + "\n"
        "候选包:\n" + json.dumps(packet, ensure_ascii=False, indent=2) + "\n"
        "固定问题:\n" + json.dumps(candidate_screen_engine.QUESTIONS, ensure_ascii=False, indent=2) + "\n"
        "cheap-first 顺序: 先查 ECONOMIC_EXPOSURE / EXPECTATION_GAP / TRADABILITY / CATALYST。"
        "任一核心维度为 NO 或 UNKNOWN 时，停止该候选的扩展检索，并把其余维度填 UNKNOWN、"
        "evidence=[]；只有四个核心维度全部 YES 才继续查估值、治理、拥挤度和证伪。\n"
        "硬约束: 最终仍回答全部八个维度；YES/NO 必须有新鲜、具体 URL 证据；"
        "无证据写 UNKNOWN；禁止目标价、收益率、概率、排名和仓位。"
    )
    analyst = (
        f"[Candidate Analyst · candidate_analyst.md · model={model_for('candidate_analyst')}]\n"
        f"{common}\n任务: 独立验证机会是否具备经济兑现、预期差与可研究表达。"
        "严格按 candidate-screen-protocol.md 输出 JSON。"
    )
    skeptic = (
        f"[Candidate Skeptic · candidate_skeptic.md · model={model_for('candidate_skeptic')}]\n"
        f"{common}\n任务: 独立寻找经济暴露、定价、治理、流动性、拥挤度和催化的失败点。"
        "严格按 candidate-screen-protocol.md 输出 JSON。"
    )
    return {"candidate_seed_ids": [s.get("seed_id") for s in seeds],
            "screen_mode": "RESCREEN" if rescreen_context else "INITIAL",
            "rescreen_context": rescreen_context,
            "selection_audit": selection,
            "analyst_prompt": analyst, "skeptic_prompt": skeptic}


# ── commands ─────────────────────────────────────────────────────────────────
def _research_start_context(topic, packet, frame=None):
    if not packet:
        return None
    context = research_start_packet.framing_context(packet)
    question = context["question"]
    if topic and topic != question["topic"]:
        raise research_start_packet.PacketValidationError(
            "CLI topic must exactly match research-start question.topic"
        )
    if frame is not None:
        expected_binding = {
            "packet_id": context["packet_id"],
            "payload_sha256": context["payload_sha256"],
        }
        if frame.get("research_start_binding") != expected_binding:
            raise research_start_packet.PacketValidationError(
                "framer research_start_binding must match the supplied packet"
            )
        bindings = {
            "decision_question": frame.get("decision_question"),
            "question_type": frame.get("question_type"),
            "horizon": frame.get("horizon"),
            "as_of_date": frame.get("as_of_date"),
            "forecast_target_date": str(
                frame.get("forecast_target_date") or ""
            ),
        }
        for key, actual in bindings.items():
            expected = (
                str(question.get(key) or "")
                if key == "forecast_target_date"
                else question.get(key)
            )
            if actual != expected:
                raise research_start_packet.PacketValidationError(
                    f"framer {key} must exactly match research-start question.{key}"
                )
    return context


def _resolve_briefing(briefing_input):
    """Resolve the optional user briefing into framing context.

    Returns None when empty; {"type": "url", "content": ...} when the input
    looks like an http(s) URL (the parent context fetches the page); otherwise
    {"type": "text", "content": ...} truncated to 2000 chars.
    """
    stripped = (briefing_input or "").strip()
    if not stripped:
        return None
    if stripped.startswith(("http://", "https://")):
        return {"type": "url", "content": briefing_input}
    return {"type": "text", "content": briefing_input[:2000]}


def cmd_frame(topic, start_packet=None, briefing=""):
    try:
        start_context = _research_start_context(topic, start_packet)
    except research_start_packet.PacketValidationError as exc:
        return {"status": "start_packet_rejected", "topic": topic, "reason": str(exc)}
    if start_context and not topic:
        topic = start_context["question"]["topic"]
    briefing_context = _resolve_briefing(briefing)
    return {"status": "need_framing", "topic": topic, "model": model_for("crux_extraction"),
            "execution_contract": {
                "dispatch_mode": "INLINE_PARENT",
                "subagent_dispatch_allowed": False,
                "tool_calls_allowed": False,
                "isolation_required": False,
                "stage_timeout_seconds": 120,
                "on_timeout": "call --runtime-failure --stage framing --reason '<brief reason>'",
            },
            "framer_prompt": frame_prompt(topic, start_context, briefing_context),
            "research_start_context": start_context,
            "artifact_policy": _frame_artifact_policy(),
            "instruction": (
                "在父上下文内联执行 framer；严禁派生 Framer 子代理或调用搜索工具。"
                "完成后调用 --init --frame-json '<framer输出>'。若 120 秒内未完成，"
                "调用 --runtime-failure 收口，禁止无界等待或自动重试。"
            )}


def cmd_runtime_failure(topic, stage, reason):
    """Return a bounded, non-formal failure artifact without inventing research state."""
    state = _load(topic) if topic else None
    return {
        "status": "blocked_runtime_failure",
        "topic": topic,
        "stage": stage or "unknown",
        "formal_report_allowed": False,
        "state_initialized": bool(state),
        "runtime_failure_memo_markdown": research_output.render_runtime_failure_memo(
            topic, stage, reason, state_initialized=bool(state)
        ),
        "instruction": (
            "保存 runtime_failure_memo_markdown（如用户要求产物）；禁止伪造缺失代理输出、"
            "生成正式报告或自动重试。修复运行时后由用户显式授权重跑。"
        ),
    }

def cmd_init(topic, frame, runtime_isolation="unverified", start_packet=None):
    if not start_packet and isinstance(frame, dict) and frame.get("research_start_binding"):
        return {
            "status": "start_packet_rejected",
            "topic": topic,
            "reason": "framer declared research_start_binding but --start-packet was omitted",
        }
    try:
        start_context = _research_start_context(topic, start_packet, frame)
    except research_start_packet.PacketValidationError as exc:
        return {"status": "start_packet_rejected", "topic": topic, "reason": str(exc)}
    if start_context and not topic:
        topic = start_context["question"]["topic"]
    issues = _validate_frame(frame)
    if issues:
        rejected = {
            "status": "frame_rejected",
            "topic": topic,
            "issues": issues,
            "artifact_policy": _frame_artifact_policy(),
            "instruction": "修正 framer JSON 后重新调用 --init；禁止绕过立题质量闸。",
        }
        round_issue = any("requires_at_least_" in str(issue) for issue in issues)
        if round_issue and isinstance(frame, dict):
            path_count = len(landscape_engine.frame_paths(frame))
            minimum = max(
                framing_feasibility.minimum_rounds(frame),
                crux_engine.recommended_max_rounds(path_count) if path_count else 0,
            )
            rejected["frame_repair"] = {
                "field": "suggested_max_rounds",
                "submitted": frame.get("suggested_max_rounds"),
                "minimum_required": minimum,
                "automatic_repair_applied": False,
                "reason": "ROUND_FUSE_IS_A_FROZEN_FRAMER_CHOICE",
            }
            rejected["instruction"] = (
                f"将 suggested_max_rounds 明确改为至少 {minimum}，或缩小 crux/Landscape；"
                "然后重新调用 --init。引擎不会静默扩展研究预算。"
            )
        return rejected
    pre = frame.get("no_edge_precheck", {})
    if pre and pre.get("is_researchable") is False:
        return {"status": "no_edge", "topic": topic, "reason": pre.get("reason", ""),
                "research_start_context": start_context,
                "frame_quality_status": _frame_quality_status(frame),
                "instruction": "立题门判定无非对称角度。输出 No-Edge 声明，不派任何子智能体。"}
    cruxes = frame.get("candidate_cruxes", [])
    if not cruxes:
        return {"status": "error", "reason": "framer 未给出 candidate_cruxes。"}
    state = crux_engine.new_state(
        topic, frame.get("decision_question", topic), frame.get("horizon", "3-6M"), cruxes,
        question_type=frame.get("question_type"), logic_graph=frame.get("logic_graph"),
    )
    state["forbidden_consensus"] = frame.get("forbidden_consensus", [])
    state["thesis_seed"] = frame.get("thesis_seed", "")
    state["frame_contract"] = {
        "quality_status": _frame_quality_status(frame),
        "question_type": frame.get("question_type"),
        "research_intent": hypothesis_engine.infer_research_intent(frame),
        "logic_graph": frame.get("logic_graph"),
        "as_of_date": frame.get("as_of_date", ""),
        "forecast_target_date": str(
            frame.get("forecast_target_date") or ""
        ),
        "unit_of_analysis": frame.get("unit_of_analysis", ""),
        "premise_audit": frame.get("premise_audit", []),
        "no_edge_precheck": pre,
        "artifact_policy": _frame_artifact_policy(),
    }
    if start_context:
        state["research_start_context"] = start_context
    hypothesis_ledger = hypothesis_engine.initialize(frame)
    if hypothesis_ledger is not None:
        state["hypothesis_ledger"] = hypothesis_ledger
    landscape = landscape_engine.initialize(frame)
    if landscape is not None:
        state["landscape_map"] = landscape
    _bind_hypotheses_to_landscape(state)
    try:
        max_rounds = int(frame.get("suggested_max_rounds", 6))
    except (TypeError, ValueError):
        max_rounds = 6
    max_rounds = max(crux_engine.MIN_ROUNDS, min(crux_engine.MAX_ROUNDS, max_rounds))
    state["suggested_max_rounds"] = max_rounds
    state["config"]["MAX_ROUNDS"] = max_rounds
    state["negative_priors"] = _active_memory(topic)
    runtime_isolation = str(runtime_isolation or "unverified").lower()
    if runtime_isolation not in {"verified", "degraded", "unverified"}:
        runtime_isolation = "unverified"
    state["runtime_contract"] = {
        "host_enforced_isolation_required": True,
        "isolation_status": runtime_isolation,
        "frame_isolation_claim_ignored": frame.get("isolation_status"),
        "single_model_fallback": "degraded",
        "artifact_policy": _frame_artifact_policy(),
    }
    state["method_identity"] = method_identity.build_method_identity()
    out = {
        "status": "dispatch_subagents",
        "topic": topic,
        "round": 1,
        "thesis_seed": state["thesis_seed"],
        "hypothesis_exploration": hypothesis_engine.summary(state),
        "exploration_action": hypothesis_engine.exploration_action(state),
    }
    out.update(dispatch_prompts(state, 1))
    _save(topic, state)
    return out

def cmd_submit(topic, detective, inquisitor, judge):
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在，请先 --init。"}
    historical_agent_evidence_backfilled = _backfill_seen_agent_evidence_keys(state)
    try:
        configured_max = int(state.get("config", {}).get("MAX_ROUNDS", crux_engine.MAX_ROUNDS))
    except (TypeError, ValueError):
        configured_max = crux_engine.MAX_ROUNDS
    if (state.get("last_convergence", {}).get("decision") == "fuse_break"
            and len(state.get("rounds", [])) >= configured_max):
        return {
            "status": "resume_requires_explicit_extension",
            "topic": topic,
            "formal_report_allowed": False,
            "instruction": "run 已熔断；先获得用户授权，再调用 --resume-blocked --extra-rounds N。",
        }
    round_num = len(state["rounds"]) + 1
    judge = _sanitize_judge_for_agent_support(judge, detective, inquisitor)
    policy = _round_policy(state, round_num)
    admitted_new_cruxes, deferred_new_cruxes = _admit_new_cruxes(
        state, judge.get("new_cruxes", []), round_num, policy, inquisitor
    )
    allowed_scored_cruxes = _enforce_round_scope(
        judge, state, policy, admitted_new_cruxes
    )
    judge["new_crux_admission"] = {
        "admitted_ids": admitted_new_cruxes,
        "deferred": deferred_new_cruxes,
        "allowed_scored_cruxes": allowed_scored_cruxes,
        "round_policy": policy,
    }
    landscape_audit = landscape_engine.ingest_round(
        state, round_num, detective=detective, inquisitor=inquisitor
    )
    hypothesis_audit = hypothesis_engine.ingest_round(
        state,
        round_num,
        detective=detective,
        inquisitor=inquisitor,
        allowed_crux_ids=policy["dispatch_cruxes"],
    )
    scenario_path_audit = hypothesis_engine.ingest_scenario_paths(
        state, round_num, inquisitor
    )
    crux_probe_audit = _crux_probe_audit(
        state,
        detective,
        inquisitor,
        policy["dispatch_cruxes"],
    )
    # Harvest before convergence so a final-round candidate/evidence change cannot be
    # hidden by a premature coverage-complete decision.
    harvest = opportunity_engine.harvest_round(state, round_num, detective, inquisitor)
    # Promote mature EVIDENCE_BACKED hypotheses into draft OpportunitySeeds
    # before convergence so a final-round evidence change is captured.
    hypothesis_escalation = opportunity_engine.escalate_mature_hypotheses(state, round_num)
    signals = judge.get("crux_signals", {})
    conv = crux_engine.submit_round(
        state, round_num, signals,
        round_context={
            "landscape_audit": landscape_audit,
            "opportunity_harvest": harvest,
            "hypothesis_escalation": hypothesis_escalation,
            "crux_probe_audit": crux_probe_audit,
            "hypothesis_audit": hypothesis_audit,
            "scenario_path_audit": scenario_path_audit,
        },
    )
    state["last_convergence"] = conv
    # ── 保存 agent 原始输出到 state，供报告层消费 ──
    state["rounds"][-1]["detective_raw"] = detective
    state["rounds"][-1]["inquisitor_raw"] = inquisitor
    state["rounds"][-1]["judge_raw"] = judge
    state["rounds"][-1]["landscape_audit"] = landscape_audit
    state["rounds"][-1]["hypothesis_audit"] = hypothesis_audit
    state["rounds"][-1]["scenario_path_audit"] = scenario_path_audit
    state["rounds"][-1]["hypothesis_escalation"] = hypothesis_escalation
    state["rounds"][-1]["payload_repair_audit"] = {
        "historical_agent_evidence_keys_backfilled": (
            historical_agent_evidence_backfilled
        ),
        "semantics": "DERIVED_BOOKKEEPING_ONLY_NO_SUPPORT_SCORE_EFFECT",
    }
    # Root convergence can change screening eligibility; refresh only deterministic
    # projections, never the underlying seed evidence.
    opportunity_engine.refresh_candidate_states(state)
    harvest.update(opportunity_engine.summary(state))
    state["rounds"][-1]["opportunity_harvest"] = harvest
    # Tracking sync MUST run after submit_round + refresh_candidate_states so the
    # ledger sees post-convergence candidate states (e.g. seeds that just became
    # READY/WATCHLIST in this round are correctly marked ESCALATED).
    tracking_engine.sync_tracking_ledger(state, round_num, odds_payload=inquisitor)
    _save(topic, state)
    dt = state["decision_trace"][-1]
    binding_crux = (dt["weakest"] if state.get("question_type") in {
        "CONJUNCTIVE", "CAUSAL_CHAIN"
    } else None)
    base = {"topic": topic, "round_completed": round_num,
            "decision": dt["decision"], "binding_crux": binding_crux,
            "focus_crux": dt["weakest"], "aggregation_rule": dt.get("aggregation_rule"),
            "research_verdict": dt.get("research_verdict"),
            "support_weakest": dt.get("support_weakest", dt["p_weakest"]),
            "support_mean": dt.get("support_mean", dt["p_mean"]), "convergence": conv,
            "opportunity_seed_count": harvest["opportunity_seed_count"],
            "ready_for_screening_count": harvest["ready_for_screening_count"],
            "opportunity_harvest": harvest,
            "landscape_coverage": landscape_engine.summary(state),
            "hypothesis_exploration": hypothesis_engine.summary(state),
            "exploration_action": hypothesis_engine.exploration_action(state),
            "scenario_path_audit": scenario_path_audit,
            "crux_probe_audit": crux_probe_audit,
            "payload_repair_audit": state["rounds"][-1]["payload_repair_audit"],
            "round_policy": policy,
            "admitted_new_cruxes": admitted_new_cruxes,
            "deferred_new_cruxes": deferred_new_cruxes}
    if conv["decision"] == "converge":
        opportunity_question = landscape_engine.is_required(state)
        if opportunity_question and not state.get("candidate_screens"):
            dispatch = cmd_screen(
                topic,
                state.get("frame_contract", {}).get("as_of_date", ""),
            )
        else:
            dispatch = {"status": "no_default_candidate_screen"}
        if dispatch.get("status") == "dispatch_candidate_screeners":
            base.update(dispatch)
            base["research_converged"] = True
            base["formal_report_deferred"] = True
            base["instruction"] = (
                "根研究已收敛。机会型任务默认继续双边筛选确定性 Top 3；"
                "隔离运行 Analyst/Skeptic 后调用 --submit-screen。"
                "若用户只要求命题质证，可显式调用 --report --challenge-only。"
            )
        elif opportunity_question and dispatch.get("status") == "no_screenable_candidates":
            gap_dispatch = cmd_plan_candidate_gaps(topic)
            if gap_dispatch.get("status") == "candidate_gap_tasks_planned":
                base.update(gap_dispatch)
                base["research_converged"] = True
                base["formal_report_deferred"] = True
                base["instruction"] = (
                    "根研究已收敛但没有 READY_FOR_SCREENING 候选。"
                    "先执行确定性 CandidateGapTask；不得修改原 seed 或降低来源门。"
                )
            else:
                base["status"] = "ready_for_report"
                base["instruction"] = (
                    f"引擎判定 {conv['decision']}，且没有可调度候选补证任务。"
                    f"调用 --report --topic \"{topic}\"。"
                )
        else:
            base["status"] = "ready_for_report"
            base["instruction"] = f"引擎判定 {conv['decision']}。调用 --report --topic \"{topic}\"。"
    elif conv["decision"] == "fuse_break":
        base["status"] = "blocked_max_rounds"
        base["formal_report_allowed"] = False
        base["open_cruxes"] = [cid for cid, cx in state["cruxes"].items()
                               if cx["status"] in ("PENDING", "OPEN")]
        base["resolution_memo_markdown"] = research_output.render_resolution_memo(state)
        base["continuation_packet"] = research_output.build_continuation_packet(state)
        base["instruction"] = (
            f"达到最大轮次但仍未收敛。FORMAL 等级被阻断，但报告本身不阻断："
            f"调用 --report --topic \"{topic}\" 交付 EXPLORATORY 等级报告，"
            "并保存 resolution_memo_markdown。"
            "只有用户显式授权后，才可按 continuation_packet 调用 --resume-blocked。"
        )
    else:
        base["status"] = "dispatch_subagents"
        base.update(dispatch_prompts(state, round_num + 1))
        _save(topic, state)
        base["instruction"] = (f"继续 (Round {round_num+1})，仅对 OPEN crux 派 Detective+Inquisitor，"
                               "再用 Judge 评分后调用 --submit。")
    # `continue` is not a terminal block. Whenever the loop stops for any reason
    # (budget, user, runtime), a graded report must still be delivered.
    base.setdefault("report_always_available", True)
    base.setdefault(
        "if_you_stop_here",
        f"调用 --report --topic \"{topic}\"，交付带 report_grade 的报告；"
        "不要因为 status 不是 ready_for_report 就不出报告。",
    )
    return base


def _formal_surface_digest(state):
    """Hash every formal/promotion surface excluded from exploration writes."""
    surface = {
        key: state.get(key)
        for key in (
            "topic",
            "decision_question",
            "horizon",
            "question_type",
            "logic_graph",
            "frame_contract",
            "research_start_context",
            "runtime_contract",
            "method_identity",
            "config",
            "suggested_max_rounds",
            "negative_priors",
            "forbidden_consensus",
            "thesis_seed",
            "cruxes",
            "rounds",
            "decision_trace",
            "last_convergence",
            "landscape_map",
            "scenario_path_ledger",
            "opportunity_seeds",
            "candidate_gap_tasks",
            "candidate_evidence_supplements",
            "candidate_gap_resolutions",
            "candidate_screens",
            "source_snapshots",
            "claim_verifications",
        )
    }
    encoded = json.dumps(
        surface, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _exploration_ledger_digest(state):
    encoded = json.dumps(
        state.get("hypothesis_ledger"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _execution_proposal_digest(proposal):
    execution_proposal = {
        key: value
        for key, value in proposal.items()
        if key not in {"design_target_id", "design_state_revision"}
    }
    encoded = json.dumps(
        execution_proposal,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _exploration_action_id(state, proposal, attempt):
    payload = {
        "topic": state.get("topic"),
        "round_count": len(state.get("rounds", [])),
        "formal_state_digest": _formal_surface_digest(state),
        "exploration_ledger_digest": _exploration_ledger_digest(state),
        "proposal_digest": _execution_proposal_digest(proposal),
        "attempt": int(attempt),
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "EA-" + hashlib.sha256(encoded).hexdigest()[:16].upper()


def _exploration_action_record(state, action_id):
    return next(
        (
            item
            for item in state.get("exploration_actions", [])
            if isinstance(item, dict) and item.get("action_id") == action_id
        ),
        None,
    )


def _exploration_transaction_lock(topic):
    return CrossPlatformFileLock(
        _path(topic) + ".exploration-transaction", timeout=15.0
    )


def _bind_exploration_as_of(state, proposal):
    as_of = str(
        state.get("frame_contract", {}).get("as_of_date")
        or state.get("as_of_date")
        or ""
    ).strip()
    try:
        date.fromisoformat(as_of)
    except ValueError:
        raise ValueError("exploration_action_as_of_date_invalid")
    return {**proposal, "as_of_date": as_of}


def cmd_record_exploration_design(topic, design):
    with _exploration_transaction_lock(topic):
        try:
            state = _load(topic)
            if not state:
                return {
                    "status": "error",
                    "reason": "状态不存在，请先完成 --init。",
                }
            open_actions = [
                item
                for item in state.get("exploration_actions", [])
                if isinstance(item, dict)
                and item.get("status") in {
                    "PLANNED_NOT_AUTHORIZED",
                    "AUTHORIZED_NOT_EXECUTED",
                }
            ]
            if open_actions:
                return {
                    "status": "exploration_design_blocked_open_action",
                    "topic": topic,
                    "action_id": open_actions[-1].get("action_id"),
                    "action_status": open_actions[-1].get("status"),
                    "instruction": (
                        "开放 action 冻结了探索账本。未授权计划可先显式取消；"
                        "已授权动作必须先提交有界结果。"
                    ),
                }
            before = _formal_surface_digest(state)
            audit = hypothesis_engine.record_exploration_design(
                state, design
            )
            if _formal_surface_digest(state) != before:
                return {
                    "status": "exploration_integrity_error",
                    "topic": topic,
                    "reason": "exploration_design_touched_formal_surface",
                }
            _save(topic, state)
            return {
                "status": "exploration_design_recorded",
                "topic": topic,
                "design_audit": audit,
                "exploration_action": hypothesis_engine.exploration_action(
                    state
                ),
                "formal_state_unchanged": True,
                "instruction": (
                    "设计已写入探索账本但没有执行查询或授予权限；"
                    "若下一动作可执行，再单独 --plan-exploration。"
                ),
            }
        except ValueError as exc:
            if str(exc) == "state_revision_conflict":
                return {
                    "status": "exploration_state_conflict",
                    "topic": topic,
                    "reason": str(exc),
                    "instruction": "状态已并发更新；设计未覆盖新状态，请重新审阅。",
                }
            return {
                "status": "exploration_design_rejected",
                "topic": topic,
                "reason": str(exc),
            }


def cmd_plan_exploration(topic, design=None):
    with _exploration_transaction_lock(topic):
        try:
            return _cmd_plan_exploration_locked(topic, design)
        except ValueError as exc:
            if str(exc) == "state_revision_conflict":
                return {
                    "status": "exploration_state_conflict",
                    "topic": topic,
                    "reason": str(exc),
                    "instruction": "状态已被并发更新；未覆盖任何内容，请重新计划。",
                }
            raise


def _cmd_plan_exploration_locked(topic, design=None):
    """Freeze one executable exploration proposal without authorizing it."""
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在，请先完成 --init。"}
    if design not in (None, {}):
        return {
            "status": "exploration_design_requires_record_command",
            "topic": topic,
            "instruction": (
                "设计与执行计划必须分离；先调用 "
                "--record-exploration-design --exploration-design JSON。"
            ),
        }
    open_actions = [
        item
        for item in state.get("exploration_actions", [])
        if isinstance(item, dict)
        and item.get("status") in {
            "PLANNED_NOT_AUTHORIZED",
            "AUTHORIZED_NOT_EXECUTED",
        }
    ]
    if open_actions:
        latest = sorted(
            open_actions,
            key=lambda item: (
                int(item.get("sequence") or 0),
                str(item.get("action_id") or ""),
            ),
        )[-1]
        unchanged_unapproved_plan = (
            latest.get("status") == "PLANNED_NOT_AUTHORIZED"
            and latest.get("formal_state_digest_before")
            == _formal_surface_digest(state)
            and latest.get("exploration_ledger_digest_before")
            == _exploration_ledger_digest(state)
        )
        if unchanged_unapproved_plan and len(open_actions) == 1:
            return {
                "topic": topic,
                **latest,
                "status": "exploration_action_already_planned",
                "action_status": latest.get("status"),
                "exploration_action": latest.get("proposal"),
            }
        return {
            "status": "exploration_plan_blocked_open_action",
            "topic": topic,
            "action_id": latest.get("action_id"),
            "action_status": latest.get("status"),
            "open_action_count": len(open_actions),
            "open_action_ids": [
                item.get("action_id") for item in open_actions
            ],
            "instruction": (
                "同一研究状态只允许一个开放探索动作。未授权计划可先显式"
                "取消；已授权动作必须先提交结果并被记录或安全隔离，"
                "不得创建并行授权。"
            ),
        }
    try:
        proposal = _bind_exploration_as_of(
            state,
            hypothesis_engine.exploration_action(
                state, include_host_state=False
            ),
        )
    except ValueError as exc:
        return {
            "status": "exploration_action_needs_design",
            "topic": topic,
            "reason": str(exc),
            "exploration_action": hypothesis_engine.exploration_action(state),
        }
    if not proposal.get("authorization_ready"):
        return {
            "status": "exploration_action_needs_design",
            "topic": topic,
            "exploration_action": proposal,
            "formal_state_digest": _formal_surface_digest(state),
            "instruction": (
                "来源类或有界查询尚未完成，不能授权或执行；"
                "先通过 --record-exploration-design 写入 typed design。"
            ),
        }
    proposal_digest = _execution_proposal_digest(proposal)
    formal_digest = _formal_surface_digest(state)
    ledger_digest = _exploration_ledger_digest(state)
    sequence = len([
        item for item in state.get("exploration_actions", [])
        if isinstance(item, dict)
    ]) + 1
    action_id = _exploration_action_id(state, proposal, sequence)
    existing = _exploration_action_record(state, action_id)
    if existing:
        return {
            "topic": topic,
            **existing,
            "status": "exploration_action_already_planned",
            "action_status": existing.get("status"),
            "exploration_action": existing.get("proposal"),
        }
    record = {
        "action_id": action_id,
        "sequence": sequence,
        "status": "PLANNED_NOT_AUTHORIZED",
        "created_after_round": len(state.get("rounds", [])),
        "proposal": proposal,
        "proposal_digest": proposal_digest,
        "formal_state_digest_before": formal_digest,
        "exploration_ledger_digest_before": ledger_digest,
        "authorization_receipt": None,
        "execution_receipt": None,
        "result_audit": None,
    }
    state.setdefault("exploration_actions", []).append(record)
    _save(topic, state)
    return {
        "topic": topic,
        **record,
        "status": "exploration_action_planned",
        "action_status": record["status"],
        "exploration_action": proposal,
        "instruction": (
            "尚未授权。只有用户明确授权这一 action_id 后，才可调用 "
            "--authorize-exploration。"
        ),
    }


def cmd_cancel_exploration_action(topic, action_id, reason):
    """Cancel only an unexecuted, unauthorized plan with an audit reason."""
    with _exploration_transaction_lock(topic):
        try:
            state = _load(topic)
            if not state:
                return {"status": "error", "reason": "状态不存在。"}
            record = _exploration_action_record(
                state, str(action_id or "").strip()
            )
            if not record:
                return {
                    "status": "exploration_action_not_found",
                    "topic": topic,
                }
            if record.get("status") != "PLANNED_NOT_AUTHORIZED":
                return {
                    "status": "exploration_action_not_cancellable",
                    "topic": topic,
                    "action_id": action_id,
                    "current_status": record.get("status"),
                    "instruction": (
                        "只允许取消尚未授权、尚未执行的计划；"
                        "已授权动作不能由该命令取消。"
                    ),
                }
            reason_text = " ".join(str(reason or "").split())
            if not reason_text:
                return {
                    "status": "exploration_action_cancel_rejected",
                    "topic": topic,
                    "action_id": action_id,
                    "reason": "cancel_reason_required",
                }
            record["status"] = "CANCELLED_NOT_EXECUTED"
            record["cancellation_receipt"] = {
                "action_id": action_id,
                "reason": reason_text,
                "execution_occurred": False,
                "authorization_occurred": False,
            }
            _save(topic, state)
            return {
                "status": "exploration_action_cancelled",
                "topic": topic,
                "action_id": action_id,
                "cancellation_receipt": record["cancellation_receipt"],
                "instruction": (
                    "计划已取消且从未授权/执行；可重新设计探索账本。"
                ),
            }
        except ValueError as exc:
            if str(exc) == "state_revision_conflict":
                return {
                    "status": "exploration_state_conflict",
                    "topic": topic,
                    "action_id": action_id,
                    "reason": str(exc),
                }
            raise


def _mark_exploration_plan_stale(
    topic, state, record, reason, instruction
):
    record["status"] = "STALE_NOT_AUTHORIZED"
    record["stale_receipt"] = {
        "action_id": record.get("action_id"),
        "reason": reason,
        "authorization_occurred": False,
        "execution_occurred": False,
    }
    _save(topic, state)
    return {
        "status": "exploration_action_stale",
        "topic": topic,
        "action_id": record.get("action_id"),
        "reason": reason,
        "stale_receipt": record["stale_receipt"],
        "instruction": instruction,
    }


def cmd_authorize_exploration(topic, action_id, authorization_receipt):
    with _exploration_transaction_lock(topic):
        try:
            return _cmd_authorize_exploration_locked(
                topic, action_id, authorization_receipt
            )
        except ValueError as exc:
            if str(exc) == "state_revision_conflict":
                return {
                    "status": "exploration_action_stale",
                    "topic": topic,
                    "action_id": action_id,
                    "reason": str(exc),
                    "instruction": "状态已被并发更新；未授权执行，请重新计划。",
                }
            raise


def _cmd_authorize_exploration_locked(
    topic, action_id, authorization_receipt
):
    """Record explicit one-action user authority and emit a bounded dispatch."""
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在。"}
    record = _exploration_action_record(state, str(action_id or "").strip())
    if not record:
        return {"status": "exploration_action_not_found", "topic": topic}
    if record.get("status") != "PLANNED_NOT_AUTHORIZED":
        return {
            "status": "exploration_action_not_authorizable",
            "topic": topic,
            "action_id": action_id,
            "current_status": record.get("status"),
        }
    other_open_actions = [
        item
        for item in state.get("exploration_actions", [])
        if isinstance(item, dict)
        and item.get("action_id") != action_id
        and item.get("status") in {
            "PLANNED_NOT_AUTHORIZED",
            "AUTHORIZED_NOT_EXECUTED",
        }
    ]
    if other_open_actions:
        latest = sorted(
            other_open_actions,
            key=lambda item: (
                int(item.get("sequence") or 0),
                str(item.get("action_id") or ""),
            ),
        )[-1]
        return {
            "status": "exploration_authorization_blocked_open_action",
            "topic": topic,
            "action_id": action_id,
            "blocking_action_id": latest.get("action_id"),
            "blocking_action_status": latest.get("status"),
            "instruction": (
                "检测到另一个开放探索动作；本动作未获授权。先关闭既有"
                "动作并复核状态，禁止并行派发。"
            ),
        }
    if (
        _formal_surface_digest(state)
        != record.get("formal_state_digest_before")
    ):
        return _mark_exploration_plan_stale(
            topic,
            state,
            record,
            "formal_state_changed_after_plan",
            (
                "正式研究状态在计划后发生变化；未执行该动作，"
                "请重新 --plan-exploration。"
            ),
        )
    if (
        _exploration_ledger_digest(state)
        != record.get("exploration_ledger_digest_before")
    ):
        return _mark_exploration_plan_stale(
            topic,
            state,
            record,
            "exploration_ledger_changed_after_plan",
            (
                "探索账本在计划后变化；未授权执行，请重新计划。"
            ),
        )
    receipt = authorization_receipt if isinstance(
        authorization_receipt, dict
    ) else {}
    if (
        receipt.get("explicit_user_authorization") is not True
        or receipt.get("action_id") != action_id
        or receipt.get("authorization_scope")
        != "ONE_BOUNDED_EXPLORATION_ACTION"
        or not _present(receipt.get("authorization_note"))
    ):
        return {
            "status": "exploration_authorization_rejected",
            "topic": topic,
            "action_id": action_id,
            "reason": (
                "需要绑定 action_id 的 explicit_user_authorization=true、"
                "ONE_BOUNDED_EXPLORATION_ACTION 与非空 authorization_note。"
            ),
        }
    try:
        current = _bind_exploration_as_of(
            state,
            hypothesis_engine.exploration_action(
                state, include_host_state=False
            ),
        )
    except ValueError:
        return _mark_exploration_plan_stale(
            topic,
            state,
            record,
            "exploration_as_of_date_invalid",
            "as_of_date 无效；不得执行，重新计划。",
        )
    if (
        _execution_proposal_digest(current)
        != record.get("proposal_digest")
        or _exploration_action_id(
            state, current, int(record.get("sequence") or 0)
        )
        != action_id
    ):
        return _mark_exploration_plan_stale(
            topic,
            state,
            record,
            "exploration_action_changed_after_plan",
            "探索账本已变化；重新 --plan-exploration。",
        )
    record["status"] = "AUTHORIZED_NOT_EXECUTED"
    record["authorization_receipt"] = json.loads(json.dumps(
        receipt, ensure_ascii=False
    ))
    record["authorization_assurance"] = (
        "CALLER_ATTESTED_NOT_HOST_VERIFIED"
    )
    record["exploration_ledger_digest_at_authorization"] = (
        _exploration_ledger_digest(state)
    )
    proposal = record["proposal"]
    document_item_schema = {
        "document_id": "<optional deterministic receipt id>",
        "claim": "<what this document establishes>",
        "source": "<publisher>",
        "url": "<concrete URL>",
        "date": "<YYYY-MM-DD; must be on or before action as_of_date>",
        "publisher_class": proposal.get("source_class"),
    }
    observation_result_schema = {
        "action_id": action_id,
        "as_of_date": proposal.get("as_of_date"),
        "execution_status": "OBSERVATION_RECORDED",
        "query_executed": proposal.get("bounded_query"),
        "search_count": 1,
        "documents_read": [deepcopy(document_item_schema)],
        "automatic_follow_on": False,
        "stop_reason": "<why this one-action run stopped>",
        "proxy_trail": {
            "route_id": (
                proposal.get("route_spec", {}).get("route_id")
                if isinstance(proposal.get("route_spec"), dict)
                else "<exact planned route id>"
            ),
            "planned_proxy": (
                proposal.get("route_spec", {}).get("proxy")
                if isinstance(proposal.get("route_spec"), dict)
                else "<exact planned observable>"
            ),
            "observation": "<actual dated observation from bound receipt>",
            "origin_crux": (
                proposal.get("route_spec", {}).get("origin_crux")
                if isinstance(proposal.get("route_spec"), dict)
                else "<one hypothesis origin crux>"
            ),
            "causal_link": (
                proposal.get("route_spec", {}).get("causal_link")
                if isinstance(proposal.get("route_spec"), dict)
                else "<exact planned diagnostic link>"
            ),
            "direction": "SUPPORTS|CONTRADICTS|AMBIGUOUS",
            "alternative_explanation": "<ordinary explanation>",
            "checkpoint": "<next observable>",
            "next_source_class": proposal.get("source_class"),
            "bounded_query": proposal.get("bounded_query"),
            "stop_condition": proposal.get("stop_condition"),
            "evidence": [{
                "document_id": "<document_id from documents_read>"
            }],
        },
    }
    falsified_result_schema = deepcopy(observation_result_schema)
    falsified_result_schema["execution_status"] = "FALSIFIED_ROUTE"
    falsified_result_schema["proxy_trail"]["direction"] = "CONTRADICTS"
    exhausted_result_schema = {
        "action_id": action_id,
        "as_of_date": proposal.get("as_of_date"),
        "execution_status": "EXHAUSTED",
        "query_executed": proposal.get("bounded_query"),
        "search_count": 1,
        "documents_read": [],
        "documents_read_cardinality": "0..3",
        "documents_read_item_schema": deepcopy(document_item_schema),
        "automatic_follow_on": False,
        "stop_reason": "<why the bounded query was exhausted>",
        "proxy_trail": None,
    }
    record["dispatch_contract"] = {
        "question": proposal.get("question"),
        "source_class": proposal.get("source_class"),
        "bounded_query": proposal.get("bounded_query"),
        "success_condition": proposal.get("success_condition"),
        "stop_condition": proposal.get("stop_condition"),
        "budget_boundary": proposal.get("budget_boundary"),
        "result_schema": {
            "selection_rule": (
                "Choose exactly one schema matching execution_status."
            ),
            "schemas": [
                "observation_result_schema",
                "falsified_result_schema",
                "exhausted_result_schema",
                "runtime_failure_result_schema",
                "in_query_failure_result_schema",
            ],
        },
        "observation_result_schema": observation_result_schema,
        "falsified_result_schema": falsified_result_schema,
        "exhausted_result_schema": exhausted_result_schema,
        "runtime_failure_result_schema": {
            "action_id": action_id,
            "as_of_date": proposal.get("as_of_date"),
            "execution_status": "EXECUTION_FAILED_NO_SEARCH",
            "query_executed": None,
            "search_count": 0,
            "documents_read": [],
            "automatic_follow_on": False,
            "stop_reason": "<why dispatch stopped before any query>",
            "failure_reason": "<tool, network, or runtime failure>",
            "proxy_trail": None,
        },
        "in_query_failure_result_schema": {
            "action_id": action_id,
            "as_of_date": proposal.get("as_of_date"),
            "execution_status": "EXECUTION_FAILED_DURING_QUERY",
            "query_executed": proposal.get("bounded_query"),
            "search_count": 1,
            "documents_read": [],
            "documents_read_cardinality": "0..3",
            "documents_read_item_schema": {
                **deepcopy(document_item_schema),
            },
            "automatic_follow_on": False,
            "stop_reason": "<why the in-flight query stopped>",
            "failure_reason": "<tool, network, or runtime failure>",
            "proxy_trail": None,
        },
        "authority": "EXPLORATION_ONLY_NO_PROMOTION",
        "authorization_assurance": record["authorization_assurance"],
    }
    _save(topic, state)
    return {
        "status": "dispatch_authorized_exploration",
        "topic": topic,
        "action_id": action_id,
        "authorization_assurance": record["authorization_assurance"],
        "dispatch_contract": record["dispatch_contract"],
        "exploration_prompt": (
            "执行且只执行以下一次有界探索动作。不得创建 OpportunitySeed、"
            "CandidateScreen、交易或仓位；达到成功/停止条件即返回 JSON：\n"
            + json.dumps(record["dispatch_contract"], ensure_ascii=False)
        ),
    }


def _receipt_text(value):
    return " ".join(str(value or "").split())


def _exploration_result_sha256(result):
    return hashlib.sha256(json.dumps(
        result,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def _close_stale_authorized_result(
    topic, state, record, result, reason, instruction
):
    """Close a stale authorized action without ingesting its submitted result."""
    result_hash = _exploration_result_sha256(result)
    record["status"] = "STALE_RESULT_NOT_RECORDED"
    record["stale_result_receipt"] = {
        "action_id": record.get("action_id"),
        "reason": reason,
        "result_sha256": result_hash,
        "authorization_occurred": True,
        "result_ingested": False,
        "automatic_retry": False,
    }
    _save(topic, state)
    return {
        "status": "exploration_action_stale",
        "topic": topic,
        "action_id": record.get("action_id"),
        "reason": reason,
        "result_sha256": result_hash,
        "stale_result_receipt": record["stale_result_receipt"],
        "automatic_retry": False,
        "instruction": instruction,
    }


def _document_receipt_key(citation):
    return "|".join((
        crux_engine.citation_source_identity(citation),
        _receipt_text(citation.get("claim")),
        _receipt_text(citation.get("source")),
        _receipt_text(citation.get("date")),
        _receipt_text(citation.get("number")),
    ))


def _canonical_document_receipt(document, publisher_class):
    if not isinstance(document, dict):
        raise ValueError("exploration_result_invalid_document_receipt")
    if (
        not crux_engine.valid_citation(document)
        or document.get("publisher_class") != publisher_class
    ):
        raise ValueError("exploration_result_invalid_document_receipt")
    published = _receipt_text(document.get("date"))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", published):
        raise ValueError(
            "exploration_result_document_date_requires_day_precision"
        )
    try:
        date.fromisoformat(published)
    except ValueError:
        raise ValueError("exploration_result_invalid_document_date")
    receipt = {
        "claim": _receipt_text(document.get("claim")),
        "source": _receipt_text(document.get("source")),
        "url": crux_engine.citation_source_identity(document),
        "date": published,
        "publisher_class": publisher_class,
    }
    for field in ("number", "source_tier"):
        value = _receipt_text(document.get(field))
        if value:
            receipt[field] = value
    key = _document_receipt_key(receipt)
    document_id = "ED-" + hashlib.sha256(
        key.encode("utf-8")
    ).hexdigest()[:16].upper()
    supplied_id = _receipt_text(document.get("document_id"))
    if supplied_id and supplied_id != document_id:
        raise ValueError("exploration_result_document_id_mismatch")
    receipt["document_id"] = document_id
    return receipt


def _validate_exploration_result(record, result):
    if not isinstance(result, dict):
        raise ValueError("exploration_result_must_be_object")
    proposal = record["proposal"]
    budget = proposal.get("budget_boundary", {})
    if result.get("action_id") != record.get("action_id"):
        raise ValueError("exploration_result_action_id_mismatch")
    if result.get("as_of_date") != proposal.get("as_of_date"):
        raise ValueError("exploration_result_as_of_date_mismatch")
    status = str(result.get("execution_status") or "").strip().upper()
    if status not in {
        "OBSERVATION_RECORDED",
        "EXHAUSTED",
        "FALSIFIED_ROUTE",
        "EXECUTION_FAILED_NO_SEARCH",
        "EXECUTION_FAILED_DURING_QUERY",
    }:
        raise ValueError("exploration_result_invalid_execution_status")
    search_count = result.get("search_count")
    if status == "EXECUTION_FAILED_NO_SEARCH":
        if result.get("query_executed") not in (None, ""):
            raise ValueError(
                "failed_no_search_must_not_claim_query_execution"
            )
        if search_count != 0 or isinstance(search_count, bool):
            raise ValueError(
                "failed_no_search_requires_zero_search_count"
            )
        if not _present(result.get("failure_reason")):
            raise ValueError(
                "failed_no_search_requires_failure_reason"
            )
    else:
        if result.get("query_executed") != proposal.get("bounded_query"):
            raise ValueError("exploration_result_query_mismatch")
        if (
            isinstance(search_count, bool)
            or not isinstance(search_count, int)
            or search_count != 1
            or search_count > budget.get("max_bounded_queries", 0)
        ):
            raise ValueError("exploration_result_search_budget_exceeded")
        if (
            status == "EXECUTION_FAILED_DURING_QUERY"
            and not _present(result.get("failure_reason"))
        ):
            raise ValueError(
                "failed_during_query_requires_failure_reason"
            )
    if result.get("automatic_follow_on") is not False:
        raise ValueError("exploration_result_automatic_follow_on_forbidden")
    if not _present(result.get("stop_reason")):
        raise ValueError("exploration_result_stop_reason_required")
    documents = result.get("documents_read")
    if not isinstance(documents, list):
        raise ValueError("exploration_result_documents_read_must_be_list")
    if len(documents) > budget.get("max_documents_read", 0):
        raise ValueError("exploration_result_document_budget_exceeded")
    if status == "EXECUTION_FAILED_NO_SEARCH" and documents:
        raise ValueError("failed_no_search_must_not_read_documents")
    document_receipts = []
    receipt_by_id = {}
    receipt_by_key = {}
    as_of = date.fromisoformat(proposal["as_of_date"])
    for document in documents:
        receipt = _canonical_document_receipt(
            document, proposal.get("source_class")
        )
        published = date.fromisoformat(receipt["date"])
        if published > as_of:
            raise ValueError("exploration_result_document_after_as_of")
        if receipt["document_id"] in receipt_by_id:
            raise ValueError("exploration_result_duplicate_document_receipt")
        receipt_by_id[receipt["document_id"]] = receipt
        receipt_by_key[_document_receipt_key(receipt)] = receipt
        document_receipts.append(receipt)
    publisher_domains = {
        crux_engine.citation_publisher_identity(item)
        for item in document_receipts
        if crux_engine.citation_publisher_identity(item)
    }
    if len(publisher_domains) > budget.get(
        "max_new_publisher_domains", 0
    ):
        raise ValueError("exploration_result_publisher_domain_budget_exceeded")
    if (
        status in {"OBSERVATION_RECORDED", "FALSIFIED_ROUTE"}
        and proposal.get("action_code")
        in {"SEEK_INDEPENDENT_PUBLISHER", "TEST_INDEPENDENT_REPLICATION"}
        and publisher_domains
        & set(proposal.get("excluded_existing_domains", []))
    ):
        raise ValueError(
            "exploration_result_independent_publisher_required"
        )
    proxy = result.get("proxy_trail")
    if status in {"OBSERVATION_RECORDED", "FALSIFIED_ROUTE"}:
        if not document_receipts:
            raise ValueError("exploration_result_document_receipt_required")
        if not isinstance(proxy, dict):
            raise ValueError("exploration_result_proxy_trail_required")
        route_spec = proposal.get("route_spec")
        if not isinstance(route_spec, dict):
            raise ValueError("exploration_result_route_spec_missing")
        if _receipt_text(proxy.get("route_id")) != _receipt_text(
            route_spec.get("route_id")
        ):
            raise ValueError("exploration_result_route_id_mismatch")
        if _receipt_text(proxy.get("planned_proxy")) != _receipt_text(
            route_spec.get("proxy")
        ):
            raise ValueError("exploration_result_planned_proxy_mismatch")
        observation = _receipt_text(proxy.get("observation"))
        if not observation:
            raise ValueError("exploration_result_observation_required")
        if _receipt_text(
            proxy.get("causal_link") or proxy.get("why_diagnostic")
        ) != _receipt_text(route_spec.get("causal_link")):
            raise ValueError("exploration_result_causal_link_not_planned")
        planned_origin = _receipt_text(route_spec.get("origin_crux"))
        if (
            planned_origin
            and _receipt_text(proxy.get("origin_crux")) != planned_origin
        ):
            raise ValueError("exploration_result_origin_crux_mismatch")
        direction = _receipt_text(proxy.get("direction")).upper()
        planned_direction = _receipt_text(
            route_spec.get("direction")
        ).upper()
        if direction not in hypothesis_engine.PROXY_DIRECTIONS:
            raise ValueError("exploration_result_proxy_direction_invalid")
        if status == "FALSIFIED_ROUTE" and direction != "CONTRADICTS":
            raise ValueError(
                "falsified_route_requires_contradicting_proxy"
            )
        for field, expected in (
            ("next_source_class", proposal.get("source_class")),
            ("bounded_query", proposal.get("bounded_query")),
            ("stop_condition", proposal.get("stop_condition")),
        ):
            if _receipt_text(proxy.get(field)) != _receipt_text(expected):
                raise ValueError(
                    f"exploration_result_proxy_{field}_mismatch"
                )
        evidence = proxy.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("exploration_result_proxy_evidence_required")
        if len(evidence) > budget.get("max_documents_read", 0):
            raise ValueError("exploration_result_proxy_evidence_budget_exceeded")
        bound_evidence = []
        seen_ids = set()
        for citation in evidence:
            if not isinstance(citation, dict):
                raise ValueError(
                    "exploration_result_proxy_evidence_not_in_read_receipt"
                )
            document_id = _receipt_text(citation.get("document_id"))
            matched = receipt_by_id.get(document_id) if document_id else None
            has_citation_fields = any(
                _present(citation.get(field))
                for field in ("claim", "source", "url", "date", "number")
            )
            if has_citation_fields:
                if not crux_engine.valid_citation(citation):
                    raise ValueError(
                        "exploration_result_proxy_evidence_not_in_read_receipt"
                    )
                by_key = receipt_by_key.get(
                    _document_receipt_key(citation)
                )
                if matched is not None and by_key != matched:
                    raise ValueError(
                        "exploration_result_proxy_evidence_receipt_mismatch"
                    )
                matched = by_key
            if matched is None:
                raise ValueError(
                    "exploration_result_proxy_evidence_not_in_read_receipt"
                )
            if matched["document_id"] in seen_ids:
                raise ValueError(
                    "exploration_result_duplicate_proxy_evidence"
                )
            seen_ids.add(matched["document_id"])
            bound_evidence.append(deepcopy(matched))
        proxy = json.loads(json.dumps(proxy, ensure_ascii=False))
        proxy["proxy"] = observation
        proxy["planned_direction"] = planned_direction or "AMBIGUOUS"
        proxy["evidence"] = bound_evidence
    elif proxy not in (None, {}):
        raise ValueError("non_observation_result_must_not_submit_proxy")
    return status, document_receipts, proxy


def cmd_submit_exploration_result(topic, action_id, result):
    with _exploration_transaction_lock(topic):
        try:
            return _cmd_submit_exploration_result_locked(
                topic, action_id, result
            )
        except ValueError as exc:
            if str(exc) == "state_revision_conflict":
                result_hash = _exploration_result_sha256(result)
                return {
                    "status": "exploration_result_not_recorded",
                    "topic": topic,
                    "action_id": action_id,
                    "reason": "state_revision_conflict",
                    "result_sha256": result_hash,
                    "automatic_retry": False,
                    "instruction": (
                        "结果执行期间状态被并发更新，系统没有覆盖新状态。"
                        "保留本结果及 SHA-256，人工审阅后重新计划；不得自动重试。"
                    ),
                }
            raise


def _cmd_submit_exploration_result_locked(topic, action_id, result):
    """Close one authorized action and write only its exploration receipt."""
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在。"}
    record = _exploration_action_record(state, str(action_id or "").strip())
    if not record:
        return {"status": "exploration_action_not_found", "topic": topic}
    if record.get("status") != "AUTHORIZED_NOT_EXECUTED":
        return {
            "status": "exploration_result_not_accepted",
            "topic": topic,
            "action_id": action_id,
            "current_status": record.get("status"),
        }
    before = _formal_surface_digest(state)
    if before != record.get("formal_state_digest_before"):
        return _close_stale_authorized_result(
            topic,
            state,
            record,
            result,
            "formal_state_changed_after_authorization",
            (
                "正式研究状态在执行前已变化；未写入结果。保留原始结果，"
                "该授权动作已安全关闭；人工审阅后创建新计划，不得自动重试。"
            ),
        )
    if (
        _exploration_ledger_digest(state)
        != record.get("exploration_ledger_digest_at_authorization")
    ):
        return _close_stale_authorized_result(
            topic,
            state,
            record,
            result,
            "exploration_ledger_changed_after_authorization",
            (
                "探索账本在授权后发生变化；未写入结果。保留原始结果与"
                "回执，该动作已安全关闭；人工审阅后重新规划，不得自动重试。"
            ),
        )
    try:
        execution_status, documents, proxy = _validate_exploration_result(
            record, result
        )
        result_audit = (
            hypothesis_engine.ingest_authorized_action_result(
                state, record, proxy
            )
            if execution_status in {
                "OBSERVATION_RECORDED", "FALSIFIED_ROUTE"
            }
            else {
                "action_id": action_id,
                "hypothesis_id": record["proposal"].get("hypothesis_id"),
                "execution_status": execution_status,
                "accepted_new_proxy_trails": 0,
                "accepted_evidence": 0,
                "state_after": record["proposal"].get("hypothesis_state"),
                "authority": "EXPLORATION_ONLY_NO_PROMOTION",
            }
        )
        result_audit["execution_status"] = execution_status
    except ValueError as exc:
        return {
            "status": "exploration_result_rejected",
            "topic": topic,
            "action_id": action_id,
            "reason": str(exc),
        }
    after = _formal_surface_digest(state)
    if before != after:
        return {
            "status": "exploration_integrity_error",
            "topic": topic,
            "action_id": action_id,
            "reason": "exploration_write_touched_formal_surface",
        }
    result_hash = _exploration_result_sha256(result)
    record["execution_receipt"] = {
        "action_id": action_id,
        "execution_status": execution_status,
        "route_id": record["proposal"].get("route_spec", {}).get(
            "route_id"
        ),
        "planned_proxy": record["proposal"].get("route_spec", {}).get(
            "proxy"
        ),
        "proxy_id": result_audit.get("proxy_id"),
        "observation": result_audit.get("observation"),
        "result_sha256": result_hash,
        "search_count": result["search_count"],
        "documents_read": len(documents),
        "document_receipts": documents,
        "automatic_follow_on": False,
        "stop_reason": str(result["stop_reason"]).strip(),
        "failure_reason": (
            str(result.get("failure_reason") or "").strip() or None
        ),
        "formal_state_digest_after": after,
    }
    record["result_audit"] = result_audit
    try:
        hypothesis_engine.record_authorized_action_outcome(
            state,
            record,
            record["execution_receipt"],
            result_audit,
        )
    except ValueError as exc:
        return {
            "status": "exploration_integrity_error",
            "topic": topic,
            "action_id": action_id,
            "reason": str(exc),
        }
    record["status"] = (
        "FAILED_NO_SEARCH"
        if execution_status == "EXECUTION_FAILED_NO_SEARCH"
        else (
            "FAILED_DURING_QUERY"
            if execution_status == "EXECUTION_FAILED_DURING_QUERY"
            else "COMPLETED"
        )
    )
    _save(topic, state)
    return {
        "status": "exploration_result_recorded",
        "topic": topic,
        "action_id": action_id,
        "execution_receipt": record["execution_receipt"],
        "result_audit": result_audit,
        "hypothesis_exploration": hypothesis_engine.summary(state),
        "formal_state_unchanged": True,
        "automatic_follow_on": False,
        "instruction": (
            "探索结果已入独立账本；未创建候选、正式状态、交易或后续自动任务。"
        ),
    }


def cmd_screen(topic, as_of_date="", seed_id=""):
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在，请先完成 -deepthink2。"}
    if state.get("last_convergence", {}).get("decision") != "converge":
        return {"status": "blocked_unconverged", "topic": topic,
                "instruction": "根命题尚未收敛，禁止提前消耗候选筛选资源。"}
    try:
        as_of_date = candidate_screen_engine.normalize_as_of(as_of_date)
    except ValueError as exc:
        return {"status": "error", "reason": str(exc)}
    seeds = candidate_screen_engine.screenable_seeds(state, seed_id or None)
    if not seeds:
        return {"status": "no_screenable_candidates", "topic": topic,
                "seed_id": seed_id or None,
                "instruction": "没有未筛选的 READY_FOR_SCREENING 候选；指定 --seed-id 可重筛已有候选。"}
    latest = candidate_screen_engine.latest_by_seed(state)
    if seed_id and seed_id in latest:
        previous_as_of = str(latest[seed_id].get("as_of_date") or "")
        if as_of_date <= previous_as_of:
            return {
                "status": "blocked_screen_as_of_not_newer",
                "topic": topic,
                "seed_id": seed_id,
                "requested_as_of_date": as_of_date,
                "previous_as_of_date": previous_as_of,
                "previous_screen_id": latest[seed_id].get("screen_id"),
                "instruction": (
                    "同一 as-of 不允许用新 payload 覆盖历史筛选。等待新的观察日并使用严格更晚的 "
                    "--as-of；原筛选保持不可变。"
                ),
            }
    prompts = candidate_screen_prompts(state, seeds, as_of_date)
    dispatch_id = "CSD-" + hashlib.sha256(
        f"{as_of_date}|{'|'.join(prompts['candidate_seed_ids'])}".encode("utf-8")
    ).hexdigest()[:10].upper()
    record = {
        "dispatch_id": dispatch_id,
        "as_of_date": as_of_date,
        "candidate_seed_ids": prompts["candidate_seed_ids"],
        "screen_mode": prompts["screen_mode"],
        "rescreen_context": prompts["rescreen_context"],
        "selection_audit": prompts["selection_audit"],
        "max_batch": candidate_screen_engine.MAX_BATCH,
        "prompt_sha256": {
            "analyst": hashlib.sha256(prompts["analyst_prompt"].encode("utf-8")).hexdigest(),
            "skeptic": hashlib.sha256(prompts["skeptic_prompt"].encode("utf-8")).hexdigest(),
        },
    }
    history = state.setdefault("candidate_screen_dispatches", [])
    if not isinstance(history, list):
        history = state["candidate_screen_dispatches"] = []
    existing_dispatch = next(
        (item for item in history if isinstance(item, dict) and item.get("dispatch_id") == dispatch_id),
        None,
    )
    if existing_dispatch is not None and existing_dispatch != record:
        return {
            "status": "blocked_candidate_screen_dispatch_conflict",
            "topic": topic,
            "dispatch_id": dispatch_id,
            "instruction": "同一 dispatch identity 已绑定不同内容；保留原记录并停止。",
        }
    if existing_dispatch is None:
        history.append(record)
    _save(topic, state)
    out = {
        "status": "dispatch_candidate_screeners",
        "topic": topic,
        "as_of_date": as_of_date,
        "dispatch_id": dispatch_id,
        "max_batch": candidate_screen_engine.MAX_BATCH,
        "model": model_for("candidate_analyst"),
        "isolation_required": True,
        "instruction": (
            "在隔离上下文分别运行 Candidate Analyst 与 Candidate Skeptic；"
            "收集 JSON 后调用 --submit-screen，并传回同一 --as-of。"
        ),
    }
    out.update(prompts)
    return out


def cmd_plan_candidate_gaps(topic):
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在，请先完成 -deepthink2。"}
    result = candidate_gap_engine.plan_tasks(state)
    if result.get("task_count"):
        opportunity_engine.refresh_candidate_states(state)
        _save(topic, state)
    return {"topic": topic, **result, **candidate_gap_engine.summary(state)}


def cmd_submit_gap_evidence(topic, task_id, supplement):
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在。"}
    try:
        result = candidate_gap_engine.submit_supplement(
            state, str(task_id or ""), supplement
        )
    except ValueError as exc:
        return {"status": "candidate_gap_evidence_rejected", "reason": str(exc)}
    _save(topic, state)
    screen = cmd_screen(
        topic,
        state.get("frame_contract", {}).get("as_of_date", ""),
    )
    out = {"topic": topic, **result, **candidate_gap_engine.summary(state)}
    if screen.get("status") == "dispatch_candidate_screeners":
        out.update(screen)
        out["gap_evidence_status"] = result["status"]
        out["instruction"] = (
            "候选已确定性进入 READY_FOR_SCREENING；继续隔离运行默认 Top-3 CandidateScreen。"
        )
    return out


def cmd_close_gap_task(topic, task_id, status, reason):
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在。"}
    try:
        result = candidate_gap_engine.close_task(
            state, str(task_id or ""), status, reason
        )
    except ValueError as exc:
        return {"status": "candidate_gap_close_rejected", "reason": str(exc)}
    _save(topic, state)
    return {"topic": topic, **result, **candidate_gap_engine.summary(state)}


def cmd_submit_screen(
    topic, analyst, skeptic, as_of_date="", isolation_status="unverified",
    isolation_receipt=None,
):
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在。"}
    if state.get("last_convergence", {}).get("decision") != "converge":
        return {"status": "blocked_unconverged", "topic": topic,
                "instruction": "根命题尚未收敛，禁止候选升级。"}
    analyst = analyst if isinstance(analyst, dict) else {}
    skeptic = skeptic if isinstance(skeptic, dict) else {}
    try:
        audit = candidate_screen_engine.evaluate_batch(
            state, analyst, skeptic,
            as_of_date or analyst.get("as_of_date") or skeptic.get("as_of_date"),
            isolation_status=isolation_status,
            isolation_receipt=isolation_receipt,
        )
    except ValueError as exc:
        return {"status": "error", "reason": str(exc)}
    if audit.get("conflicting_screen_ids"):
        return {
            "status": "candidate_screen_submission_conflict",
            "topic": topic,
            "screen_audit": audit,
            "instruction": (
                "同一 seed/as-of 已存在不同提交；历史记录未被覆盖。使用严格更晚的 --as-of "
                "重新 dispatch，不得修改或删除旧筛选。"
            ),
        }
    _save(topic, state)
    latest = candidate_screen_engine.latest_by_seed(state)
    thesis_candidates = [
        screen.get("promotion_packet") for screen in latest.values()
        if screen.get("status") == "THESIS_CANDIDATE"
    ]
    return {
        "status": "candidate_screen_complete",
        "topic": topic,
        "screen_audit": audit,
        **candidate_screen_engine.summary(state),
        "thesis_candidate_drafts": thesis_candidates,
        "instruction": (
            "重新调用 --report 查看宝藏地图筛选矩阵；再调用 --verification-plan。"
            "THESIS_CANDIDATE 必须先完成页面快照与 claim 对齐，才进入人工确认。"
        ),
    }


def cmd_verification_plan(topic, seed_id=""):
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在。"}
    plan = claim_verification_engine.verification_plan(state, seed_id or None)
    if not plan["claim_count"]:
        return {"status": "no_claims_to_verify", "topic": topic,
                "instruction": "当前没有 THESIS_CANDIDATE 的决定性 claim。"}
    return {
        "status": "need_source_snapshots",
        "topic": topic,
        **plan,
        "instruction": (
            "使用 scripts/evidence_snapshot.py 或宿主抓取器取得每个具体 URL 的页面快照；"
            "然后调用 --verify-claims --snapshots '<json>'。"
        ),
    }


def cmd_verify_claims(topic, snapshots, seed_id="", requested_claim_id=""):
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在。"}
    packet = claim_verification_engine.build_verifier_packet(
        state, snapshots, seed_id or None, requested_claim_id or None
    )
    if not packet["claims"]:
        return {
            "status": "need_source_snapshots",
            "topic": topic,
            "missing_snapshot_claim_ids": packet["missing_snapshot_claim_ids"],
            "rejected_snapshots": packet["rejected_snapshots"],
            "instruction": "没有可送审的有效快照；补齐或修复 snapshot hash 后重试。",
        }
    prompt = (
        f"[Claim Verifier · claim_verifier.md · model={model_for('claim_verifier')}]\n"
        "只使用下列 content-hashed snapshot excerpt 审核 claim。"
        "SUPPORTS/CONTRADICTS 必须给出快照中逐字存在的短 quote；不得浏览替换来源。\n"
        + json.dumps(packet, ensure_ascii=False, indent=2)
        + "\n严格按 claim-verification-protocol.md 输出 JSON。"
    )
    dispatch = claim_verification_engine.verifier_dispatch_record(packet, prompt)
    history = state.setdefault("claim_verifier_dispatches", [])
    if not isinstance(history, list):
        history = state["claim_verifier_dispatches"] = []
    existing = next((
        item for item in history
        if isinstance(item, dict) and item.get("dispatch_id") == dispatch["dispatch_id"]
    ), None)
    if existing is not None and existing != dispatch:
        return {
            "status": "blocked_claim_verifier_dispatch_conflict",
            "topic": topic,
            "dispatch_id": dispatch["dispatch_id"],
            "instruction": "同一 verifier dispatch identity 已绑定不同内容；保留原记录并停止。",
        }
    if existing is None:
        history.append(dispatch)
        _save(topic, state)
    return {
        "status": "dispatch_claim_verifier",
        "topic": topic,
        "model": model_for("claim_verifier"),
        "verifier_isolation_required": True,
        **dispatch,
        "verifier_prompt": prompt,
        "missing_snapshot_claim_ids": packet["missing_snapshot_claim_ids"],
        "rejected_snapshots": packet["rejected_snapshots"],
        "instruction": "在独立上下文运行 Claim Verifier，再调用 --submit-verification。",
    }


def cmd_submit_verification(topic, snapshots, verifier, seed_id="", requested_claim_id="",
                            isolation_status="unverified", isolation_receipt=None):
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在。"}
    audit = claim_verification_engine.apply_verifier_results(
        state, snapshots, verifier, seed_id or None, requested_claim_id or None,
        isolation_status=isolation_status,
        isolation_receipt=isolation_receipt,
    )
    if audit.get("conflicting_claim_ids"):
        return {
            "status": "claim_verification_submission_conflict",
            "topic": topic,
            "verification_audit": audit,
            "instruction": (
                "同一 claim/snapshot 已存在不同 verifier 提交；旧结果保持不变。"
                "不得覆盖、删除或重写，需使用新的合法 snapshot 才能形成新记录。"
            ),
        }
    _save(topic, state)
    latest = candidate_screen_engine.latest_by_seed(state)
    promotion_packets = [
        screen.get("promotion_packet") for screen in latest.values()
        if screen.get("claim_verification_status") == "VERIFIED"
    ]
    return {
        "status": "claim_verification_complete",
        "topic": topic,
        "verification_audit": audit,
        **claim_verification_engine.summary(state),
        "verified_promotion_drafts": promotion_packets,
        "instruction": (
            "继续处理 verification plan 中剩余 claim，并重新调用 --report。"
            "只有 VERIFIED 候选才恢复 DRAFT_REQUIRES_HUMAN。"
        ),
    }


def cmd_resolution_memo(topic):
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在。"}
    if state.get("last_convergence", {}).get("decision") == "converge":
        return {
            "status": "resolution_not_needed",
            "topic": topic,
            "formal_report_allowed": True,
            "instruction": "engine 已收敛；调用 --report 生成正式报告。",
        }
    packet = research_output.build_continuation_packet(state)
    return {
        "status": "resolution_memo_ready",
        "topic": topic,
        "formal_report_allowed": False,
        "resolution_memo_markdown": research_output.render_resolution_memo(state),
        "continuation_packet": packet,
        "audit_state_path": _path(topic),
        "instruction": (
            "保存 resolution_memo_markdown 和 continuation_packet；不要保存 transcript。"
            "继续研究必须由用户显式授权后调用 --resume-blocked。"
        ),
    }


def cmd_resume_blocked(topic, extra_rounds=0):
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在。"}
    if state.get("last_convergence", {}).get("decision") != "fuse_break":
        return {
            "status": "resume_not_allowed",
            "topic": topic,
            "instruction": "只有 fuse_break 状态可显式扩展；普通 continue 直接按 dispatch prompt 执行。",
        }
    try:
        extra_rounds = int(extra_rounds)
    except (TypeError, ValueError):
        extra_rounds = 0
    if extra_rounds <= 0:
        return {
            "status": "resume_requires_explicit_extension",
            "topic": topic,
            "recommended_extra_rounds": research_output.recommended_extra_rounds(
                state,
                research_output.build_continuation_packet(state).get("open_cruxes", []),
            ),
            "instruction": "显式传入 --extra-rounds N；该命令会继续消耗研究 Token。",
        }
    current_round = len(state.get("rounds", []))
    try:
        old_max = int(state.get("config", {}).get("MAX_ROUNDS", current_round))
    except (TypeError, ValueError):
        old_max = current_round
    new_max = min(crux_engine.MAX_ROUNDS, max(old_max, current_round) + extra_rounds)
    if new_max <= current_round:
        return {
            "status": "blocked_hard_fuse",
            "topic": topic,
            "hard_max_rounds": crux_engine.MAX_ROUNDS,
            "instruction": "已达到硬上限；保留 Resolution Memo，禁止继续自动扩展。",
        }
    state["config"]["MAX_ROUNDS"] = new_max
    state.setdefault("resume_history", []).append({
        "from_round": current_round,
        "old_max_rounds": old_max,
        "new_max_rounds": new_max,
        "reason": "explicit_user_authorization_required",
    })
    out = {
        "status": "dispatch_subagents",
        "topic": topic,
        "resumed_from_blocked": True,
        "old_max_rounds": old_max,
        "new_max_rounds": new_max,
        "round": current_round + 1,
    }
    out.update(dispatch_prompts(state, current_round + 1))
    _save(topic, state)
    out["instruction"] = (
        "只处理 continuation packet 中的 OPEN crux。不要读取历史 transcript；"
        "使用本次 compact prompts，完成后调用 --submit。"
    )
    return out

def cmd_report(topic, challenge_only=False, report_view="full", include_synthesis=True, allow_non_formal=False):
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在。"}
    conv = state.get("last_convergence", {})
    converged = conv.get("decision") == "converge"
    # Close out exhausted probe slots first so the grade reflects the honest
    # coverage outcome rather than a stale UNPROBED.
    landscape = landscape_engine.finalize_coverage(state, len(state.get("rounds", [])))
    grade = crux_engine.research_grade(state)

    if allow_non_formal and not converged:
        import report_v2
        ledger_md = report_v2.render_non_formal_ledger(state)
        return {"status": "non_formal_ledger_ready", "topic": topic,
                "formal_report_allowed": False,
                "convergence": conv,
                **grade,
                "evidence_ledger_markdown": ledger_md,
                "instruction": "非正式证据账本已生成（研究未收敛）。"}

    # An unconverged run still delivers its research.  The grade and the two hard
    # gates carry the limitation; withholding the report only pushed operators
    # into hand-writing one outside the engine.
    degraded_extras = {}
    if not converged:
        resolution = cmd_resolution_memo(topic)
        degraded_extras = {
            "unresolved_cruxes": [
                cid for cid, cx in state.get("cruxes", {}).items()
                if cx.get("status") in ("PENDING", "OPEN")
            ],
            "resolution_memo_markdown": resolution.get("resolution_memo_markdown"),
            "continuation_packet": resolution.get("continuation_packet"),
        }

    rd = crux_engine.report_data(state)
    opportunity_question = landscape_engine.is_required(state)
    if (converged and opportunity_question and not challenge_only
            and not state.get("candidate_screens")):
        dispatch = cmd_screen(
            topic,
            state.get("frame_contract", {}).get("as_of_date", ""),
        )
        if dispatch.get("status") == "dispatch_candidate_screeners":
            degraded_extras["candidate_screen_dispatch"] = dispatch
    # Refresh tracking ledger to reflect any post-submit state transitions before
    # the report view model captures tracking_rows.
    tracking_engine.sync_tracking_ledger(state, len(state.get("rounds", [])))
    import report_v2
    opportunity_counts = opportunity_engine.summary(state)
    gap_counts = candidate_gap_engine.summary(state)
    candidate_counts = candidate_screen_engine.summary(state)
    verification_counts = claim_verification_engine.summary(state)
    view_model = report_v2.build_report_view_model(state)
    facts_box_markdown = report_v2.render_facts_box(view_model)
    evidence_ledger_markdown = report_v2.render(state, view="audit")
    candidate_cards_markdown = report_v2.render(state, view="cards")
    out = {"status": "report_data_ready", "topic": topic,
            "convergence": conv,
            "formal_report_allowed": grade["report_grade"] == "FORMAL",
            **grade,
            **degraded_extras,
            "decision": rd["decision"], "binding_crux": rd["binding_crux"],
            "focus_crux": rd["focus_crux"], "aggregation_rule": rd["aggregation_rule"],
            "research_verdict": rd["research_verdict"],
            "landscape_coverage": landscape,
            "hypothesis_exploration": hypothesis_engine.summary(state),
            "exploration_action": hypothesis_engine.exploration_action(state),
            "support_weakest": rd["support_weakest"], "support_mean": rd["support_mean"],
            "n_unique_sources": rd["n_unique_sources"],
            "n_primary_sources": rd["n_primary_sources"],
            **opportunity_counts,
            **gap_counts,
            **candidate_counts,
            **verification_counts,
            "model": model_for("battle_log_synthesis"),
            "report_view": report_view,
            "available_report_views": [
                "facts_box", "brief", "cards", "audit", "full"
            ],
            "report_view_model": view_model,
            "facts_box_markdown": facts_box_markdown,
            "facts_box_sha256": hashlib.sha256(
                facts_box_markdown.encode("utf-8")
            ).hexdigest(),
            "evidence_ledger_markdown": evidence_ledger_markdown,
            "candidate_cards_markdown": candidate_cards_markdown,
            "report_markdown": report_v2.render(state, view=report_view),
            "report_markdown_deprecated": True,
            "audit_state_path": _path(topic),
            "instruction": (
                "交付两个主文件：1. Decision Brief（总计≤150行）：顶部原样嵌入 "
                "facts_box_markdown，再基于 report_view_model（若显式提供，也可使用 "
                "synthesis_packet）写≤120行、由研究发现驱动的自由叙事；"
                "不得采用跨报告固定节段名。2. Evidence Ledger：直接保存 "
                "evidence_ledger_markdown。candidate_cards_markdown 可嵌入 Brief 末尾"
                "或独立保存。LLM 严禁修改 facts box 的数值、状态词、crux 内容、"
                "候选计数或正式动作；引用只能来自结构化输入并以内联链接标注。"
                "formal_action 与 exploration_action 必须分开解释，且不得读取 "
                "transcript、扩展候选、执行探索动作或改变 engine 状态。"
                "3. 断言分档：VERIFIED 档可直接陈述；SINGLE_SOURCE 档必须标注"
                "『单一来源·未交叉验证』；HYPOTHESIS 档必须标注『假说』，"
                "但允许写进正文——假说是洞见来源，撕掉标签才是违规。"
                "4. 证据条数、轮次、收敛状态一律读取 evidence_counts，严禁自行撰写。"
                f"5. 本次 report_grade={grade['report_grade']}；"
                f"publication_allowed={grade['publication_allowed']}（对外发布闸），"
                f"ranking_allowed={grade['ranking_allowed']}（个股排序闸）。"
                "这两道闸为 false 时，禁止产出对外传播稿或对具名标的排序/推荐。"
            )}
    if include_synthesis:
        out["synthesis_packet"] = research_output.build_synthesis_packet(state)
        out["instruction"] += (
            " synthesis_packet 是写作层的交接契约：风格自由，但其中的 "
            "evidence_counts / claim_tiers / 两道闸门为约束。风格化产物"
            "（不含 Facts Box）用 `validate_report_v2.py --styled` 做出处 lint。"
        )
    return out


# ── CLI ──────────────────────────────────────────────────────────────────────
def _jload(s):
    if s and os.path.exists(s):
        s = open(s, encoding="utf-8").read()
    return json.loads(s) if s else {}

def main():
    ap = argparse.ArgumentParser(description="Trade Nothing v0.13.0 Crux Orchestrator")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--frame", action="store_true")
    g.add_argument("--init", action="store_true")
    g.add_argument("--submit", action="store_true")
    g.add_argument("--report", action="store_true")
    g.add_argument("--resolution-memo", action="store_true")
    g.add_argument("--resume-blocked", action="store_true")
    g.add_argument("--plan-exploration", action="store_true")
    g.add_argument("--record-exploration-design", action="store_true")
    g.add_argument("--cancel-exploration-action", action="store_true")
    g.add_argument("--authorize-exploration", action="store_true")
    g.add_argument("--submit-exploration-result", action="store_true")
    g.add_argument("--screen", action="store_true")
    g.add_argument("--plan-candidate-gaps", action="store_true")
    g.add_argument("--submit-gap-evidence", action="store_true")
    g.add_argument("--close-gap-task", action="store_true")
    g.add_argument("--submit-screen", action="store_true")
    g.add_argument("--verification-plan", action="store_true")
    g.add_argument("--verify-claims", action="store_true")
    g.add_argument("--submit-verification", action="store_true")
    g.add_argument("--runtime-failure", action="store_true")
    g.add_argument("--create-run", action="store_true")
    g.add_argument("--adopt-run", action="store_true")
    g.add_argument("--selftest", action="store_true")
    ap.add_argument("--topic", default="")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--state-path", default="")
    ap.add_argument("--frame-json", default="")
    ap.add_argument("--start-packet", default="",
                    help="tradenothing-next research-start packet JSON path or object")
    ap.add_argument("--briefing", default="", help="optional user briefing text or URL for framing context")
    ap.add_argument("--det", default=""); ap.add_argument("--inq", default=""); ap.add_argument("--judge", default="")
    ap.add_argument("--analyst", default=""); ap.add_argument("--skeptic", default="")
    ap.add_argument("--as-of", default=""); ap.add_argument("--seed-id", default="")
    ap.add_argument("--task-id", default="")
    ap.add_argument("--supplement", default="")
    ap.add_argument("--close-status", default="",
                    choices=["", "SOURCE_EXHAUSTED", "WAITING_EVENT"])
    ap.add_argument("--close-reason", default="")
    ap.add_argument("--screen-isolation", default="unverified",
                    choices=["verified", "degraded", "unverified"])
    ap.add_argument("--runtime-isolation", default="unverified",
                    choices=["verified", "degraded", "unverified"])
    ap.add_argument("--run-purpose", default="", choices=sorted(run_registry.RUN_PURPOSES))
    ap.add_argument("--isolation-receipt", default="")
    ap.add_argument("--snapshots", default=""); ap.add_argument("--verifier", default="")
    ap.add_argument("--claim-id", default="")
    ap.add_argument("--challenge-only", action="store_true",
                    help="render root-thesis report without default opportunity CandidateScreen")
    ap.add_argument("--allow-non-formal", action="store_true",
                    help="generate non-formal evidence ledger even when unconverged")
    ap.add_argument("--report-view", default="full",
                    choices=["facts_box", "brief", "cards", "audit", "full"],
                    help="select one deterministic report view")
    ap.add_argument("--no-synthesis", action="store_true",
                    help="omit the writing-layer synthesis packet (it is included by default "
                         "because it carries the assertion contract)")
    ap.add_argument("--extra-rounds", type=int, default=0)
    ap.add_argument("--action-id", default="")
    ap.add_argument("--exploration-design", default="")
    ap.add_argument("--authorization-receipt", default="")
    ap.add_argument("--exploration-result", default="")
    ap.add_argument("--stage", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--verifier-isolation", default="unverified",
                    choices=["verified", "degraded", "unverified"])
    ap.add_argument("--verifier-isolation-receipt", default="")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.create_run or a.adopt_run:
        try:
            if a.create_run and not a.run_purpose:
                raise ValueError("run_purpose_required_for_new_run")
            manifest = (
                run_registry.adopt_manifest(a.topic, a.state_path)
                if a.adopt_run
                else run_registry.create_manifest(
                    a.topic, state_path=a.state_path,
                    runtime_isolation=a.runtime_isolation,
                    run_purpose=a.run_purpose,
                )
            )
            out = {
                "status": "run_adopted" if a.adopt_run else "run_created",
                "topic": manifest["topic"],
                "run_id": manifest["run_id"],
                "run_purpose": manifest["run_purpose"],
                "state_path": manifest["state_path"],
                "instruction": (
                    "后续命令只传 --run-id；不要再用自然语言 topic 寻址。"
                ),
            }
            print(json.dumps(run_registry.stage_envelope(out, context=manifest),
                             ensure_ascii=False, indent=2))
            return
        except ValueError as exc:
            print(json.dumps({"status": "run_identity_error", "reason": str(exc)},
                             ensure_ascii=False, indent=2))
            return
    context = None
    try:
        context = run_registry.resolve_context(
            run_id=a.run_id, state_path=a.state_path, topic=a.topic
        )
        if context:
            run_registry.bind_context(context)
            a.topic = context["topic"]
    except ValueError as exc:
        print(json.dumps({"status": "run_identity_error", "reason": str(exc)},
                         ensure_ascii=False, indent=2))
        return
    try:
        start_packet = _jload(a.start_packet) if a.start_packet else None
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "status": "start_packet_rejected",
            "topic": a.topic,
            "reason": f"cannot load research-start packet: {exc}",
        }, ensure_ascii=False, indent=2))
        return
    if a.frame:  out = cmd_frame(a.topic, start_packet, briefing=a.briefing)
    elif a.init: out = cmd_init(
        a.topic, _jload(a.frame_json), a.runtime_isolation, start_packet
    )
    elif a.submit: out = cmd_submit(a.topic, _jload(a.det), _jload(a.inq), _jload(a.judge))
    elif a.report: out = cmd_report(
        a.topic,
        challenge_only=a.challenge_only,
        report_view=a.report_view,
        include_synthesis=not a.no_synthesis,
        allow_non_formal=a.allow_non_formal,
    )
    elif a.resolution_memo: out = cmd_resolution_memo(a.topic)
    elif a.resume_blocked: out = cmd_resume_blocked(a.topic, a.extra_rounds)
    elif a.record_exploration_design: out = cmd_record_exploration_design(
        a.topic, _jload(a.exploration_design)
    )
    elif a.plan_exploration: out = cmd_plan_exploration(a.topic)
    elif a.cancel_exploration_action: out = cmd_cancel_exploration_action(
        a.topic, a.action_id, a.reason
    )
    elif a.authorize_exploration: out = cmd_authorize_exploration(
        a.topic, a.action_id, _jload(a.authorization_receipt)
    )
    elif a.submit_exploration_result: out = cmd_submit_exploration_result(
        a.topic, a.action_id, _jload(a.exploration_result)
    )
    elif a.screen: out = cmd_screen(a.topic, a.as_of, a.seed_id)
    elif a.plan_candidate_gaps: out = cmd_plan_candidate_gaps(a.topic)
    elif a.submit_gap_evidence: out = cmd_submit_gap_evidence(
        a.topic, a.task_id, _jload(a.supplement)
    )
    elif a.close_gap_task: out = cmd_close_gap_task(
        a.topic, a.task_id, a.close_status, a.close_reason
    )
    elif a.submit_screen: out = cmd_submit_screen(
        a.topic, _jload(a.analyst), _jload(a.skeptic), a.as_of, a.screen_isolation,
        _jload(a.isolation_receipt),
    )
    elif a.verification_plan: out = cmd_verification_plan(a.topic, a.seed_id)
    elif a.verify_claims: out = cmd_verify_claims(
        a.topic, _jload(a.snapshots), a.seed_id, a.claim_id
    )
    elif a.submit_verification: out = cmd_submit_verification(
        a.topic, _jload(a.snapshots), _jload(a.verifier), a.seed_id, a.claim_id,
        a.verifier_isolation, _jload(a.verifier_isolation_receipt)
    )
    elif a.runtime_failure: out = cmd_runtime_failure(a.topic, a.stage, a.reason)
    if context:
        out = run_registry.stage_envelope(out, context=context)
    print(json.dumps(out, ensure_ascii=False, indent=2))


# ── bounded end-to-end wiring self-test over deterministic fixture signals ──
def selftest():
    topic = "绿色算力景气度与产业链_v2selftest"
    if os.path.exists(_path(topic)): os.remove(_path(topic))
    frame = {
        "decision_question": "绿色算力产业链是否值得做多(3-6月)", "horizon": "3-6M",
        "question_type": "CONJUNCTIVE",
        "logic_graph": {
            "root_id": "Q1",
            "nodes": [
                {"id": "Q1", "node_type": "QUESTION", "label": "是否值得继续筛选"},
                {"id": "C1", "node_type": "CRUX", "label": "时空错配/储能成本"},
                {"id": "C2", "node_type": "CRUX", "label": "液冷/PFAS介质"},
                {"id": "C3", "node_type": "CRUX", "label": "WUE水资源红线"},
            ],
            "edges": [
                {"from": "C1", "to": "Q1", "relation": "REQUIRED_FOR"},
                {"from": "C2", "to": "Q1", "relation": "REQUIRED_FOR"},
                {"from": "C3", "to": "Q1", "relation": "REQUIRED_FOR"},
            ],
        },
        "as_of_date": "2026-07-11",
        "unit_of_analysis": "绿色算力产业链资产",
        "thesis_seed": "若能源约束能够转化为可兑现现金流，市场可能低估相关基础设施资产",
        "premise_audit": [{
            "id": "P1", "claim": "能源约束可能形成可兑现的基础设施收益",
            "status": "HYPOTHESIS", "as_of": "UNKNOWN", "source_url": None,
            "required_primary_source": "项目合同、费率文件与并网数据", "use": "定义研究方向",
        }],
        "candidate_cruxes": [
            {"id":"C1","label":"时空错配/储能成本","logic_role":"THESIS_HINGE","definition":"综合电力成本能否支持项目收益",
             "monitor_anchor":"西部到户综合电价(含储能)、储能EPC元/Wh", "falsifier":"综合成本持续高于项目承受上限",
             "evidence_plan":[
                 {"plan_id":"C1-A","publisher_class":"REGULATOR_OR_OFFICIAL_DATASET",
                  "target_claim":"项目到户电价与并网约束","search_query":"官方 项目 电价 并网"},
                 {"plan_id":"C1-B","publisher_class":"PROJECT_OWNER",
                  "target_claim":"储能配置与项目承受成本","search_query":"项目业主 储能 配置 成本"}],
             "catalyst_window":{"event":"项目合同或费率披露", "expected_by":"2026-10-31",
                                "date_status":"REVIEW_CHECKPOINT", "basis_claim_id":"P1"}},
            {"id":"C2","label":"液冷/PFAS介质","logic_role":"THESIS_HINGE","definition":"冷却介质是否构成可兑现瓶颈",
             "monitor_anchor":"冷板式市占率、巨化/新宙邦氟化液产能", "falsifier":"替代介质快速规模化",
             "evidence_plan":[
                 {"plan_id":"C2-A","publisher_class":"ISSUER_OR_FILING",
                  "target_claim":"冷却介质产能与订单兑现","search_query":"发行人 冷却介质 产能 订单"},
                 {"plan_id":"C2-B","publisher_class":"CUSTOMER_OR_COUNTERPARTY",
                  "target_claim":"客户技术选型与验证节奏","search_query":"客户 液冷 验证 技术选型"}],
             "catalyst_window":{"event":"供应商产能与订单披露", "expected_by":"2026-11-30",
                                "date_status":"REVIEW_CHECKPOINT", "basis_claim_id":"P1"}},
            {"id":"C3","label":"WUE水资源红线","logic_role":"THESIS_HINGE","definition":"水资源约束是否改变技术选型",
             "monitor_anchor":"西部干冷器节点实测WUE、水预算配额", "falsifier":"审批与项目数据未体现水约束",
             "evidence_plan":[
                 {"plan_id":"C3-A","publisher_class":"REGULATOR_OR_OFFICIAL_DATASET",
                  "target_claim":"项目用水许可与审批约束","search_query":"官方 数据中心 用水许可 环评"},
                 {"plan_id":"C3-B","publisher_class":"PROJECT_OWNER",
                  "target_claim":"项目WUE与冷却技术选型","search_query":"项目业主 WUE 冷却 技术"}],
             "catalyst_window":{"event":"项目环评或用水许可披露", "expected_by":"2026-12-31",
                                "date_status":"REVIEW_CHECKPOINT", "basis_claim_id":"P1"}}],
        "forbidden_consensus": ["产能过剩内卷","ESG合规成本"],
        "no_edge_precheck": {"is_researchable": True, "basis_type": "TESTABILITY",
                             "basis_claim_ids": ["P1"], "reason": "合同、费率与项目数据可检验"},
        "suggested_max_rounds": 12}
    LATE = {5:{"id":"C4","label":"电网零惯量/RoCoF","monitor_anchor":"GFM-BESS循环寿命@阶跃负荷"},
            6:{"id":"C5","label":"变压器/GOES产能墙","monitor_anchor":"0.18mm取向硅钢良率"},
            9:{"id":"C6","label":"需求/供给过剩/绿证","monitor_anchor":"智算上架率、绿证均价、训练/推理结构"}}
    SIG = {"C1":{1:-0.5,3:0.5,4:0.5,5:0.5,7:0.5,8:0.5,9:1.0,10:0.5,11:0.5,12:-0.5},
           "C2":{2:-0.5,3:0.5,4:0.5,5:1.0,6:0.5,8:0.5,9:1.0,11:0.5,12:0.5},
           "C3":{1:-0.5,2:0.5,3:0.5,4:1.0,7:0.5,11:-0.5},
           "C4":{5:-0.5,7:0.5,8:0.5,9:1.0,10:0.5,12:-1.0},
           "C5":{6:-0.5,8:0.5,11:1.0,12:-0.3},
           "C6":{9:-1.0,10:-0.5,11:0.2}}
    out = cmd_init(topic, frame)
    if out.get("status") != "dispatch_subagents":
        raise RuntimeError(
            "selftest init failed current frame contract: "
            + json.dumps(out, ensure_ascii=False, sort_keys=True)
        )
    print(f"INIT → status={out['status']}, R1 open={out['open_cruxes']}")
    # free-roam: Inquisitor lands a NEW hard-data attack on already-resolved C4 at R12 (GFM-BESS电芯寿命)
    FREEROAM = {12: ("C4", -1.0)}
    for r in range(1, 13):
        st = _load(topic)
        # mock judge output from SIG, scoped to currently-open cruxes; introduce late cruxes here
        new = [LATE[r]] if r in LATE else []
        score_ids = set(dispatch_prompts(st, r)["dispatch_cruxes"] + [c["id"] for c in new])
        if r in FREEROAM:                       # free-roam may score a retired crux -> re-open
            score_ids.add(FREEROAM[r][0])
        cs = {}
        for cid in score_ids:
            s = FREEROAM[r][1] if (r in FREEROAM and cid == FREEROAM[r][0]) else SIG.get(cid,{}).get(r,0.0)
            cs[cid] = {"signal": s, "rationale":"(selftest)","best_bull":"(略)","best_bear":"(略)",
                       "citations":([{"claim":f"{cid}-r{r}","number":"1","source":"demo","url":f"https://fixture-research.org/source/{cid}/{r}","date":"2026-06"}]
                                    if s != 0 else [])}
        judge = {"round": r, "crux_signals": cs, "new_cruxes": new}
        det = {"evidence_chain": [{"claim_node": "[Vision Node: selftest | Constraint: x]",
                                   "source": "demo, https://fixture-research.org/source, 2026"}]}
        inq = {"lethal_attack_vectors": [{"attack": "[Audit Attack | Target: selftest]",
                                           "evidence_audit": "demo"}]}
        res = cmd_submit(topic, det, inq, judge)
        print(f"R{r:<2} open→{res.get('open_cruxes','-')} | 研究状态={res['decision']:<22} "
              f"弱={res['binding_crux']}({int(res['support_weakest']*100)}/100) | {res['convergence']['decision']}")
        if res["status"] == "ready_for_report":
            break
        if res["status"] == "blocked_max_rounds":
            break
    rep = cmd_report(topic)
    print(f"\nREPORT status={rep['status']}")
    if rep["status"] == "report_data_ready":
        print(f"研究状态={rep['decision']} | binding={rep['binding_crux']} "
              f"({int(rep['support_weakest']*100)}/100) | 命题均值支持度={int(rep['support_mean']*100)}/100 "
              f"| 唯一来源={rep['n_unique_sources']}")
        md = rep["report_markdown"].splitlines()
        a0 = next(i for i, l in enumerate(md) if l.startswith("## A ·"))
        print("渲染的报告(A层账本节选):")
        for l in md[a0:a0 + 11]:
            print("  " + l)
    else:
        print(f"阻断正式报告: {rep.get('instruction')} unresolved={rep.get('unresolved_cruxes')}")
    os.remove(_path(topic))
    print("\n[selftest] 全链路 framing→scoped dispatch→judge→engine→report-gate 跑通。")


if __name__ == "__main__":
    main()
