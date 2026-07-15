#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trade Nothing v0.10 — Crux Orchestrator  (-deepthink2; parallel to deepthink_orchestrator.py)

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
  --screen TOPIC                       -> dispatch isolated Candidate Analyst + Skeptic on eligible seeds.
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
from datetime import date
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import crux_engine
import landscape_engine
import opportunity_engine
import candidate_screen_engine
import claim_verification_engine
import research_output
import run_registry
from utils import get_scratch_dir, get_output_dir, get_evolution_path, load_json_safe, save_json
try:
    from model_tiers import model_for
except Exception:
    def model_for(t): return "deep"

LEGACY_STATE_DIR = os.path.join(SCRIPT_DIR, ".state")


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
    issues.extend(landscape_engine.validate_frame(frame))
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


def _legacy_path(topic):
    return os.path.join(LEGACY_STATE_DIR, f"{_legacy_slug(topic)}_v2_state.json")

def _load(topic):
    p = _path(topic)
    if os.path.exists(p):
        return load_json_safe(p, default=None)
    old = _legacy_path(topic)
    if os.path.exists(old):
        state = load_json_safe(old, default=None)
        if state:
            state.setdefault("migration", {})["loaded_from_legacy_state"] = old
        return state
    return None

def _save(topic, state):
    state.setdefault("runtime", {})["state_path"] = _path(topic)
    if os.environ.get("TRADE_NOTHING_RUN_ID"):
        state["runtime"]["run_id"] = os.environ["TRADE_NOTHING_RUN_ID"]
    save_json(_path(topic), state)


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
    """Map structured agent evidence to crux ids; None means legacy payload."""
    det = detective if isinstance(detective, dict) else {}
    inq = inquisitor if isinstance(inquisitor, dict) else {}
    structured_present = "crux_evidence" in det or "crux_attacks" in inq
    if not structured_present:
        return None
    out = {}
    for group in det.get("crux_evidence", []):
        if not isinstance(group, dict) or not group.get("crux_id"):
            continue
        bucket = out.setdefault(group["crux_id"], set())
        for evidence in group.get("evidence", []):
            key = crux_engine.citation_identity(evidence)
            if key:
                bucket.add(key)
    for group in inq.get("crux_attacks", []):
        if not isinstance(group, dict) or not group.get("crux_id"):
            continue
        bucket = out.setdefault(group["crux_id"], set())
        for evidence in group.get("attacks", []):
            key = crux_engine.citation_identity(evidence)
            if key:
                bucket.add(key)
    return out


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
            allowed = evidence_by_crux.get(cid, set())
            accepted = [c for c in submitted if crux_engine.citation_identity(c) in allowed]
            if len(accepted) < len(submitted):
                flags.append(f"dropped_judge_invented_citations:{len(submitted) - len(accepted)}")
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
    ranked = sorted(
        open_ids,
        key=lambda cid: (
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


def _admit_new_cruxes(state, proposed, round_num, policy):
    admitted, deferred = [], []
    proposed = proposed if isinstance(proposed, list) else []
    for item in proposed:
        issues = _new_crux_issues(state, item)
        if not policy["new_cruxes_allowed"]:
            issues.append("new_crux_introduced_after_cutoff")
        cid = str(item.get("id", "")).strip() if isinstance(item, dict) else ""
        if cid in state.get("cruxes", {}):
            issues.append("new_crux_id_already_exists")
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

def frame_prompt(topic):
    return ("[HOST EXECUTION CONTRACT — MANDATORY]\n"
            "Execute the Framer inline in the current parent context. Do not call "
            "define_subagent, invoke_subagent, Task, delegate, context-fork, or any equivalent "
            "sub-agent mechanism. Do not browse or call tools during framing.\n"
            f"[Framer · framer.md] Topic: {topic}\n"
            "立题：输出 decision_question / question_type / logic_graph / horizon / as_of_date / "
            "unit_of_analysis / thesis_seed / premise_audit / 2–5 candidate_cruxes(每条带 "
            "logic_role、monitor_anchor、falsifier、catalyst_window) / "
            "forbidden_consensus / no_edge_precheck / suggested_max_rounds。机会型问题还必须输出 "
            "5–7 路 entity-agnostic landscape_map。严格按 framer.md 的 JSON 输出。"
            "只返回内联 JSON；禁止创建 Markdown、Google Drive、云文档或自选输出路径。")

def dispatch_prompts(state, round_num):
    policy = _round_policy(state, round_num)
    open_ids = policy["dispatch_cruxes"]
    landscape_plan = landscape_engine.ensure_round_plan(state, round_num)
    fc = state.get("forbidden_consensus", [])
    lines = []
    for cid in open_ids:
        cx = state["cruxes"][cid]
        catalyst = cx.get("catalyst_window", {})
        catalyst_text = (f"{catalyst.get('event', '—')} @ {catalyst.get('expected_by', '—')} "
                         f"[{catalyst.get('date_status', 'UNVERIFIED')}; "
                         f"basis={catalyst.get('basis_claim_id', '—')}]"
                         if isinstance(catalyst, dict) else str(catalyst or "—"))
        lines.append(f"- [{cid}] {cx['label']}: {cx.get('definition','')}\n"
                     f"    逻辑角色: {cx.get('logic_role', 'THESIS_HINGE')}\n"
                     f"    对方当前最强点(bear): {cx.get('best_bear') or '（暂无）'}\n"
                     f"    我方当前最强点(bull): {cx.get('best_bull') or '（暂无）'}\n"
                     f"    监控锚点: {cx.get('monitor_anchor','')}\n"
                     f"    反证条件: {cx.get('falsifier','')}\n"
                     f"    催化窗口: {catalyst_text}")
    scope = "\n".join(lines)
    resolved = [f"{cid}({state['cruxes'][cid]['label']})" for cid, cx in state["cruxes"].items()
                if cx["retired"] and cx["status"].startswith("RESOLVED")]
    # ── 退休 crux 上下文（不需重辩，但供产业链交叉引用）──
    retired_ctx = ""
    retired_cruxes = [(cid, cx) for cid, cx in state["cruxes"].items() if cx["retired"]]
    if retired_cruxes:
        rc_lines = [f"  - {cid}({cx['label']}): {cx['status']}, debate-support={int(cx['p_history'][-1]*100)}/100, "
                    f"bull={cx.get('best_bull') or '?'}, bear={cx.get('best_bear') or '?'}"
                    for cid, cx in retired_cruxes]
        retired_ctx = ("\n📋 已收敛 crux 上下文（不需重辩，但供产业链交叉引用）:\n"
                       + "\n".join(rc_lines))
    # ── 产业链检查：只服务当前 crux，不为制造篇幅而重复全链路 ──
    chain_directive = (
        "\n🔗 产业链检查（按需）:\n"
        "  1. 只追踪能改变当前 OPEN crux 的价值链节点，不重复已经登记的行业背景\n"
        "  2. 新发现必须带具体公司/项目/产能/招标/海关页面；没有增量就返回 null\n"
        "  3. 禁止为了满足新颖性强行制造新维度或晚期 crux"
    )
    opportunity_directive = (
        "\n💎 OpportunitySeed 收割（每个 agent 每轮最多 3 条，可为 0）:\n"
        "  1. 原命题若失败，继续找替代者、竞争者、瓶颈所有者、基础资产所有者、二阶受益者或做空候选\n"
        "  2. 必须写清 crux 结果→价值转移→候选经济暴露；只有主题名称不得提交\n"
        "  3. evidence 必须逐字复用本 agent 本轮同一 origin_crux 的结构化证据\n"
        "  4. 线索仅进入后续筛选队列，不得给收益率、目标价或仓位"
    )
    landscape_by_id = {
        item.get("path_id"): item
        for item in state.get("landscape_map", {}).get("paths", [])
        if isinstance(item, dict)
    }

    def landscape_directive(role):
        assigned = landscape_plan.get("assignments", {}).get(role, [])
        if not assigned:
            return "\n🗺 Landscape Map: 本轮无路径分配；输出 landscape_findings=[]。"
        packets = [landscape_by_id[path_id] for path_id in assigned if path_id in landscape_by_id]
        return (
            "\n🗺 Landscape Map 路径质证（硬分配，每轮最多 2 条）:\n"
            f"{json.dumps(packets, ensure_ascii=False)}\n"
            "  1. 每条分配路径恰好返回一个 landscape_findings 项；不得改 path_id 或 linked_crux_id\n"
            "  2. state 只能 SUPPORTED / REJECTED / UNKNOWN；非 UNKNOWN 必须逐字复用本角色"
            "同轮、linked_crux_id 下的结构化 evidence/attack\n"
            "  3. 两条 search_queries 是该路径的查询上限，不得扩写成实体名单后全网撒网\n"
            "  4. Landscape 是覆盖账本，不是推荐；不得以候选数量替代路径质证"
        )
    budget_directive = (
        "\n🧮 有界研究预算（硬上限）:\n"
        f"  1. 每个 agent 本轮最多 {min(10, 2 * max(1, len(open_ids)))} 次网页搜索，"
        "每条本轮 crux 最多 2 次\n"
        "  2. 每条 crux 最多保留 2 个一级来源 + 1 个补充来源\n"
        "  3. 连续 2 次搜索没有新增一级证据，立即返回 UNKNOWN/INSUFFICIENT_EVIDENCE\n"
        "  4. 禁止重复查询、重复域名和为了必须回答而换词无限搜索"
    )
    scope_directive = (
        f"\n🎯 本轮调度契约: free_roam_allowed={str(policy['free_roam_allowed']).lower()}, "
        f"new_cruxes_allowed={str(policy['new_cruxes_allowed']).lower()}, "
        f"new_crux_cutoff_round={policy['new_crux_cutoff_round']}。\n"
        f"本轮只处理 {policy['dispatch_cruxes']}；延后但仍 OPEN: "
        f"{policy['deferred_open_cruxes']}。\n"
        "未检验 crux 永远优先；若 free-roam 或新增 crux 被禁用，不得用旧 crux 或新主题替代当前任务。"
    )
    common = (f"决策问题: {state['decision_question']} | 视野: {state['horizon']} | as-of: "
              f"{state.get('frame_contract', {}).get('as_of_date', '—')}\n"
              f"分析单元: {state.get('frame_contract', {}).get('unit_of_analysis', '—')}\n"
              f"立题事实状态: {state.get('frame_contract', {}).get('quality_status', 'UNVERIFIED')}\n"
              "立题前提账本（HYPOTHESIS 不是事实，必须在辩论中验证）:\n"
              f"{json.dumps(state.get('frame_contract', {}).get('premise_audit', []), ensure_ascii=False)}\n"
              f"本轮重点质证以下 OPEN crux:\n{scope}\n"
              f"{retired_ctx}\n"
              f"历史负面先验（必须显式检查，不得机械照抄）:\n"
              f"{_compact_text(state.get('negative_priors','（无）'))}\n"
              f"平庸共识禁区(禁用): {fc}\n"
              f"{chain_directive}\n"
              f"{opportunity_directive}\n"
              f"{budget_directive}\n"
              f"{scope_directive}\n"
              "硬约束: 每个数据点必须带 来源+具体URL+日期；禁止主页级URL；"
              "不确定性必须明确表达；无来源数字必须省略或置 null；没有新维度时明确写 null。")
    det = (f"[Detective · detective.md · model={model_for('detective')}] Round {round_num}\n{common}\n"
           f"{landscape_directive('detective')}\n"
           "任务: 对每个 OPEN crux 用**带URL的硬数据**加固多头/反驳空头。\n"
           "额外要求: 输出中必须包含 supply_chain_map 字段描述本轮新发现的产业链节点。\n"
           "输出 detective.md 的 JSON。")
    free_roam_text = (
        f"⭐ FREE-ROAM(最多1个名额): 可对以下已收敛 crux 用新硬数据攻击: {resolved or '（暂无）'}。"
        if policy["free_roam_allowed"] else
        "⛔ 本轮 FREE-ROAM 禁用：存在从未质证 crux 或已临近轮次上限。"
    )
    new_crux_text = (
        "发现全新攻击面时，按 judge.md 完整 schema 提出。"
        if policy["new_cruxes_allowed"] else
        "本轮禁止新增 crux；将潜在线索留在叙事中，不得让其阻塞当前 run。"
    )
    inq = (f"[Inquisitor · inquisitor.md · model={model_for('inquisitor')}] Round {round_num}\n{common}\n"
           f"{landscape_directive('inquisitor')}\n"
           f"任务: 对每个 OPEN crux 发起带数据的致命攻击。{new_crux_text}\n"
           f"{free_roam_text}\n输出 inquisitor.md 的 JSON。")
    judge = (f"[Judge · judge.md · model={model_for('judge_scoring')}] Round {round_num}\n"
             f"读 Detective/Inquisitor 两份 JSON，对 OPEN crux {open_ids} 各打一个 signal∈[-1,1]+引用，"
             f"free-roam={policy['free_roam_allowed']}，new_cruxes={policy['new_cruxes_allowed']}。"
             "严格按 judge.md 的 JSON 输出。")
    return {"open_cruxes": policy["open_cruxes"], "dispatch_cruxes": open_ids,
            "round_policy": policy,
            "landscape_assignments": landscape_plan.get("assignments", {}),
            "detective_prompt": det, "inquisitor_prompt": inq, "judge_prompt": judge}


def candidate_screen_prompts(state, seeds, as_of_date):
    selection = candidate_screen_engine.selection_audit(seeds)
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
            "selection_audit": selection,
            "analyst_prompt": analyst, "skeptic_prompt": skeptic}


# ── commands ─────────────────────────────────────────────────────────────────
def cmd_frame(topic):
    return {"status": "need_framing", "topic": topic, "model": model_for("crux_extraction"),
            "execution_contract": {
                "dispatch_mode": "INLINE_PARENT",
                "subagent_dispatch_allowed": False,
                "tool_calls_allowed": False,
                "isolation_required": False,
                "stage_timeout_seconds": 120,
                "on_timeout": "call --runtime-failure --stage framing --reason '<brief reason>'",
            },
            "framer_prompt": frame_prompt(topic),
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

def cmd_init(topic, frame, runtime_isolation="unverified"):
    issues = _validate_frame(frame)
    if issues:
        return {
            "status": "frame_rejected",
            "topic": topic,
            "issues": issues,
            "artifact_policy": _frame_artifact_policy(),
            "instruction": "修正 framer JSON 后重新调用 --init；禁止绕过立题质量闸。",
        }
    pre = frame.get("no_edge_precheck", {})
    if pre and pre.get("is_researchable") is False:
        return {"status": "no_edge", "topic": topic, "reason": pre.get("reason", ""),
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
        "logic_graph": frame.get("logic_graph"),
        "as_of_date": frame.get("as_of_date", ""),
        "unit_of_analysis": frame.get("unit_of_analysis", ""),
        "premise_audit": frame.get("premise_audit", []),
        "no_edge_precheck": pre,
        "artifact_policy": _frame_artifact_policy(),
    }
    landscape = landscape_engine.initialize(frame)
    if landscape is not None:
        state["landscape_map"] = landscape
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
    out = {"status": "dispatch_subagents", "topic": topic, "round": 1, "thesis_seed": state["thesis_seed"]}
    out.update(dispatch_prompts(state, 1))
    _save(topic, state)
    return out

def cmd_submit(topic, detective, inquisitor, judge):
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在，请先 --init。"}
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
        state, judge.get("new_cruxes", []), round_num, policy
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
    signals = judge.get("crux_signals", {})
    conv = crux_engine.submit_round(state, round_num, signals)
    state["last_convergence"] = conv
    # ── 保存 agent 原始输出到 state，供报告层消费 ──
    state["rounds"][-1]["detective_raw"] = detective
    state["rounds"][-1]["inquisitor_raw"] = inquisitor
    state["rounds"][-1]["judge_raw"] = judge
    state["rounds"][-1]["landscape_audit"] = landscape_audit
    harvest = opportunity_engine.harvest_round(state, round_num, detective, inquisitor)
    state["rounds"][-1]["opportunity_harvest"] = harvest
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
            "round_policy": policy,
            "admitted_new_cruxes": admitted_new_cruxes,
            "deferred_new_cruxes": deferred_new_cruxes}
    if conv["decision"] == "converge":
        opportunity_question = state.get("question_type") in {"UNIVERSE_SEARCH", "COMPARATIVE"}
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
            "达到最大轮次但仍未收敛。正式报告继续阻断；保存 resolution_memo_markdown。"
            "只有用户显式授权后，才可按 continuation_packet 调用 --resume-blocked。"
        )
    else:
        base["status"] = "dispatch_subagents"
        base.update(dispatch_prompts(state, round_num + 1))
        _save(topic, state)
        base["instruction"] = (f"继续 (Round {round_num+1})，仅对 OPEN crux 派 Detective+Inquisitor，"
                               "再用 Judge 评分后调用 --submit。")
    return base


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
    prompts = candidate_screen_prompts(state, seeds, as_of_date)
    dispatch_id = "CSD-" + hashlib.sha256(
        f"{as_of_date}|{'|'.join(prompts['candidate_seed_ids'])}".encode("utf-8")
    ).hexdigest()[:10].upper()
    record = {
        "dispatch_id": dispatch_id,
        "as_of_date": as_of_date,
        "candidate_seed_ids": prompts["candidate_seed_ids"],
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
    history[:] = [
        item for item in history
        if not isinstance(item, dict) or item.get("dispatch_id") != dispatch_id
    ]
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
    return {
        "status": "dispatch_claim_verifier",
        "topic": topic,
        "model": model_for("claim_verifier"),
        "verifier_isolation_required": True,
        "claim_ids": [item["claim_id"] for item in packet["claims"]],
        "verifier_prompt": prompt,
        "missing_snapshot_claim_ids": packet["missing_snapshot_claim_ids"],
        "rejected_snapshots": packet["rejected_snapshots"],
        "instruction": "在独立上下文运行 Claim Verifier，再调用 --submit-verification。",
    }


def cmd_submit_verification(topic, snapshots, verifier, seed_id="", requested_claim_id="",
                            isolation_status="unverified"):
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在。"}
    audit = claim_verification_engine.apply_verifier_results(
        state, snapshots, verifier, seed_id or None, requested_claim_id or None,
        isolation_status=isolation_status,
    )
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

def cmd_report(topic, challenge_only=False, report_view="full", include_synthesis=False):
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在。"}
    conv = state.get("last_convergence", {})
    if conv.get("decision") != "converge":
        unresolved = [cid for cid, cx in state.get("cruxes", {}).items()
                      if cx.get("status") in ("PENDING", "OPEN")]
        resolution = cmd_resolution_memo(topic)
        return {"status": "blocked_unconverged", "topic": topic,
                "formal_report_allowed": False,
                "convergence": conv, "unresolved_cruxes": unresolved,
                "resolution_memo_markdown": resolution.get("resolution_memo_markdown"),
                "continuation_packet": resolution.get("continuation_packet"),
                "audit_state_path": _path(topic),
                "instruction": "正式报告已物理阻断；改为交付非正式 Resolution Memo。"}
    landscape = landscape_engine.summary(state)
    if landscape["required"] and not landscape["coverage_complete"]:
        return {
            "status": "blocked_landscape_coverage",
            "topic": topic,
            "formal_report_allowed": False,
            "unprobed_path_ids": [
                item["path_id"] for item in landscape["paths"]
                if item.get("state") == "UNPROBED"
            ],
            "instruction": "机会型研究仍有未质证路径；禁止正式报告或 EDGE 声明。",
        }
    rd = crux_engine.report_data(state)
    weak_evidence = [c["id"] for c in rd["cruxes"]
                     if len(c.get("unique_source_urls", [])) < crux_engine.MIN_VALID_CITATIONS]
    if weak_evidence:
        return {"status": "blocked_evidence_gate", "topic": topic,
                "cruxes_below_source_minimum": weak_evidence,
                "minimum_unique_sources_per_crux": crux_engine.MIN_VALID_CITATIONS,
                "instruction": "禁止生成正式报告：至少一条 crux 缺少两个独立、可复核的具体来源。"}
    opportunity_question = state.get("question_type") in {"UNIVERSE_SEARCH", "COMPARATIVE"}
    if opportunity_question and not challenge_only and not state.get("candidate_screens"):
        dispatch = cmd_screen(
            topic,
            state.get("frame_contract", {}).get("as_of_date", ""),
        )
        if dispatch.get("status") == "dispatch_candidate_screeners":
            dispatch.update({
                "formal_report_allowed": False,
                "formal_report_deferred": True,
                "report_deferred_reason": "default_candidate_screen_pending",
                "instruction": (
                    "机会型研究存在 READY_FOR_SCREENING 候选，正式报告默认延后。"
                    "隔离运行 Analyst/Skeptic 后调用 --submit-screen；"
                    "若用户只要求原命题质证，可显式重试 --report --challenge-only。"
                ),
            })
            return dispatch
    import report_v2
    opportunity_counts = opportunity_engine.summary(state)
    candidate_counts = candidate_screen_engine.summary(state)
    verification_counts = claim_verification_engine.summary(state)
    view_model = report_v2.build_report_view_model(state)
    out = {"status": "report_data_ready", "topic": topic,
            "decision": rd["decision"], "binding_crux": rd["binding_crux"],
            "focus_crux": rd["focus_crux"], "aggregation_rule": rd["aggregation_rule"],
            "research_verdict": rd["research_verdict"],
            "landscape_coverage": landscape,
            "support_weakest": rd["support_weakest"], "support_mean": rd["support_mean"],
            "n_unique_sources": rd["n_unique_sources"],
            "n_primary_sources": rd["n_primary_sources"],
            **opportunity_counts,
            **candidate_counts,
            **verification_counts,
            "model": model_for("battle_log_synthesis"),
            "report_view": report_view,
            "available_report_views": ["brief", "cards", "audit", "full"],
            "report_view_model": view_model,
            "report_markdown": report_v2.render(state, view=report_view),
            "audit_state_path": _path(topic),
            "instruction": (
                "默认正式报告已是可读确定性产物，不含 raw agent dump。"
                "父上下文优先消费 report_view_model 或 brief；"
                "不得读取 transcript、扩展候选或改变 engine 状态。"
            )}
    if include_synthesis:
        out["synthesis_packet"] = research_output.build_synthesis_packet(state)
        out["instruction"] += (
            " 已显式包含 synthesis_packet；它只允许增强叙事，不得改变状态词。"
        )
    return out


# ── CLI ──────────────────────────────────────────────────────────────────────
def _jload(s):
    if s and os.path.exists(s):
        s = open(s, encoding="utf-8").read()
    return json.loads(s) if s else {}

def main():
    ap = argparse.ArgumentParser(description="Trade Nothing v0.10 Crux Orchestrator")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--frame", action="store_true")
    g.add_argument("--init", action="store_true")
    g.add_argument("--submit", action="store_true")
    g.add_argument("--report", action="store_true")
    g.add_argument("--resolution-memo", action="store_true")
    g.add_argument("--resume-blocked", action="store_true")
    g.add_argument("--screen", action="store_true")
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
    ap.add_argument("--det", default=""); ap.add_argument("--inq", default=""); ap.add_argument("--judge", default="")
    ap.add_argument("--analyst", default=""); ap.add_argument("--skeptic", default="")
    ap.add_argument("--as-of", default=""); ap.add_argument("--seed-id", default="")
    ap.add_argument("--screen-isolation", default="unverified",
                    choices=["verified", "degraded", "unverified"])
    ap.add_argument("--runtime-isolation", default="unverified",
                    choices=["verified", "degraded", "unverified"])
    ap.add_argument("--isolation-receipt", default="")
    ap.add_argument("--snapshots", default=""); ap.add_argument("--verifier", default="")
    ap.add_argument("--claim-id", default="")
    ap.add_argument("--challenge-only", action="store_true",
                    help="render root-thesis report without default opportunity CandidateScreen")
    ap.add_argument("--report-view", default="full",
                    choices=["brief", "cards", "audit", "full"],
                    help="select one deterministic report view")
    ap.add_argument("--include-synthesis", action="store_true",
                    help="include optional compact synthesis input; off by default to save context")
    ap.add_argument("--extra-rounds", type=int, default=0)
    ap.add_argument("--stage", default="")
    ap.add_argument("--reason", default="")
    ap.add_argument("--verifier-isolation", default="unverified",
                    choices=["verified", "degraded", "unverified"])
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.create_run or a.adopt_run:
        try:
            manifest = (
                run_registry.adopt_manifest(a.topic, a.state_path)
                if a.adopt_run
                else run_registry.create_manifest(
                    a.topic, state_path=a.state_path,
                    runtime_isolation=a.runtime_isolation,
                )
            )
            out = {
                "status": "run_adopted" if a.adopt_run else "run_created",
                "topic": manifest["topic"],
                "run_id": manifest["run_id"],
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
    if a.frame:  out = cmd_frame(a.topic)
    elif a.init: out = cmd_init(a.topic, _jload(a.frame_json), a.runtime_isolation)
    elif a.submit: out = cmd_submit(a.topic, _jload(a.det), _jload(a.inq), _jload(a.judge))
    elif a.report: out = cmd_report(
        a.topic,
        challenge_only=a.challenge_only,
        report_view=a.report_view,
        include_synthesis=a.include_synthesis,
    )
    elif a.resolution_memo: out = cmd_resolution_memo(a.topic)
    elif a.resume_blocked: out = cmd_resume_blocked(a.topic, a.extra_rounds)
    elif a.screen: out = cmd_screen(a.topic, a.as_of, a.seed_id)
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
        a.verifier_isolation
    )
    elif a.runtime_failure: out = cmd_runtime_failure(a.topic, a.stage, a.reason)
    if context:
        out = run_registry.stage_envelope(out, context=context)
    print(json.dumps(out, ensure_ascii=False, indent=2))


# ── end-to-end wiring self-test: drive the full loop on real 绿色算力 signals ──
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
             "catalyst_window":{"event":"项目合同或费率披露", "expected_by":"2026-10-31",
                                "date_status":"REVIEW_CHECKPOINT", "basis_claim_id":"P1"}},
            {"id":"C2","label":"液冷/PFAS介质","logic_role":"THESIS_HINGE","definition":"冷却介质是否构成可兑现瓶颈",
             "monitor_anchor":"冷板式市占率、巨化/新宙邦氟化液产能", "falsifier":"替代介质快速规模化",
             "catalyst_window":{"event":"供应商产能与订单披露", "expected_by":"2026-11-30",
                                "date_status":"REVIEW_CHECKPOINT", "basis_claim_id":"P1"}},
            {"id":"C3","label":"WUE水资源红线","logic_role":"THESIS_HINGE","definition":"水资源约束是否改变技术选型",
             "monitor_anchor":"西部干冷器节点实测WUE、水预算配额", "falsifier":"审批与项目数据未体现水约束",
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
