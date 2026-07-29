#!/usr/bin/env python3
"""Frozen-corpus discovery benchmark with a bounded, logged retrieval gateway.

Research roles receive only a public dispatch and host-mediated search/read tools.
They never receive corpus paths, corpus bodies, evaluator labels, or answer keys.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import uuid
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath

from method_identity import build_method_identity_from_git


SUITE_SCHEMA = "trade-nothing.discovery-benchmark-suite.v1"
CORPUS_SCHEMA = "trade-nothing.frozen-corpus.v1"
DISPATCH_SCHEMA = "trade-nothing.discovery-dispatch.v1"
GATEWAY_STATE_SCHEMA = "trade-nothing.discovery-gateway-state.v1"
RETRIEVAL_RECEIPT_SCHEMA = "trade-nothing.discovery-retrieval-receipt.v1"
RESULT_SCHEMA = "trade-nothing.discovery-result.v1"
ASSESSMENT_SCHEMA = "trade-nothing.discovery-assessment.v2"
LEGACY_ASSESSMENT_SCHEMA = "trade-nothing.discovery-assessment.v1"
SUMMARY_SCHEMA = "trade-nothing.discovery-summary.v1"
ANSWER_KEY_SCHEMA = "trade-nothing.discovery-answer-key.v1"
EVALUATION_SCOPE = "FROZEN_CORPUS_DISCOVERY"
QUESTION_TYPES = {
    "CONJUNCTIVE", "DISJUNCTIVE", "CAUSAL_CHAIN", "COMPARATIVE", "UNIVERSE_SEARCH"
}
VARIANT_KINDS = {"PROMPT_ONLY", "GIT_METHOD_ADAPTER"}
STATUS_VALUES = {"COMPLETE", "FAILED", "PAUSED_BUDGET", "RUNTIME_FAILURE"}
LEAKAGE_KEYS = {
    "gold", "gold_answer", "expected_answer", "expected_outcome", "major_paths",
    "relevant_doc_ids", "false_opportunity_traps", "future_return", "post_as_of",
    "rubric", "assessment", "answer_key",
}
ASSESSOR_COUNT_METRICS = {
    "decisive_claim_total",
    "decisive_claim_correct",
    "false_source_count",
    "major_path_total",
    "major_path_found",
    "candidate_count",
    "effective_seed_count",
    "false_discovery_count",
    "novel_valid_path_count",
    "pricing_anchor_total",
    "pricing_anchor_valid",
    "maturity_misread_count",
    "comprehension_question_total",
    "comprehension_question_correct",
    "manual_edit_count",
}
EXPLORATION_COUNT_METRICS = {
    "insight_card_total",
    "insight_card_valid",
    "causal_path_total",
    "causal_path_valid",
    "exploration_trace_total",
    "exploration_trace_complete",
    "hypothesis_laundering_count",
    "formal_exploration_action_confusion_count",
}
ASSESSOR_COUNT_METRICS |= EXPLORATION_COUNT_METRICS


def _load_json(path):
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return value


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _hash_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_text(value, field):
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _sha256(value, field):
    text = _require_text(value, field).lower()
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise ValueError(f"{field} must be a 64-character sha256")
    return text


def _safe_path(value, field):
    text = _require_text(value, field)
    pure = PurePosixPath(text)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"{field} must remain inside its declared root")
    return text


def _iso_date(value, field):
    text = _require_text(value, field)
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be YYYY-MM-DD") from exc
    return text


def _positive_int(value, field):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _nonnegative_number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{field} must be non-negative")
    return value


def _walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).lower()
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def _validate_variants(variants, manifest):
    if not isinstance(variants, list) or len(variants) < 2:
        raise ValueError("variants must contain at least two comparison arms")
    variants = [_require_text(item, "variants[]") for item in variants]
    if len(set(variants)) != len(variants):
        raise ValueError("variants must be unique")
    if any(not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,31}", item) for item in variants):
        raise ValueError("variants have invalid format")
    if not isinstance(manifest, dict) or set(manifest) != set(variants):
        raise ValueError("variant_manifest keys must exactly match variants")
    normalized = {}
    for variant in variants:
        entry = manifest[variant]
        kind = _require_text(entry.get("runner_kind"), f"{variant}.runner_kind").upper()
        if kind not in VARIANT_KINDS:
            raise ValueError(f"unsupported runner kind: {kind}")
        engine = _require_text(entry.get("engine_version"), f"{variant}.engine_version")
        base = {
            "runner_kind": kind,
            "engine_version": engine,
            "adapter_instruction_path": _safe_path(
                entry.get("adapter_instruction_path"), f"{variant}.adapter_instruction_path"
            ),
            "adapter_instruction_sha256": _sha256(
                entry.get("adapter_instruction_sha256"),
                f"{variant}.adapter_instruction_sha256",
            ),
        }
        if kind == "PROMPT_ONLY":
            instruction_hash = _sha256(
                entry.get("instruction_sha256"), f"{variant}.instruction_sha256"
            )
            base.update({
                "instruction_path": _safe_path(
                    entry.get("instruction_path"), f"{variant}.instruction_path"
                ),
                "instruction_sha256": instruction_hash,
            })
            if engine != f"prompt:{instruction_hash}":
                raise ValueError(f"{variant}.engine_version must bind instruction hash")
        else:
            commit = _require_text(entry.get("git_commit"), f"{variant}.git_commit").lower()
            if not re.fullmatch(r"[0-9a-f]{40}", commit):
                raise ValueError(f"{variant}.git_commit must be a full git sha")
            base.update({
                "git_commit": commit,
                "method_instruction_path": _safe_path(
                    entry.get("method_instruction_path"),
                    f"{variant}.method_instruction_path",
                ),
                "method_instruction_sha256": _sha256(
                    entry.get("method_instruction_sha256"),
                    f"{variant}.method_instruction_sha256",
                ),
                "entrypoint_path": _safe_path(
                    entry.get("entrypoint_path"), f"{variant}.entrypoint_path"
                ),
                "entrypoint_sha256": _sha256(
                    entry.get("entrypoint_sha256"), f"{variant}.entrypoint_sha256"
                ),
                "orchestrator_path": _safe_path(
                    entry.get("orchestrator_path"), f"{variant}.orchestrator_path"
                ),
                "orchestrator_sha256": _sha256(
                    entry.get("orchestrator_sha256"), f"{variant}.orchestrator_sha256"
                ),
            })
            if entry.get("method_contract_sha256") is not None:
                base["method_contract_sha256"] = _sha256(
                    entry.get("method_contract_sha256"),
                    f"{variant}.method_contract_sha256",
                )
            if engine != f"git:{commit}":
                raise ValueError(f"{variant}.engine_version must bind git commit")
        base["variant_contract_sha256"] = _hash_bytes(_json(base).encode("utf-8"))
        normalized[variant] = base
    return variants, normalized


def validate_suite(suite, suite_path):
    if suite.get("schema_version") != SUITE_SCHEMA:
        raise ValueError(f"schema_version must be {SUITE_SCHEMA}")
    suite_id = _require_text(suite.get("suite_id"), "suite_id")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,63}", suite_id):
        raise ValueError("suite_id has invalid format")
    if suite.get("evaluation_scope") != EVALUATION_SCOPE:
        raise ValueError(f"evaluation_scope must be {EVALUATION_SCOPE}")
    access = suite.get("research_access")
    if access != {
        "external_search_allowed": False,
        "filesystem_allowed": False,
        "corpus_gateway_required": True,
    }:
        raise ValueError("discovery research access must be gateway-only")
    variants, variant_manifest = _validate_variants(
        suite.get("variants"), suite.get("variant_manifest")
    )
    candidate_variant = str(suite.get("candidate_variant") or "").strip()
    if candidate_variant and candidate_variant not in variants:
        raise ValueError("candidate_variant must name one declared variant")
    root = Path(suite_path).resolve().parent
    for variant, entry in variant_manifest.items():
        paths = [("adapter_instruction_path", "adapter_instruction_sha256")]
        if entry["runner_kind"] == "PROMPT_ONLY":
            paths.append(("instruction_path", "instruction_sha256"))
        else:
            paths.append(("method_instruction_path", "method_instruction_sha256"))
        for path_field, hash_field in paths:
            path = (root / entry[path_field]).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError(f"variant instruction is missing or escapes suite: {variant}")
            if _hash_file(path) != entry[hash_field]:
                raise ValueError(f"variant instruction hash mismatch: {variant}")
    corpus_manifest = suite.get("corpus_manifest")
    if not isinstance(corpus_manifest, dict):
        raise ValueError("corpus_manifest is required")
    corpus_path_value = _safe_path(corpus_manifest.get("path"), "corpus_manifest.path")
    corpus_hash = _sha256(corpus_manifest.get("sha256"), "corpus_manifest.sha256")
    document_count = _positive_int(
        corpus_manifest.get("document_count"), "corpus_manifest.document_count"
    )
    corpus_path = (root / corpus_path_value).resolve()
    if not corpus_path.is_relative_to(root) or not corpus_path.is_file():
        raise ValueError("frozen corpus is missing or escapes suite")
    if _hash_file(corpus_path) != corpus_hash:
        raise ValueError("frozen corpus hash mismatch")
    corpus = _load_json(corpus_path)
    if corpus.get("schema_version") != CORPUS_SCHEMA:
        raise ValueError(f"corpus schema_version must be {CORPUS_SCHEMA}")
    corpus_id = _require_text(corpus.get("corpus_id"), "corpus.corpus_id")
    documents = corpus.get("documents")
    if not isinstance(documents, list) or len(documents) != document_count:
        raise ValueError("corpus document_count does not match documents")
    doc_ids = set()
    normalized_documents = []
    for index, document in enumerate(documents):
        if not isinstance(document, dict):
            raise ValueError(f"documents[{index}] must be an object")
        leaked = sorted(LEAKAGE_KEYS.intersection(_walk_keys(document)))
        if leaked:
            raise ValueError(f"documents[{index}] leaks evaluator keys: {', '.join(leaked)}")
        doc_id = _require_text(document.get("doc_id"), f"documents[{index}].doc_id")
        if not re.fullmatch(r"DOC-[A-Z0-9-]{3,80}", doc_id) or doc_id in doc_ids:
            raise ValueError(f"invalid or duplicate doc_id: {doc_id}")
        doc_ids.add(doc_id)
        normalized_documents.append({
            "doc_id": doc_id,
            "date": _iso_date(document.get("date"), f"documents[{index}].date"),
            "publisher": _require_text(document.get("publisher"), f"documents[{index}].publisher"),
            "title": _require_text(document.get("title"), f"documents[{index}].title"),
            "url": _require_text(document.get("url"), f"documents[{index}].url"),
            "body": _require_text(document.get("body"), f"documents[{index}].body"),
        })
    cases = suite.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be non-empty")
    case_ids = set()
    normalized_cases = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"cases[{index}] must be an object")
        leaked = sorted(LEAKAGE_KEYS.intersection(_walk_keys(case)))
        if leaked:
            raise ValueError(f"cases[{index}] leaks evaluator keys: {', '.join(leaked)}")
        case_id = _require_text(case.get("case_id"), f"cases[{index}].case_id")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,63}", case_id) or case_id in case_ids:
            raise ValueError(f"invalid or duplicate case_id: {case_id}")
        case_ids.add(case_id)
        if case.get("corpus_id") != corpus_id:
            raise ValueError(f"cases[{index}].corpus_id does not match corpus")
        question_type = _require_text(
            case.get("question_type"), f"cases[{index}].question_type"
        ).upper()
        if question_type not in QUESTION_TYPES:
            raise ValueError(f"cases[{index}].question_type is unsupported")
        budget = case.get("budget")
        if not isinstance(budget, dict):
            raise ValueError(f"cases[{index}].budget is required")
        normalized_cases.append({
            **case,
            "case_id": case_id,
            "question_type": question_type,
            "as_of": _iso_date(case.get("as_of"), f"cases[{index}].as_of"),
            "prompt": _require_text(case.get("prompt"), f"cases[{index}].prompt"),
            "budget": {
                "max_tokens": _positive_int(budget.get("max_tokens"), "budget.max_tokens"),
                "max_queries": _positive_int(budget.get("max_queries"), "budget.max_queries"),
                "max_documents_read": _positive_int(
                    budget.get("max_documents_read"), "budget.max_documents_read"
                ),
                "max_wall_seconds": _positive_int(
                    budget.get("max_wall_seconds"), "budget.max_wall_seconds"
                ),
            },
        })
    contract = {
        "schema_version": SUITE_SCHEMA,
        "suite_id": suite_id,
        "evaluation_scope": EVALUATION_SCOPE,
        "research_access": access,
        "variants": variants,
        "variant_manifest": variant_manifest,
        "corpus_manifest": {
            "corpus_id": corpus_id,
            "path": corpus_path_value,
            "sha256": corpus_hash,
            "document_count": document_count,
        },
        "cases": normalized_cases,
    }
    if candidate_variant:
        contract["candidate_variant"] = candidate_variant
    return {
        **contract,
        "candidate_variant": candidate_variant or None,
        "suite_contract_sha256": _hash_bytes(_json(contract).encode("utf-8")),
        "corpus_path": str(corpus_path),
        "documents": normalized_documents,
    }


def verify_git_variants(suite, source_repo):
    repo = Path(source_repo).resolve()
    verified = []
    for variant, entry in suite["variant_manifest"].items():
        if entry["runner_kind"] != "GIT_METHOD_ADAPTER":
            continue
        for path_field, hash_field in (
            ("entrypoint_path", "entrypoint_sha256"),
            ("orchestrator_path", "orchestrator_sha256"),
        ):
            completed = subprocess.run(
                ["git", "-C", str(repo), "show", f"{entry['git_commit']}:{entry[path_field]}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if completed.returncode != 0:
                raise ValueError(f"cannot read pinned variant {variant}:{entry[path_field]}")
            if _hash_bytes(completed.stdout) != entry[hash_field]:
                raise ValueError(f"pinned variant file hash mismatch: {variant}")
        if entry.get("method_contract_sha256") is not None:
            actual_identity = build_method_identity_from_git(repo, entry["git_commit"])
            if actual_identity["contract_sha256"] != entry["method_contract_sha256"]:
                raise ValueError(f"pinned variant method identity mismatch: {variant}")
        verified.append(variant)
    return verified


def initialize_run(suite, suite_path, case_id, variant, output_dir):
    selected = [case for case in suite["cases"] if case["case_id"] == case_id]
    if not selected:
        raise ValueError(f"unknown case_id: {case_id}")
    if variant not in suite["variant_manifest"]:
        raise ValueError(f"unknown variant: {variant}")
    suite_root = Path(suite_path).resolve().parent
    output = Path(output_dir).resolve()
    if output.is_relative_to(suite_root):
        raise ValueError("run output must be outside the suite directory")
    if output.exists():
        raise ValueError("run output already exists")
    output.mkdir(parents=False)
    case = selected[0]
    variant_contract = suite["variant_manifest"][variant]
    session_id = "DISC-" + uuid.uuid4().hex.upper()
    root = Path(suite_path).resolve().parent
    method_instruction = None
    if variant_contract["runner_kind"] == "PROMPT_ONLY":
        method_instruction = (root / variant_contract["instruction_path"]).read_text(
            encoding="utf-8"
        )
    else:
        method_instruction = (
            root / variant_contract["method_instruction_path"]
        ).read_text(encoding="utf-8")
    adapter_instruction = (
        root / variant_contract["adapter_instruction_path"]
    ).read_text(encoding="utf-8")
    dispatch = {
        "schema_version": DISPATCH_SCHEMA,
        "suite_id": suite["suite_id"],
        "evaluation_scope": EVALUATION_SCOPE,
        "suite_contract_sha256": suite["suite_contract_sha256"],
        "session_id": session_id,
        "variant": variant,
        "variant_contract": variant_contract,
        "method_instruction": method_instruction,
        "corpus_adapter_instruction": adapter_instruction,
        "case": case,
        "tool_contract": {
            "corpus_search": {
                "arguments": {"query": "non-empty text", "limit": "1..5"},
                "returns": "ranked metadata and snippets, never full bodies",
            },
            "corpus_read": {
                "arguments": {"doc_id": "an id previously returned by corpus_search"},
                "returns": "one frozen as-of document",
            },
        },
        "research_constraints": {
            "allowed_inputs": "this dispatch plus host-mediated corpus_search/corpus_read only",
            "external_search_allowed": False,
            "filesystem_allowed": False,
            "future_information": "forbidden",
            "self_assessment": "forbidden",
        },
    }
    leaked = sorted(LEAKAGE_KEYS.intersection(_walk_keys(dispatch)))
    if leaked:
        raise ValueError("public dispatch leaks evaluator keys: " + ", ".join(leaked))
    state = {
        "schema_version": GATEWAY_STATE_SCHEMA,
        "session_id": session_id,
        "suite_path": str(Path(suite_path).resolve()),
        "suite_contract_sha256": suite["suite_contract_sha256"],
        "case_id": case_id,
        "variant": variant,
        "as_of": case["as_of"],
        "budget": case["budget"],
        "query_count": 0,
        "event_count": 0,
        "read_doc_ids": [],
        "accessible_doc_ids": [],
        "finalized": False,
        "started_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }
    (output / "dispatch.json").write_text(
        json.dumps(dispatch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_state(output, state)
    (output / "retrieval.jsonl").touch(exist_ok=False)
    return dispatch


def _write_state(run_dir, state):
    target = Path(run_dir) / "gateway-state.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def _load_run(run_dir):
    root = Path(run_dir).resolve()
    state = _load_json(root / "gateway-state.json")
    if state.get("schema_version") != GATEWAY_STATE_SCHEMA:
        raise ValueError("invalid gateway state schema")
    suite = validate_suite(_load_json(state["suite_path"]), state["suite_path"])
    if suite["suite_contract_sha256"] != state["suite_contract_sha256"]:
        raise ValueError("gateway state is not bound to current suite")
    case = next(case for case in suite["cases"] if case["case_id"] == state["case_id"])
    if case["as_of"] != state["as_of"] or case["budget"] != state["budget"]:
        raise ValueError("gateway state case contract drifted")
    if not isinstance(state.get("event_count"), int) or state["event_count"] < 0:
        raise ValueError("gateway state event_count is invalid")
    if not isinstance(state.get("finalized"), bool):
        raise ValueError("gateway state finalized flag is invalid")
    return root, state, suite


def _tokens(text):
    return re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", str(text).lower())


def _search_score(query_tokens, document, document_frequency, corpus_size):
    title_tokens = Counter(_tokens(document["title"]))
    body_tokens = Counter(_tokens(document["body"] + " " + document["publisher"]))
    score = 0.0
    for token in set(query_tokens):
        tf = body_tokens[token] + title_tokens[token] * 3
        if not tf:
            continue
        inverse = math.log((corpus_size + 1) / (document_frequency[token] + 1)) + 1
        score += (1 + math.log(tf)) * inverse
    return score


def _append_log(root, event):
    path = root / "retrieval.jsonl"
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(_json(event) + "\n")


def _require_mutable_session(root, state):
    if state["finalized"] or (root / "retrieval-receipt.json").exists():
        raise ValueError("retrieval session is finalized")


def search(run_dir, query, limit=5):
    root, state, suite = _load_run(run_dir)
    _require_mutable_session(root, state)
    query = _require_text(query, "query")
    limit = _positive_int(limit, "limit")
    if limit > 5:
        raise ValueError("limit cannot exceed 5")
    if state["query_count"] >= state["budget"]["max_queries"]:
        raise ValueError("query budget exhausted")
    query_tokens = _tokens(query)
    if not query_tokens:
        raise ValueError("query must contain searchable terms")
    available = [doc for doc in suite["documents"] if doc["date"] <= state["as_of"]]
    frequency = Counter()
    for document in available:
        for token in set(_tokens(document["title"] + " " + document["body"] + " " + document["publisher"])):
            frequency[token] += 1
    ranked = []
    for document in available:
        score = _search_score(query_tokens, document, frequency, len(available))
        if score > 0:
            ranked.append((score, document))
    ranked.sort(key=lambda item: (-item[0], item[1]["date"], item[1]["doc_id"]))
    results = []
    for score, document in ranked[:limit]:
        results.append({
            "doc_id": document["doc_id"],
            "date": document["date"],
            "publisher": document["publisher"],
            "title": document["title"],
            "snippet": document["body"][:280],
            "score": round(score, 6),
        })
    state["query_count"] += 1
    state["event_count"] += 1
    state["accessible_doc_ids"] = sorted(
        set(state["accessible_doc_ids"]) | {item["doc_id"] for item in results}
    )
    _write_state(root, state)
    _append_log(root, {
        "seq": state["event_count"],
        "event": "SEARCH",
        "query": query,
        "limit": limit,
        "returned_doc_ids": [item["doc_id"] for item in results],
    })
    return {"session_id": state["session_id"], "query_count": state["query_count"], "results": results}


def read_document(run_dir, doc_id):
    root, state, suite = _load_run(run_dir)
    _require_mutable_session(root, state)
    doc_id = _require_text(doc_id, "doc_id")
    if doc_id not in state["accessible_doc_ids"]:
        raise ValueError("document must first be returned by corpus_search")
    if doc_id not in state["read_doc_ids"] and len(state["read_doc_ids"]) >= state["budget"]["max_documents_read"]:
        raise ValueError("document-read budget exhausted")
    document = next((doc for doc in suite["documents"] if doc["doc_id"] == doc_id), None)
    if document is None or document["date"] > state["as_of"]:
        raise ValueError("document is unavailable for this as-of case")
    if doc_id not in state["read_doc_ids"]:
        state["read_doc_ids"].append(doc_id)
        state["read_doc_ids"].sort()
    state["event_count"] += 1
    _write_state(root, state)
    _append_log(root, {
        "seq": state["event_count"],
        "event": "READ",
        "doc_id": doc_id,
    })
    return {"session_id": state["session_id"], "document": document}


def finalize_retrieval(run_dir):
    root, state, suite = _load_run(run_dir)
    log_path = root / "retrieval.jsonl"
    path = root / "retrieval-receipt.json"
    if state["finalized"]:
        if not path.is_file():
            raise ValueError("finalized retrieval session is missing its receipt")
        return _load_json(path)
    receipt = {
        "schema_version": RETRIEVAL_RECEIPT_SCHEMA,
        "session_id": state["session_id"],
        "suite_contract_sha256": suite["suite_contract_sha256"],
        "corpus_sha256": suite["corpus_manifest"]["sha256"],
        "case_id": state["case_id"],
        "variant": state["variant"],
        "as_of": state["as_of"],
        "query_count": state["query_count"],
        "event_count": state["event_count"],
        "read_doc_ids": state["read_doc_ids"],
        "distinct_documents_read": len(state["read_doc_ids"]),
        "retrieval_log_sha256": _hash_file(log_path),
        "within_gateway_budget": (
            state["query_count"] <= state["budget"]["max_queries"]
            and len(state["read_doc_ids"]) <= state["budget"]["max_documents_read"]
        ),
    }
    if path.exists():
        existing = _load_json(path)
        if existing != receipt:
            raise ValueError("retrieval receipt exists with different content")
    else:
        path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state["finalized"] = True
    _write_state(root, state)
    return receipt


def _variant_receipt_expected(contract):
    expected = {
        "runner_kind": contract["runner_kind"],
        "engine_version": contract["engine_version"],
        "variant_contract_sha256": contract["variant_contract_sha256"],
        "adapter_instruction_sha256": contract["adapter_instruction_sha256"],
    }
    if contract["runner_kind"] == "PROMPT_ONLY":
        expected["instruction_sha256"] = contract["instruction_sha256"]
    else:
        expected.update({
            "git_commit": contract["git_commit"],
            "method_instruction_sha256": contract["method_instruction_sha256"],
            "entrypoint_sha256": contract["entrypoint_sha256"],
            "orchestrator_sha256": contract["orchestrator_sha256"],
        })
        if contract.get("method_contract_sha256") is not None:
            expected["method_contract_sha256"] = contract["method_contract_sha256"]
    return expected


def _validate_result(result, case, suite, results_root):
    if result.get("schema_version") != RESULT_SCHEMA:
        raise ValueError(f"result schema_version must be {RESULT_SCHEMA}")
    variant = _require_text(result.get("variant"), "result.variant")
    if result.get("case_id") != case["case_id"] or variant not in suite["variants"]:
        raise ValueError("result case/variant does not match suite")
    if result.get("suite_contract_sha256") != suite["suite_contract_sha256"]:
        raise ValueError("result is not bound to suite contract")
    contract = suite["variant_manifest"][variant]
    if result.get("variant_contract_sha256") != contract["variant_contract_sha256"]:
        raise ValueError("result is not bound to variant contract")
    if result.get("engine_version") != contract["engine_version"]:
        raise ValueError("result engine_version does not match variant")
    engine_receipt = result.get("engine_receipt")
    if not isinstance(engine_receipt, dict) or engine_receipt.get("verified_by_host") is not True:
        raise ValueError("engine_receipt must be host verified")
    _require_text(engine_receipt.get("host_invocation_id"), "host_invocation_id")
    for field, expected in _variant_receipt_expected(contract).items():
        if engine_receipt.get(field) != expected:
            raise ValueError(f"engine_receipt.{field} does not match variant")
    status = _require_text(result.get("completion_status"), "completion_status").upper()
    if status not in STATUS_VALUES:
        raise ValueError("invalid completion_status")
    if "assessment" in result:
        raise ValueError("result cannot score itself")
    paths = {}
    for field in ("artifact_path", "retrieval_receipt_path", "retrieval_log_path"):
        path = (results_root / _safe_path(result.get(field), f"result.{field}")).resolve()
        if not path.is_relative_to(results_root) or not path.is_file():
            raise ValueError(f"result.{field} is missing or escapes results root")
        paths[field] = path
    if _hash_file(paths["artifact_path"]) != _sha256(result.get("artifact_sha256"), "artifact_sha256"):
        raise ValueError("artifact hash mismatch")
    receipt = _load_json(paths["retrieval_receipt_path"])
    if receipt.get("schema_version") != RETRIEVAL_RECEIPT_SCHEMA:
        raise ValueError("invalid retrieval receipt")
    if _hash_file(paths["retrieval_receipt_path"]) != _sha256(
        result.get("retrieval_receipt_sha256"), "retrieval_receipt_sha256"
    ):
        raise ValueError("retrieval receipt hash mismatch")
    if _hash_file(paths["retrieval_log_path"]) != receipt.get("retrieval_log_sha256"):
        raise ValueError("retrieval log hash mismatch")
    expected = {
        "suite_contract_sha256": suite["suite_contract_sha256"],
        "corpus_sha256": suite["corpus_manifest"]["sha256"],
        "case_id": case["case_id"],
        "variant": variant,
        "as_of": case["as_of"],
    }
    for field, value in expected.items():
        if receipt.get(field) != value:
            raise ValueError(f"retrieval receipt {field} mismatch")
    usage = result.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("result.usage is required")
    usage = {
        "tokens_total": _nonnegative_number(usage.get("tokens_total"), "tokens_total"),
        "wall_seconds": _nonnegative_number(usage.get("wall_seconds"), "wall_seconds"),
    }
    within_budget = (
        usage["tokens_total"] <= case["budget"]["max_tokens"]
        and usage["wall_seconds"] <= case["budget"]["max_wall_seconds"]
        and receipt.get("within_gateway_budget") is True
    )
    return {**result, "variant": variant, "completion_status": status, "usage": usage,
            "receipt": receipt, "within_budget": within_budget}


def _validate_assessment(assessment, result):
    assessment_schema = assessment.get("schema_version")
    if assessment_schema not in {
        ASSESSMENT_SCHEMA, LEGACY_ASSESSMENT_SCHEMA
    }:
        raise ValueError(
            "assessment schema_version must be "
            f"{ASSESSMENT_SCHEMA} or {LEGACY_ASSESSMENT_SCHEMA}"
        )
    if assessment.get("case_id") != result["case_id"] or assessment.get("variant") != result["variant"]:
        raise ValueError("assessment case/variant mismatch")
    if assessment.get("blind") is not True:
        raise ValueError("assessment must be blind")
    _require_text(assessment.get("assessor_id"), "assessor_id")
    if assessment.get("artifact_sha256") != result["artifact_sha256"]:
        raise ValueError("assessment does not bind exact artifact")
    metrics = assessment.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("assessment.metrics is required")
    exploration_metrics_assessed = (
        assessment_schema == ASSESSMENT_SCHEMA
        and EXPLORATION_COUNT_METRICS.issubset(metrics)
    )
    normalized = {
        field: int(_nonnegative_number(
            metrics.get(
                field,
                0
                if (
                    assessment_schema == LEGACY_ASSESSMENT_SCHEMA
                    and field in EXPLORATION_COUNT_METRICS
                )
                else None,
            ),
            f"metrics.{field}",
        ))
        for field in ASSESSOR_COUNT_METRICS
    }
    for numerator, denominator in (
        ("decisive_claim_correct", "decisive_claim_total"),
        ("major_path_found", "major_path_total"),
        ("insight_card_valid", "insight_card_total"),
        ("causal_path_valid", "causal_path_total"),
        ("exploration_trace_complete", "exploration_trace_total"),
        ("effective_seed_count", "candidate_count"),
        ("false_discovery_count", "candidate_count"),
        ("pricing_anchor_valid", "pricing_anchor_total"),
        ("comprehension_question_correct", "comprehension_question_total"),
    ):
        if normalized[numerator] > normalized[denominator]:
            raise ValueError(f"{numerator} cannot exceed {denominator}")
    return {
        "metrics": normalized,
        "exploration_metrics_assessed": exploration_metrics_assessed,
    }


def _ratio(numerator, denominator):
    return round(numerator / denominator, 6) if denominator else None


def score_suite(suite, answer_key, results_dir):
    if answer_key.get("schema_version") != ANSWER_KEY_SCHEMA:
        raise ValueError(f"answer key schema must be {ANSWER_KEY_SCHEMA}")
    if answer_key.get("suite_id") != suite["suite_id"]:
        raise ValueError("answer key suite mismatch")
    keyed_cases = answer_key.get("cases")
    if not isinstance(keyed_cases, dict) or set(keyed_cases) != {case["case_id"] for case in suite["cases"]}:
        raise ValueError("answer key cases must exactly match suite")
    root = Path(results_dir).resolve()
    rows, errors = [], []
    doc_ids = {doc["doc_id"] for doc in suite["documents"]}
    for case in suite["cases"]:
        keyed_case = keyed_cases[case["case_id"]]
        if not isinstance(keyed_case, dict):
            raise ValueError(f"invalid answer key for {case['case_id']}")
        questions = keyed_case.get("comprehension_questions")
        if not isinstance(questions, list) or len(questions) != 3 or any(
            not str(question).strip() for question in questions
        ):
            raise ValueError(f"exactly three comprehension questions are required for {case['case_id']}")
        relevant = set(keyed_case.get("relevant_doc_ids") or [])
        if not relevant or not relevant.issubset(doc_ids):
            raise ValueError(f"invalid relevant_doc_ids for {case['case_id']}")
        for variant in suite["variants"]:
            stem = f"{case['case_id']}__{variant}"
            try:
                result = _validate_result(
                    _load_json(root / f"{stem}.result.json"), case, suite, root
                )
                assessment = _validate_assessment(
                    _load_json(root / f"{stem}.assessment.json"), result
                )
                metrics = assessment["metrics"]
                read_ids = set(result["receipt"]["read_doc_ids"])
                row = {
                    "case_id": case["case_id"],
                    "variant": variant,
                    "completion_status": result["completion_status"],
                    "within_budget": result["within_budget"],
                    "usage": result["usage"],
                    "query_count": result["receipt"]["query_count"],
                    "documents_read": len(read_ids),
                    "relevant_source_total": len(relevant),
                    "relevant_source_read": len(read_ids & relevant),
                    "metrics": metrics,
                    "exploration_metrics_assessed": assessment[
                        "exploration_metrics_assessed"
                    ],
                }
                row["comparable"] = result["completion_status"] == "COMPLETE" and result["within_budget"]
                rows.append(row)
                if not row["comparable"]:
                    errors.append(f"{stem}: incomplete or over budget")
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                errors.append(f"{stem}: {exc}")
    aggregates = {}
    for variant in suite["variants"]:
        selected = [row for row in rows if row["variant"] == variant]
        totals = defaultdict(int)
        for row in selected:
            for field, value in row["metrics"].items():
                totals[field] += value
            totals["tokens_total"] += row["usage"]["tokens_total"]
            totals["wall_seconds"] += row["usage"]["wall_seconds"]
            totals["query_count"] += row["query_count"]
            totals["documents_read"] += row["documents_read"]
            totals["relevant_source_total"] += row["relevant_source_total"]
            totals["relevant_source_read"] += row["relevant_source_read"]
        effective = totals["effective_seed_count"]
        aggregates[variant] = {
            "case_count": len(selected),
            "comparable_count": sum(row["comparable"] for row in selected),
            "source_recall": _ratio(totals["relevant_source_read"], totals["relevant_source_total"]),
            "retrieval_precision": _ratio(totals["relevant_source_read"], totals["documents_read"]),
            "major_path_coverage": _ratio(totals["major_path_found"], totals["major_path_total"]),
            "insight_card_valid_rate": _ratio(
                totals["insight_card_valid"], totals["insight_card_total"]
            ),
            "causal_path_valid_rate": _ratio(
                totals["causal_path_valid"], totals["causal_path_total"]
            ),
            "exploration_trace_complete_rate": _ratio(
                totals["exploration_trace_complete"],
                totals["exploration_trace_total"],
            ),
            "hypothesis_laundering_count": totals[
                "hypothesis_laundering_count"
            ],
            "formal_exploration_action_confusion_count": totals[
                "formal_exploration_action_confusion_count"
            ],
            "exploration_assessed_count": sum(
                row["exploration_metrics_assessed"] for row in selected
            ),
            "safety_gate_pass": (
                len(selected) == len(suite["cases"])
                and all(
                    row["exploration_metrics_assessed"] for row in selected
                )
                and totals["hypothesis_laundering_count"] == 0
                and totals[
                    "formal_exploration_action_confusion_count"
                ] == 0
            ),
            "false_discovery_rate": _ratio(totals["false_discovery_count"], totals["candidate_count"]),
            "pricing_anchor_valid_rate": _ratio(totals["pricing_anchor_valid"], totals["pricing_anchor_total"]),
            "tokens_per_effective_seed": _ratio(totals["tokens_total"], effective),
            "totals": dict(sorted(totals.items())),
        }
    expected = len(suite["cases"]) * len(suite["variants"])
    exploration_assessment_complete = (
        len(rows) == expected
        and all(row["exploration_metrics_assessed"] for row in rows)
    )
    comparison_ready = (
        not errors
        and len(rows) == expected
        and all(row["comparable"] for row in rows)
        and exploration_assessment_complete
    )
    candidate_variant = suite.get("candidate_variant")
    method_change_gate_pass = (
        aggregates[candidate_variant]["safety_gate_pass"]
        if candidate_variant else None
    )
    method_change_gate_ready = (
        comparison_ready
        and bool(candidate_variant)
        and method_change_gate_pass is True
    )
    return {
        "schema_version": SUMMARY_SCHEMA,
        "suite_id": suite["suite_id"],
        "evaluation_scope": EVALUATION_SCOPE,
        "expected_case_variant_pairs": expected,
        "observed_case_variant_pairs": len(rows),
        "comparison_ready": comparison_ready,
        "candidate_variant": candidate_variant,
        "method_change_gate_pass": method_change_gate_pass,
        "method_change_gate_ready": method_change_gate_ready,
        "errors": errors,
        "rows": rows,
        "aggregates": aggregates,
    }


def _method_change_cli_outcome(summary):
    if not summary.get("comparison_ready"):
        return "BLOCKED_COMPARISON", 2
    if not summary.get("candidate_variant"):
        return "COMPARISON_READY_NOT_GATED", 3
    if not summary.get("method_change_gate_ready"):
        return "BLOCKED_METHOD_CHANGE", 4
    return "METHOD_CHANGE_READY", 0


def render_markdown(summary):
    lines = [
        f"# Discovery Benchmark Summary — {summary['suite_id']}", "",
        f"- Scope: **{summary['evaluation_scope']}**",
        f"- Comparison ready: **{str(summary['comparison_ready']).upper()}**",
        f"- Candidate method: **{summary.get('candidate_variant') or 'NOT_DECLARED'}**",
        f"- Candidate exploration safety gate: "
        f"**{str(summary.get('method_change_gate_pass')).upper()}**",
        f"- Method-change ready: "
        f"**{str(summary.get('method_change_gate_ready', False)).upper()}**",
        "- This pilot measures bounded retrieval and opportunity-path construction inside one frozen corpus; it does not prove live-web universe recall or alpha.",
        "",
        "| Variant | Source recall | Retrieval precision | Path coverage | False discovery | Pricing valid | Tokens / effective seed |",
        "|:---|---:|---:|---:|---:|---:|---:|",
    ]
    pct = lambda value: "—" if value is None else f"{value * 100:.1f}%"
    for variant, item in summary["aggregates"].items():
        tokens = item["tokens_per_effective_seed"]
        lines.append(
            f"| {variant} | {pct(item['source_recall'])} | {pct(item['retrieval_precision'])} | "
            f"{pct(item['major_path_coverage'])} | {pct(item['false_discovery_rate'])} | "
            f"{pct(item['pricing_anchor_valid_rate'])} | {'—' if tokens is None else f'{tokens:.0f}'} |"
        )
    lines.extend([
        "",
        "| Variant | Valid insight cards | Valid causal paths | Complete traces | "
        "Hypothesis laundering | Formal/exploration confusion |",
        "|:---|---:|---:|---:|---:|---:|",
    ])
    for variant, item in summary["aggregates"].items():
        lines.append(
            f"| {variant} | {pct(item['insight_card_valid_rate'])} | "
            f"{pct(item['causal_path_valid_rate'])} | "
            f"{pct(item['exploration_trace_complete_rate'])} | "
            f"{item['hypothesis_laundering_count']} | "
            f"{item['formal_exploration_action_confusion_count']} |"
        )
    if summary["errors"]:
        lines.extend(["", "## Blocking errors", *[f"- {item}" for item in summary["errors"]]])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate_cmd = sub.add_parser("validate-suite")
    validate_cmd.add_argument("--suite", required=True)
    verify_cmd = sub.add_parser("verify-variants")
    verify_cmd.add_argument("--suite", required=True)
    verify_cmd.add_argument("--source-repo", required=True)
    init_cmd = sub.add_parser("init-run")
    init_cmd.add_argument("--suite", required=True)
    init_cmd.add_argument("--case-id", required=True)
    init_cmd.add_argument("--variant", required=True)
    init_cmd.add_argument("--output-dir", required=True)
    search_cmd = sub.add_parser("search")
    search_cmd.add_argument("--run-dir", required=True)
    search_cmd.add_argument("--query", required=True)
    search_cmd.add_argument("--limit", type=int, default=5)
    read_cmd = sub.add_parser("read")
    read_cmd.add_argument("--run-dir", required=True)
    read_cmd.add_argument("--doc-id", required=True)
    finalize_cmd = sub.add_parser("finalize-retrieval")
    finalize_cmd.add_argument("--run-dir", required=True)
    score_cmd = sub.add_parser("score")
    score_cmd.add_argument("--suite", required=True)
    score_cmd.add_argument("--answer-key", required=True)
    score_cmd.add_argument("--results-dir", required=True)
    score_cmd.add_argument("--output-json", required=True)
    score_cmd.add_argument("--output-md", required=True)
    args = parser.parse_args()

    if args.command in {"search", "read", "finalize-retrieval"}:
        if args.command == "search":
            output = search(args.run_dir, args.query, args.limit)
        elif args.command == "read":
            output = read_document(args.run_dir, args.doc_id)
        else:
            output = finalize_retrieval(args.run_dir)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return
    suite = validate_suite(_load_json(args.suite), args.suite)
    if args.command == "validate-suite":
        print(json.dumps({
            "status": "VALID", "suite_id": suite["suite_id"],
            "evaluation_scope": EVALUATION_SCOPE,
            "case_count": len(suite["cases"]), "variants": suite["variants"],
            "corpus_document_count": len(suite["documents"]),
            "suite_contract_sha256": suite["suite_contract_sha256"],
        }, ensure_ascii=False, indent=2))
        return
    if args.command == "verify-variants":
        print(json.dumps({
            "status": "VERIFIED",
            "git_variants": verify_git_variants(suite, args.source_repo),
            "suite_contract_sha256": suite["suite_contract_sha256"],
        }, ensure_ascii=False, indent=2))
        return
    if args.command == "init-run":
        dispatch = initialize_run(suite, args.suite, args.case_id, args.variant, args.output_dir)
        print(json.dumps({
            "status": "INITIALIZED", "session_id": dispatch["session_id"],
            "dispatch_path": str((Path(args.output_dir) / "dispatch.json").resolve()),
            "suite_contract_sha256": suite["suite_contract_sha256"],
        }, ensure_ascii=False, indent=2))
        return
    summary = score_suite(suite, _load_json(args.answer_key), args.results_dir)
    Path(args.output_json).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    Path(args.output_md).write_text(render_markdown(summary), encoding="utf-8")
    status, exit_code = _method_change_cli_outcome(summary)
    print(json.dumps({
        "status": status,
        "comparison_ready": summary["comparison_ready"],
        "candidate_variant": summary.get("candidate_variant"),
        "method_change_gate_pass": summary.get("method_change_gate_pass"),
        "method_change_gate_ready": summary["method_change_gate_ready"],
        "errors": summary["errors"],
    }, ensure_ascii=False, indent=2))
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
