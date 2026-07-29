#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compact deterministic user views for Trade Nothing v2 research state.

Raw agent payloads stay in state for audit and never enter these user views.
"""
import json

import crux_engine
import hypothesis_engine
import landscape_engine
import opportunity_engine


SCHEMA_RESOLUTION = "trade-nothing.resolution.v1"
SCHEMA_CONTINUATION = "trade-nothing.continuation.v1"
SCHEMA_RUNTIME_FAILURE = "trade-nothing.runtime-failure.v1"
FORBIDDEN_PACKET_KEYS = {
    "detective_raw", "inquisitor_raw", "judge_raw", "evidence_chain",
    "crux_attacks", "lethal_attack_vectors", "opportunity_harvest",
}


def _text(value):
    return " ".join(str(value or "").split())


def _cell(value):
    return _text(value).replace("|", "\\|")


def _proxy_direction_lineage(proxy):
    variants = proxy.get("direction_variants", [])
    variant_text = (
        f"[{','.join(str(value) for value in variants)}]"
        if proxy.get("direction_contested")
        else ""
    )
    bindings = []
    for binding in proxy.get("direction_bindings", [])[:6]:
        if not isinstance(binding, dict):
            continue
        evidence_ids = ",".join(
            str(value) for value in binding.get("evidence_ids", [])
        ) or "no-evidence"
        bindings.append(
            f"{binding.get('direction', 'AMBIGUOUS')}@"
            f"R{binding.get('round', '—')}/"
            f"{binding.get('source_agent') or '—'}/"
            f"{binding.get('origin_crux') or '—'}/"
            f"{evidence_ids}/"
            f"{binding.get('authorized_action_id') or 'no-action'}"
        )
    binding_text = "；".join(bindings) or "—"
    return (
        f"{proxy.get('direction', 'AMBIGUOUS')}{variant_text}: "
        f"{proxy.get('proxy') or '—'}；bindings={binding_text}"
    )


def _bounded_text(value, receipt, limit=280):
    text = _text(value)
    if len(text) <= limit:
        return text
    receipt["truncated_fields"] += 1
    return text[: max(0, limit - 1)] + "…"


def _compact_exploration(
    state, limit=5, total_byte_budget=12000
):
    view = hypothesis_engine.report_view(state, limit=limit)
    truncation = {
        "truncated_fields": 0,
        "field_character_limit": 280,
        "evidence_per_proxy_limit": 2,
        "proxy_trails_per_hypothesis_limit": 3,
    }
    action = view.get("exploration_action", {})
    compact_action = {
        key: action.get(key)
        for key in (
            "action_id",
            "action_code",
            "action_type",
            "hypothesis_id",
            "hypothesis_state",
            "host_action_status",
            "proposal_drifted",
            "recomputed_action",
            "requires_human_authorization",
            "authorization_state",
            "authorization_ready",
            "executable_after_authorization",
            "authorization_assurance",
            "execution_receipt",
            "budget_boundary",
            "as_of_date",
            "route_spec",
            "excluded_existing_domains",
            "design_target_id",
            "design_state_revision",
            "authority",
        )
    }
    for key in (
        "reason",
        "instruction",
        "question",
        "source_class",
        "bounded_query",
        "success_condition",
        "stop_condition",
    ):
        compact_action[key] = _bounded_text(action.get(key), truncation)
    result = {
        "summary": view.get("summary", {}),
        "exploration_action": compact_action,
        "authorized_action_history": [
            {
                "action_id": item.get("action_id"),
                "hypothesis_id": item.get("hypothesis_id"),
                "action_code": item.get("action_code"),
                "execution_status": item.get("execution_status"),
                "authorization_assurance": item.get(
                    "authorization_assurance"
                ),
                "source_class": _bounded_text(
                    item.get("source_class"), truncation
                ),
                "bounded_query": _bounded_text(
                    item.get("bounded_query"), truncation
                ),
                "negative_knowledge": _bounded_text(
                    item.get("negative_knowledge"), truncation
                ),
                "execution_receipt": item.get("execution_receipt"),
            }
            for item in view.get("authorized_action_history", [])[-5:]
            if isinstance(item, dict)
        ],
        "design_history": [
            {
                "design_id": item.get("design_id"),
                "hypothesis_id": item.get("hypothesis_id"),
                "action_code": item.get("action_code"),
                "design_note": _bounded_text(
                    item.get("design_note"), truncation
                ),
                "state_before": item.get("state_before"),
                "state_after": item.get("state_after"),
                "authority": item.get("authority"),
            }
            for item in view.get("design_history", [])[-5:]
            if isinstance(item, dict)
        ],
        "closed_routes": [
            {
                "route_id": item.get("route_id"),
                "action_id": item.get("action_id"),
                "hypothesis_id": item.get("hypothesis_id"),
                "execution_status": item.get("execution_status"),
                "source_class": _bounded_text(
                    item.get("source_class"), truncation
                ),
                "bounded_query": _bounded_text(
                    item.get("bounded_query"), truncation
                ),
                "stop_reason": _bounded_text(
                    item.get("stop_reason"), truncation
                ),
            }
            for item in view.get("closed_routes", [])[-5:]
            if isinstance(item, dict)
        ],
        "terminal_action_history": [
            {
                "action_id": item.get("action_id"),
                "status": item.get("status"),
                "hypothesis_id": item.get("hypothesis_id"),
                "action_code": item.get("action_code"),
                "as_of_date": item.get("as_of_date"),
                "route_id": item.get("route_id"),
                "authorization_assurance": item.get(
                    "authorization_assurance"
                ),
                "authorization_occurred": item.get(
                    "authorization_occurred"
                ),
                "execution_occurred": item.get("execution_occurred"),
                "execution_status": item.get("execution_status"),
                "reason": _bounded_text(
                    item.get("reason"), truncation
                ),
                "result_sha256": item.get("result_sha256"),
                "result_ingested": item.get("result_ingested"),
                "proxy_ingested": item.get("proxy_ingested"),
                "automatic_retry": item.get("automatic_retry"),
            }
            for item in view.get("terminal_action_history", [])[-5:]
            if isinstance(item, dict)
        ],
        "hypotheses": [
            {
                "hypothesis_id": item.get("hypothesis_id"),
                "state": item.get("state"),
                "hypothesis": _bounded_text(
                    item.get("hypothesis"), truncation
                ),
                "observation": _bounded_text(
                    item.get("observation"), truncation
                ),
                "observation_status": item.get(
                    "observation_status", "UNVERIFIED_CLUE"
                ),
                "why_nonconsensus": _bounded_text(
                    item.get("why_nonconsensus"), truncation
                ),
                "surprise_if_true": _bounded_text(
                    item.get("surprise_if_true"), truncation
                ),
                "strongest_alternative_explanation": _bounded_text(
                    item.get("strongest_alternative_explanation"), truncation
                ),
                "causal_chain": [
                    _bounded_text(value, truncation)
                    for value in item.get("causal_chain", [])[:6]
                ],
                "value_transfer": _bounded_text(
                    item.get("value_transfer"), truncation
                ),
                "cheap_discriminating_test": _bounded_text(
                    item.get("cheap_discriminating_test"), truncation
                ),
                "falsifier": _bounded_text(
                    item.get("falsifier"), truncation
                ),
                "catalyst": _bounded_text(
                    item.get("catalyst"), truncation
                ),
                "expiry_date": _bounded_text(
                    item.get("expiry_date"), truncation
                ),
                "exploration_priority": item.get("exploration_priority", {}),
                "asymmetry_case": item.get("asymmetry_case", {}),
                "break_even_threshold": item.get("break_even_threshold", {}),
                "contested_fields": item.get("contested_fields", []),
                "field_variants": item.get("field_variants", {}),
                "proxy_trails": [
                    {
                        "proxy_id": proxy.get("proxy_id"),
                        "route_id": proxy.get("route_id"),
                        "planned_proxy": _bounded_text(
                            proxy.get("planned_proxy"), truncation
                        ),
                        "planned_direction": proxy.get("planned_direction"),
                        "authorized_action_id": proxy.get(
                            "authorized_action_id"
                        ),
                        "authorized_action_ids": proxy.get(
                            "authorized_action_ids", []
                        )[:5],
                        "authorized_route_bindings": proxy.get(
                            "authorized_route_bindings", []
                        )[:5],
                        "trail_ids": proxy.get("trail_ids", [])[:5],
                        "origin_crux": proxy.get("origin_crux"),
                        "proxy": _bounded_text(
                            proxy.get("proxy"), truncation
                        ),
                        "causal_link": _bounded_text(
                            proxy.get("causal_link"), truncation
                        ),
                        "alternative_explanation": _bounded_text(
                            proxy.get("alternative_explanation"), truncation
                        ),
                        "direction": proxy.get("direction"),
                        "direction_variants": proxy.get(
                            "direction_variants", []
                        ),
                        "direction_contested": proxy.get(
                            "direction_contested", False
                        ),
                        "direction_bindings": proxy.get(
                            "direction_bindings", []
                        )[:6],
                        "evidence_count": len(proxy.get("evidence", [])),
                        "checkpoint": _bounded_text(
                            proxy.get("checkpoint"), truncation
                        ),
                        "next_source_class": _bounded_text(
                            proxy.get("next_source_class")
                            or proxy.get("publisher_class"),
                            truncation,
                        ),
                        "bounded_query": _bounded_text(
                            proxy.get("bounded_query"), truncation
                        ),
                        "stop_condition": _bounded_text(
                            proxy.get("stop_condition"), truncation
                        ),
                        "route_contested_fields": proxy.get(
                            "route_contested_fields", []
                        ),
                        "route_field_variants": proxy.get(
                            "route_field_variants", {}
                        ),
                        "evidence": [
                            {
                                "claim": _bounded_text(
                                    citation.get("claim"), truncation
                                ),
                                "source": _bounded_text(
                                    citation.get("source"), truncation
                                ),
                                "url": _bounded_text(
                                    citation.get("url"), truncation, limit=500
                                ),
                                "date": _bounded_text(
                                    citation.get("date"), truncation, limit=32
                                ),
                            }
                            for citation in proxy.get("evidence", [])[:2]
                            if isinstance(citation, dict)
                        ],
                    }
                    for proxy in item.get("proxy_trails", [])[:3]
                ],
            }
            for item in view.get("hypotheses", [])[:limit]
        ],
        "truncation_receipt": truncation,
    }
    truncation.update({
        "total_byte_budget": total_byte_budget,
        "omitted_evidence_items": 0,
        "omitted_proxy_trails": 0,
        "omitted_hypotheses": 0,
        "degraded_to_summary": False,
    })

    def byte_size():
        return len(
            json.dumps(
                result, ensure_ascii=False, sort_keys=True
            ).encode("utf-8")
        )

    # The continuation packet must remain deliverable even when a role submits
    # pathologically long but structurally valid prose. Preserve the ranked
    # hypothesis summary and action first, then shed lower-value detail with an
    # explicit receipt.
    for hypothesis in reversed(result["hypotheses"]):
        for proxy in reversed(hypothesis.get("proxy_trails", [])):
            if byte_size() <= truncation["total_byte_budget"]:
                break
            omitted = len(proxy.get("evidence", []))
            if omitted:
                proxy["evidence"] = []
                truncation["omitted_evidence_items"] += omitted
        if byte_size() <= truncation["total_byte_budget"]:
            break
    while byte_size() > truncation["total_byte_budget"]:
        removable = next(
            (
                hypothesis
                for hypothesis in reversed(result["hypotheses"])
                if hypothesis.get("proxy_trails")
            ),
            None,
        )
        if removable is None:
            break
        removable["proxy_trails"].pop()
        truncation["omitted_proxy_trails"] += 1
    while (
        byte_size() > truncation["total_byte_budget"]
        and len(result["hypotheses"]) > 1
    ):
        result["hypotheses"].pop()
        truncation["omitted_hypotheses"] += 1
    if byte_size() > truncation["total_byte_budget"]:
        result["hypotheses"] = []
        truncation["degraded_to_summary"] = True
    return result


def render_runtime_failure_memo(topic, stage, reason, state_initialized=False):
    """Render a small failure receipt; never treat runtime failure as research evidence."""
    safe_topic = _text(topic)[:240] or "未命名主题"
    safe_stage = _text(stage)[:80] or "unknown"
    safe_reason = _text(reason)[:500] or "运行时未返回结构化失败原因"
    state_note = "已初始化；现有 state 不得被缺失输出污染。" if state_initialized else "尚未初始化；没有研究结论可保留。"
    return "\n".join([
        f"# Trade Nothing 运行失败备忘录 — {safe_topic}",
        "",
        f"> schema: `{SCHEMA_RUNTIME_FAILURE}`",
        "> **非研究结论。** 本备忘录只记录宿主运行故障，不能替代正式报告、Resolution Memo 或投资判断。",
        "",
        f"- 失败阶段: `{safe_stage}`",
        f"- 状态: {state_note}",
        f"- 原因: {safe_reason}",
        "- 处理: 禁止伪造代理输出、禁止自动重试；修复运行时后由用户显式授权重跑。",
    ])


def _valid_sources(cx):
    return sorted({
        crux_engine.citation_source_identity(c)
        for c in cx.get("citations", [])
        if crux_engine.valid_citation(c)
    })


def crux_gap_codes(cx):
    gaps = []
    contested = len(cx.get("contested_history", []))
    sources = len(_valid_sources(cx))
    if cx.get("first_contested") is None:
        gaps.append("NEVER_CONTESTED")
    if contested < crux_engine.MIN_CONTESTED:
        gaps.append("INSUFFICIENT_CONTESTED_ROUNDS")
    if sources < crux_engine.MIN_VALID_CITATIONS:
        gaps.append("INSUFFICIENT_UNIQUE_SOURCES")
    if not _text(cx.get("falsifier")):
        gaps.append("MISSING_FALSIFIER")
    catalyst = cx.get("catalyst_window")
    if not isinstance(catalyst, dict) or not all(
        _text(catalyst.get(field)) for field in ("event", "expected_by", "date_status")
    ):
        gaps.append("MISSING_CATALYST_WINDOW")
    history = cx.get("contested_history", [])
    if len(history) >= 2 and abs(history[-1] - history[-2]) >= crux_engine.EPS_STABLE:
        gaps.append("UNSTABLE_SUPPORT")
    return gaps


def _evidence_stance(state):
    statuses = [cx.get("status") for cx in state.get("cruxes", {}).values()]
    bull = statuses.count("RESOLVED_BULL")
    bear = statuses.count("RESOLVED_BEAR")
    if bull and bear:
        return "MIXED"
    if bull:
        return "FAVORS_BULL"
    if bear:
        return "FAVORS_BEAR"
    return "UNDETERMINED"


def _research_status(state):
    decision = state.get("last_convergence", {}).get("decision")
    if decision == "converge":
        return "READY"
    if decision == "fuse_break":
        return "BLOCKED_MAX_ROUNDS"
    return "INCOMPLETE"


def _crux_view(cid, cx):
    sources = _valid_sources(cx)
    catalyst = cx.get("catalyst_window") if isinstance(cx.get("catalyst_window"), dict) else {}
    return {
        "id": cid,
        "label": cx.get("label", ""),
        "definition": cx.get("definition", ""),
        "status": cx.get("status", "PENDING"),
        "introduced_round": cx.get("introduced", 0),
        "contested_rounds": len(cx.get("contested_history", [])),
        "unique_source_count": len(sources),
        "missing_unique_sources": max(0, crux_engine.MIN_VALID_CITATIONS - len(sources)),
        "gap_codes": crux_gap_codes(cx),
        "best_bull": cx.get("best_bull"),
        "best_bear": cx.get("best_bear"),
        "monitor_anchor": cx.get("monitor_anchor", ""),
        "falsifier": cx.get("falsifier", ""),
        "evidence_plan": cx.get("evidence_plan", []),
        "catalyst_window": catalyst,
        "transition_reason": cx.get("transition_reason"),
        "monitorable_semantics": cx.get("monitorable_semantics"),
        "zero_signal_receipt_count": sum(
            item.get("support_effect") == "NONE_ZERO_SIGNAL_WASH"
            for item in cx.get("citations", [])
            if isinstance(item, dict)
        ),
        "seen_source_urls": sources[:5],
    }


def _focus_key(item):
    return (
        0 if "NEVER_CONTESTED" in item["gap_codes"] else 1,
        -item["missing_unique_sources"],
        item["introduced_round"],
        item["id"],
    )


def recommended_extra_rounds(state, open_views=None):
    open_views = open_views or []
    current = len(state.get("rounds", []))
    max_introduced = int(state.get("max_introduced_round", 0) or 0)
    dry_gap = max(0, crux_engine.DRY_ROUNDS - (current - max_introduced))
    contested_gap = max(
        [max(0, crux_engine.MIN_CONTESTED - item["contested_rounds"]) for item in open_views]
        or [0]
    )
    desired = max(2, dry_gap, contested_gap)
    remaining = max(0, crux_engine.MAX_ROUNDS - current)
    return min(desired, remaining)


def build_continuation_packet(state):
    open_views = [
        _crux_view(cid, cx)
        for cid, cx in state.get("cruxes", {}).items()
        if cx.get("status") in {"PENDING", "OPEN"}
    ]
    open_views.sort(key=_focus_key)
    opportunities = []
    for entity in opportunity_engine.entity_views(state):
        if entity["screening_status"] == opportunity_engine.READY:
            continue
        representative = entity["representative_seed"]
        opportunities.append({
            "entity_id": entity["entity_id"],
            "candidate": entity["candidate"],
            "ticker": entity.get("ticker"),
            "representative_seed_id": entity["representative_seed_id"],
            "origin_crux": representative.get("origin_crux"),
            "screening_status": entity["screening_status"],
            "blockers": entity["paths"][0]["assessment"].get("blockers", []),
        })
    landscape = landscape_engine.summary(state)
    packet = {
        "schema_version": SCHEMA_CONTINUATION,
        "topic": state.get("topic", ""),
        "decision_question": state.get("decision_question", ""),
        "source_round": len(state.get("rounds", [])),
        "terminal_status": _research_status(state),
        "formal_report_allowed": state.get("last_convergence", {}).get("decision") == "converge",
        "current_evidence_stance": _evidence_stance(state),
        "dispatch_policy": {
            "only_open_cruxes": True,
            "crux_ids": [item["id"] for item in open_views],
            "resolved_cruxes_must_not_be_redispatched": True,
            "free_roam_allowed": not any("NEVER_CONTESTED" in item["gap_codes"] for item in open_views),
            "new_cruxes_allowed": False,
        },
        "search_budget": {
            "max_searches_per_agent": 10,
            "max_searches_per_crux": 2,
            "max_primary_sources_per_crux": 2,
            "max_secondary_sources_per_crux": 1,
            "stop_when_no_new_primary_evidence_after_searches": 2,
            "unknown_is_valid": True,
        },
        "open_cruxes": open_views,
        "landscape_coverage": {
            key: landscape[key] for key in (
                "required", "path_count", "unprobed_count", "supported_count",
                "rejected_count", "unknown_count", "coverage_complete"
            )
        },
        "unprobed_landscape_paths": [
            item for item in landscape["paths"] if item.get("state") == "UNPROBED"
        ],
        "deferred_opportunities": opportunities[:10],
        "hypothesis_exploration": _compact_exploration(state, limit=5),
        "deferred_new_cruxes": state.get("deferred_cruxes", [])[-10:],
        "resume": {
            "requires_explicit_authorization": True,
            "recommended_extra_rounds": recommended_extra_rounds(state, open_views),
            "hard_max_rounds": crux_engine.MAX_ROUNDS,
        },
    }
    assert_compact_packet(packet)
    return packet


def build_resolution_view(state):
    all_cruxes = [_crux_view(cid, cx) for cid, cx in state.get("cruxes", {}).items()]
    open_cruxes = [item for item in all_cruxes if item["status"] in {"PENDING", "OPEN"}]
    open_cruxes.sort(key=_focus_key)
    settled = [item for item in all_cruxes if item["status"] not in {"PENDING", "OPEN"}]
    entities = []
    for entity in opportunity_engine.entity_views(state):
        seed = entity["representative_seed"]
        entities.append({
            "entity_id": entity["entity_id"],
            "candidate": entity["candidate"],
            "ticker": entity.get("ticker"),
            "screening_status": entity["screening_status"],
            "path_count": len(entity["paths"]),
            "representative_seed_id": entity["representative_seed_id"],
            "relation_type": seed.get("relation_type"),
            "origin_crux": seed.get("origin_crux"),
            "causal_path": seed.get("causal_path"),
            "economic_exposure": seed.get("economic_exposure"),
            "catalyst": seed.get("catalyst"),
            "catalyst_window": seed.get("catalyst_window", {}),
            "falsifier": seed.get("falsifier"),
            "blockers": entity["paths"][0]["assessment"].get("blockers", []),
        })
    verdict = crux_engine.research_verdict(state)
    landscape = landscape_engine.summary(state)
    return {
        "schema_version": SCHEMA_RESOLUTION,
        "output_type": "NON_FORMAL_RESOLUTION_MEMO",
        "formal_report_allowed": False,
        "topic": state.get("topic", ""),
        "decision_question": state.get("decision_question", ""),
        "horizon": state.get("horizon", ""),
        "as_of_date": (
            state.get("frame_contract", {}).get("as_of_date")
            or state.get("as_of_date")
            or ""
        ),
        "research_status": _research_status(state),
        "evidence_stance": _evidence_stance(state),
        "engine_decision": crux_engine.safe_decision_label(
            (state.get("decision_trace") or [{}])[-1].get("decision")
        ),
        "research_verdict": verdict,
        "rounds": len(state.get("rounds", [])),
        "coverage": {
            "total_cruxes": len(all_cruxes),
            "settled_cruxes": len(settled),
            "open_cruxes": len(open_cruxes),
            "never_contested_cruxes": sum("NEVER_CONTESTED" in item["gap_codes"] for item in all_cruxes),
        },
        "settled_cruxes": settled,
        "blocking_cruxes": open_cruxes,
        "opportunity_entities": entities,
        "opportunity_summary": opportunity_engine.summary(state),
        "hypothesis_exploration": _compact_exploration(
            state, limit=7, total_byte_budget=24000
        ),
        "scenario_paths": hypothesis_engine.scenario_view(state),
        "landscape_coverage": landscape,
        "convergence_reason": state.get("last_convergence", {}).get("reason", ""),
        "continuation_packet": build_continuation_packet(state),
        "limitations": [
            "该备忘录不是正式研究报告，也不是交易、收益、目标价或仓位指令。",
            "结构化 URL 尚不等于页面内容已通过快照与 claim 对齐。",
            "OpportunitySeed 是研究队列；被阻塞或待核的线索不得表述为可投资候选。",
            "探索假说与 ProxyTrail 只分配研究注意力，不得改写 root verdict 或候选成熟度。",
        ],
    }


def _status_label(status):
    return {
        "RESOLVED_BULL": "当前证据偏多",
        "RESOLVED_BEAR": "当前证据偏空",
        "MONITORABLE": "可监控",
        "OPEN": "证据冲突",
        "PENDING": "未实际质证",
    }.get(status, status or "未知")


def render_resolution_memo(state):
    view = build_resolution_view(state)
    L = [
        f"# Trade Nothing 未收敛研究备忘录 — {view['topic']}",
        "",
        "> **非正式结论。** 本产物用于保留已获得的信息、暴露证据缺口并定义下一轮最小研究任务；",
        "> 它不能替代通过 convergence 与 evidence gate 的正式报告。",
        "",
        "## 研究裁决",
        f"- 研究状态: **{view['research_status']}** ｜ 当前证据方向: **{view['evidence_stance']}**",
        f"- 三维 verdict: **{view['research_verdict']['edge_state']} / "
        f"{view['research_verdict']['evidence_direction']} / "
        f"{view['research_verdict']['actionability']}** ｜ "
        f"题型: **{view['research_verdict']['question_type']}**",
        f"- 决策问题: {view['decision_question']} ｜ 视野: {view['horizon']} ｜ "
        f"证据截止: {view.get('as_of_date') or 'UNKNOWN'}",
        f"- 覆盖: {view['coverage']['settled_cruxes']}/{view['coverage']['total_cruxes']} 条 crux 已形成可用方向；"
        f"{view['coverage']['never_contested_cruxes']} 条从未实际质证。",
        f"- 阻塞原因: {_text(view['convergence_reason']) or 'engine 尚未满足正式报告闸门。'}",
        "- 当前能做的决策仅是研究资源分配：保留已登记线索，优先补齐阻塞 crux；不得提升根命题或候选。",
        "",
        "## 已形成方向的 Crux",
    ]
    landscape = view.get("landscape_coverage", {})
    if landscape.get("required"):
        L.insert(13, (
            f"- Landscape: {landscape['path_count']} 条计划路径；SUPPORTED "
            f"{landscape['supported_count']} / REJECTED {landscape['rejected_count']} / "
            f"UNKNOWN {landscape['unknown_count']} / UNPROBED {landscape['unprobed_count']}。"
        ))
    if not view["settled_cruxes"]:
        L.append("- 无。")
    for item in view["settled_cruxes"]:
        L.extend([
            f"### {item['id']} · {item['label']} — {_status_label(item['status'])}",
            f"- 最强多头: {_text(item['best_bull']) or '—'}",
            f"- 最强空头: {_text(item['best_bear']) or '—'}",
            f"- 监控 / 反证: {_text(item['monitor_anchor']) or '—'} / {_text(item['falsifier']) or '—'}",
            f"- 转换原因: `{item.get('transition_reason') or '—'}`；"
            f"{_text(item.get('monitorable_semantics')) or '非耗尽型转换'}",
            f"- 零信号事实回执: {item.get('zero_signal_receipt_count', 0)} 条；"
            "`NONE_ZERO_SIGNAL_WASH` 只扩充账本，不移动支持度。",
            f"- 账本来源: {item['unique_source_count']} 个具体 URL；尚未等同于 snapshot verification。",
            "",
        ])
    L.extend(["## 真正阻塞结论的 Crux", ""])
    if not view["blocking_cruxes"]:
        L.append("- 无开放 crux；若仍阻塞，检查稳定性与 adversary-dry 条件。")
    else:
        L.append("| 优先 | crux | 状态 | 缺口代码 | 下一步只查什么 |")
        L.append("|:---:|:---|:---|:---|:---|")
        for index, item in enumerate(view["blocking_cruxes"], 1):
            planned = [
                f"{route.get('publisher_class')}: {route.get('target_claim')}"
                for route in item.get("evidence_plan", [])
                if isinstance(route, dict) and route.get("target_claim")
            ]
            next_check = (
                "；".join(planned)
                or item["monitor_anchor"]
                or item["definition"]
                or "补充一级来源并形成双侧质证"
            )
            L.append(
                f"| {index} | **{item['id']} {item['label']}** | {_status_label(item['status'])} | "
                f"{', '.join(item['gap_codes']) or 'UNSTABLE'} | {_text(next_check)} |"
            )
    exploration = view.get("hypothesis_exploration", {})
    hypotheses = exploration.get("hypotheses", [])
    action = exploration.get("exploration_action", {})
    L.extend([
        "",
        "## 大胆假说与草蛇灰线（无晋级权限）",
        f"- 探索动作: `{action.get('action_code', 'NO_EXPLORATION_TRACK')}` ｜ "
        f"假说 `{action.get('hypothesis_id') or '—'}` ｜ "
        f"{_text(action.get('instruction') or action.get('reason')) or '无'}",
        f"- 授权状态: `{action.get('authorization_state', 'NOT_REQUIRED')}` ｜ "
        f"执行就绪: `{action.get('executable_after_authorization', False)}` ｜ "
        f"来源类: {_text(action.get('source_class')) or '—'} ｜ "
        f"有界查询: {_text(action.get('bounded_query')) or '—'}。",
        f"- Host action: `{action.get('action_id') or '—'}` ｜ "
        f"host_status=`{action.get('host_action_status') or '—'}` ｜ "
        f"assurance=`{action.get('authorization_assurance') or '—'}` ｜ "
        f"proposal_drifted="
        f"`{action.get('proposal_drifted', False)}`。",
        (
            f"- 设计回执目标: `{action.get('design_target_id') or '—'}` ｜ "
            f"expected_state_revision="
            f"`{action.get('design_state_revision', '—')}`；"
            "仅允许写入探索设计，不授权搜索。"
            if action.get("authorization_state") == "NEEDS_ACTION_DESIGN"
            else "- 当前动作不需要新的 typed design 回执。"
        ),
        f"- 问题: {_text(action.get('question')) or '—'} ｜ "
        f"成功: {_text(action.get('success_condition')) or '—'} ｜ "
        f"停止: {_text(action.get('stop_condition')) or '—'}。",
        f"- 预算: queries≤"
        f"{action.get('budget_boundary', {}).get('max_bounded_queries', 0)}，"
        f"documents≤"
        f"{action.get('budget_boundary', {}).get('max_documents_read', 0)}，"
        f"new trails≤"
        f"{action.get('budget_boundary', {}).get('max_new_proxy_trails', 0)}；"
        f"execution_receipt=`{action.get('execution_receipt')}`。",
        "- 本节可在正式报告阻塞时继续保留启发式发现；它不能触发自动续跑、候选筛选或交易。",
    ])
    if not hypotheses:
        L.append("- 无已登记假说。")
    else:
        L.append("| 假说 | 状态 | 价值传导 / 反证 | ProxyTrail |")
        L.append("|:---|:---:|:---|:---|")
        for item in hypotheses:
            proxies = "；".join(
                _proxy_direction_lineage(proxy)
                for proxy in item.get("proxy_trails", [])[:3]
            ) or "尚无"
            asymmetry = item.get("asymmetry_case", {})
            priority = item.get("exploration_priority", {})
            L.append(
                f"| **{_cell(item.get('hypothesis_id'))}** "
                f"{_cell(item.get('hypothesis'))} | `{_cell(item.get('state'))}` | "
                f"{_cell(item.get('observation_status'))}: "
                f"{_cell(item.get('observation')) or '—'}；"
                f"替代解释={_cell(item.get('strongest_alternative_explanation')) or '—'}；"
                f"最低成本判别={_cell(item.get('cheap_discriminating_test')) or '—'}；"
                f"定性非对称="
                f"{_cell(asymmetry.get('upside_shape'))}/"
                f"{_cell(asymmetry.get('convexity'))} vs "
                f"{_cell(asymmetry.get('downside_shape'))}；"
                f"signal={_cell(asymmetry.get('time_to_signal'))}；"
                f"basis={_cell(asymmetry.get('basis')) or '—'}；"
                f"探索排序={_cell(priority.get('band')) or 'PARK'}"
                f"(score={priority.get('score', 0)}；"
                f"components={_cell(priority.get('components'))}；"
                f"reasons={_cell(priority.get('reasons'))})；"
                f"争议字段={_cell(item.get('contested_fields'))}；"
                f"争议变体={_cell(item.get('field_variants'))}；"
                f"{_cell(item.get('value_transfer')) or '—'} / "
                f"{_cell(item.get('falsifier')) or '—'}；"
                f"expiry={_cell(item.get('expiry_date')) or '—'} | "
                f"{_cell(proxies)} |"
            )
    L.extend(["", "### 已执行探索与负知识"])
    action_history = [
        item
        for item in exploration.get("authorized_action_history", [])
        if isinstance(item, dict)
    ]
    if not action_history:
        L.append("- 尚无经显式授权并完成的探索动作。")
    for item in action_history[-5:]:
        receipt = item.get("execution_receipt") or {}
        documents = receipt.get("document_receipts") or []
        document_ids = ", ".join(
            str(document.get("document_id") or "—")
            for document in documents
            if isinstance(document, dict)
        ) or "无"
        L.append(
            f"- `{item.get('action_id', '—')}` "
            f"`{item.get('execution_status', 'UNKNOWN')}`："
            f"route={item.get('route_id') or receipt.get('route_id') or '—'}；"
            f"proxy={item.get('proxy_id') or receipt.get('proxy_id') or '—'}；"
            f"query={_text(item.get('bounded_query')) or '—'}；"
            f"stop={_text(receipt.get('stop_reason')) or '—'}；"
            f"assurance="
            f"`{item.get('authorization_assurance') or '—'}`；"
            f"documents={document_ids}；"
            f"sha256=`{receipt.get('result_sha256', '—')}`；"
            f"negative={_text(item.get('negative_knowledge')) or '—'}。"
        )
    terminal_history = [
        item
        for item in exploration.get("terminal_action_history", [])
        if isinstance(item, dict)
    ]
    L.extend(["", "### Host 探索动作终态"])
    if not terminal_history:
        L.append("- 尚无已关闭的 host 探索动作。")
    for item in terminal_history[-5:]:
        L.append(
            f"- `{item.get('action_id', '—')}` "
            f"`{item.get('status', 'UNKNOWN')}`："
            f"route={item.get('route_id') or '—'}；"
            f"action_as_of={item.get('as_of_date') or '—'}；"
            f"reason={_text(item.get('reason')) or '—'}；"
            f"assurance="
            f"`{item.get('authorization_assurance') or '—'}`；"
            f"result_sha256=`{item.get('result_sha256') or '—'}`；"
            f"result_ingested={item.get('result_ingested', False)}；"
            f"proxy_ingested={item.get('proxy_ingested', False)}；"
            f"automatic_retry={item.get('automatic_retry', False)}。"
        )
    design_history = [
        item
        for item in exploration.get("design_history", [])
        if isinstance(item, dict)
    ]
    L.extend(["", "### Typed design 历史"])
    if not design_history:
        L.append("- 尚无 typed design 写入。")
    for item in design_history[-5:]:
        L.append(
            f"- `{item.get('design_id', '—')}` / "
            f"`{item.get('action_code', 'UNKNOWN')}` / "
            f"假说 `{item.get('hypothesis_id', '—')}`："
            f"{_text(item.get('design_note')) or '—'}；"
            f"state `{item.get('state_before', '—')}` → "
            f"`{item.get('state_after', '—')}`。"
        )
    closed_routes = [
        item
        for item in exploration.get("closed_routes", [])
        if isinstance(item, dict)
    ]
    L.extend(["", "### 已关闭诊断路线"])
    if not closed_routes:
        L.append("- 尚无已关闭诊断路线。")
    for item in closed_routes[-5:]:
        L.append(
            f"- `{item.get('route_id', '—')}` / action "
            f"`{item.get('action_id', '—')}` / "
            f"`{item.get('execution_status', 'UNKNOWN')}`："
            f"query={_text(item.get('bounded_query')) or '—'}；"
            f"stop={_text(item.get('stop_reason')) or '—'}。"
        )
    scenario = view.get("scenario_paths", {})
    L.extend([
        "",
        "## 对称场景与非对称边界",
        f"- 路径审计: `{scenario.get('status', 'MISSING')}`；"
        "三路存在不代表等概率，也不产生收益预测。",
    ])
    for path in scenario.get("paths", []):
        L.append(
            f"- **{_text(path.get('path_type'))}**: "
            f"{_text(path.get('summary'))}；触发 {_text(path.get('trigger_event'))}；"
            f"传导 {_text(path.get('transmission_chain'))}；"
            f"监控 {_text(path.get('monitor_anchor'))}；"
            f"反证 {_text(path.get('falsifier'))}。"
        )
    if scenario.get("issues"):
        L.append(
            f"- 路径缺口: `{', '.join(scenario.get('issues', [])[:8])}`。"
        )
    threshold = scenario.get("break_even_threshold", {})
    L.append(
        "- 明示情景赔率门槛: "
        + (
            f"p*={threshold.get('p_star_percent')}%（非概率）"
            if threshold.get("status") == "KNOWN"
            else f"UNKNOWN（{threshold.get('reason', '缺少可比输入')}）"
        )
    )
    L.extend(["", "## 宝藏线索分诊（按唯一候选展示）", ""])
    if not view["opportunity_entities"]:
        L.append("- 本轮没有通过同轮、同 agent、同 crux 证据反查的线索。")
    else:
        L.append("| 候选 | 有效路径 | 当前研究资格 | 来源 crux | 下一步 |")
        L.append("|:---|:---:|:---|:---|:---|")
        for item in view["opportunity_entities"][:10]:
            name = item["candidate"] + (f" ({item['ticker']})" if item.get("ticker") else "")
            blockers = ", ".join(item.get("blockers", [])) or "进入双边 CandidateScreen"
            L.append(
                f"| **{_text(name)}** | {item['path_count']} | `{item['screening_status']}` | "
                f"{_text(item['origin_crux'])} | {blockers} |"
            )
    packet = view["continuation_packet"]
    L.extend([
        "",
        "## 下一轮最小补证计划",
        f"- 建议额外轮次: **{packet['resume']['recommended_extra_rounds']}**；必须由用户显式授权恢复，禁止自动续烧 Token。",
        f"- 只允许处理: {', '.join(packet['dispatch_policy']['crux_ids']) or '无'}。",
        f"- 未覆盖 Landscape 路径: "
        f"{', '.join(item['path_id'] for item in packet['unprobed_landscape_paths']) or '无'}。",
        "- 每个 agent 最多 10 次搜索、每条 crux 最多 2 次；连续两次没有新增一级证据即返回 UNKNOWN。",
        "- 已解决 crux 不得重派；存在从未质证 crux 时禁用 free-roam；本次续跑禁止新增 crux。",
        "",
        "## 限制",
    ])
    L.extend(f"- {item}" for item in view["limitations"])
    return "\n".join(L)


def build_synthesis_packet(state):
    """Compact formal-report input; intentionally excludes all raw agent payloads."""
    rd = crux_engine.report_data(state)
    return {
        "schema_version": "trade-nothing.synthesis.v1",
        "topic": state.get("topic", ""),
        "decision_question": state.get("decision_question", ""),
        "horizon": state.get("horizon", ""),
        "engine_decision": rd.get("decision"),
        "research_verdict": rd.get("research_verdict"),
        "question_type": rd.get("question_type"),
        "logic_graph": rd.get("logic_graph"),
        "landscape_coverage": landscape_engine.summary(state),
        "hypothesis_exploration": _compact_exploration(state, limit=7),
        "binding_crux": rd.get("binding_crux"),
        "focus_crux": rd.get("focus_crux"),
        "aggregation_rule": rd.get("aggregation_rule"),
        "cruxes": [
            {
                "id": item["id"],
                "label": item["label"],
                "status": item["status"],
                "best_bull": item.get("best_bull"),
                "best_bear": item.get("best_bear"),
                "monitor_anchor": item.get("monitor_anchor"),
                "falsifier": item.get("falsifier"),
                "catalyst_window": item.get("catalyst_window"),
                "citations": [
                    {key: citation.get(key) for key in ("claim", "number", "source", "url", "date", "source_tier")}
                    for citation in item.get("valid_citations", [])[:3]
                ],
            }
            for item in rd.get("cruxes", [])
        ],
        "opportunities": [
            {
                "entity_id": entity["entity_id"],
                "candidate": entity["candidate"],
                "ticker": entity.get("ticker"),
                "screening_status": entity["screening_status"],
                "path_count": len(entity["paths"]),
                "representative_seed_id": entity["representative_seed_id"],
            }
            for entity in opportunity_engine.entity_views(state)[:10]
        ],
        "limitations": [
            "Only use claims and URLs present in this packet.",
            "Do not interpret debate-support scores as probabilities or returns.",
            "Do not promote OpportunitySeeds beyond their screening_status.",
            "Do not turn hypothesis exploration priority into probability, expected return, or sizing.",
        ],
    }


def assert_compact_packet(packet, max_bytes=32768):
    def walk(value):
        if isinstance(value, dict):
            forbidden = FORBIDDEN_PACKET_KEYS.intersection(value)
            if forbidden:
                raise ValueError(f"forbidden continuation keys: {sorted(forbidden)}")
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(packet)
    size = len(json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    if size > max_bytes:
        raise ValueError(f"continuation packet too large: {size} > {max_bytes}")
    return size
