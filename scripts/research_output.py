#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compact deterministic user views for Trade Nothing v2 research state.

Raw agent payloads stay in state for audit and never enter these user views.
"""
import json

import crux_engine
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
        "catalyst_window": catalyst,
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
        "deferred_opportunities": opportunities[:10],
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
    return {
        "schema_version": SCHEMA_RESOLUTION,
        "output_type": "NON_FORMAL_RESOLUTION_MEMO",
        "formal_report_allowed": False,
        "topic": state.get("topic", ""),
        "decision_question": state.get("decision_question", ""),
        "horizon": state.get("horizon", ""),
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
        "convergence_reason": state.get("last_convergence", {}).get("reason", ""),
        "continuation_packet": build_continuation_packet(state),
        "limitations": [
            "该备忘录不是正式研究报告，也不是交易、收益、目标价或仓位指令。",
            "结构化 URL 尚不等于页面内容已通过快照与 claim 对齐。",
            "OpportunitySeed 是研究队列；被阻塞或待核的线索不得表述为可投资候选。",
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
        f"- 决策问题: {view['decision_question']} ｜ 视野: {view['horizon']}",
        f"- 覆盖: {view['coverage']['settled_cruxes']}/{view['coverage']['total_cruxes']} 条 crux 已形成可用方向；"
        f"{view['coverage']['never_contested_cruxes']} 条从未实际质证。",
        f"- 阻塞原因: {_text(view['convergence_reason']) or 'engine 尚未满足正式报告闸门。'}",
        "- 当前能做的决策仅是研究资源分配：保留已登记线索，优先补齐阻塞 crux；不得提升根命题或候选。",
        "",
        "## 已形成方向的 Crux",
    ]
    if not view["settled_cruxes"]:
        L.append("- 无。")
    for item in view["settled_cruxes"]:
        L.extend([
            f"### {item['id']} · {item['label']} — {_status_label(item['status'])}",
            f"- 最强多头: {_text(item['best_bull']) or '—'}",
            f"- 最强空头: {_text(item['best_bear']) or '—'}",
            f"- 监控 / 反证: {_text(item['monitor_anchor']) or '—'} / {_text(item['falsifier']) or '—'}",
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
            next_check = item["monitor_anchor"] or item["definition"] or "补充一级来源并形成双侧质证"
            L.append(
                f"| {index} | **{item['id']} {item['label']}** | {_status_label(item['status'])} | "
                f"{', '.join(item['gap_codes']) or 'UNSTABLE'} | {_text(next_check)} |"
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
