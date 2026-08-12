# -*- coding: utf-8 -*-
"""
Trade Nothing v0.16.0 — Compact Formal Report Renderer

Architecture:
  FIXED LAYER (脚本物理生成，数值勿改):
    - 结论 (research status, binding crux, debate-support scores)
    - A · 证明账本 (crux table, status, best_bull/bear, monitor_anchor, refs)
    - 证据仪表盘 (support trace, source counts, round count)
    - 引用列表

  COMPACT USER SYNTHESIS:
    - B · 决策摘要 uses only the accepted crux ledger and screened opportunity
      projections. Raw agent payloads remain in state for explicit audit only.

The support score is a debate-control heuristic, not a calibrated probability,
expected return, trade signal, or position-sizing input.
"""
import os, sys, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crux_engine
import research_agenda_engine
import material_change_engine
import hypothesis_engine
import tracking_engine
import landscape_engine
import market_map_engine
import research_kernel
import opportunity_engine
import candidate_gap_engine
import candidate_screen_engine
import claim_verification_engine
import temporal_contract
import execution_integrity
from version import __version__

_STATUS = {
    "RESOLVED_BULL": "🟢 当前证据偏多", "RESOLVED_BEAR": "🔴 当前证据偏空",
    "MONITORABLE": "🟡 可监控", "OPEN": "⚪ 未决", "PENDING": "⏳ 未检验",
}


def _cite_key(c):
    return crux_engine.citation_identity(c)


def _citation_quality(state):
    invalid = []
    valid_count = 0
    for cid, cx in state.get("cruxes", {}).items():
        for cit in cx.get("citations", []):
            item = {**cit, "crux": cid} if isinstance(cit, dict) else {"crux": cid, "value": cit}
            if crux_engine.valid_citation(cit):
                valid_count += 1
            else:
                invalid.append(item)
    for seed in state.get("opportunity_seeds", []):
        if not isinstance(seed, dict):
            continue
        for cit in seed.get("evidence", []):
            item = ({**cit, "crux": f"OpportunitySeed:{seed.get('seed_id', '?')}"}
                    if isinstance(cit, dict) else
                    {"crux": f"OpportunitySeed:{seed.get('seed_id', '?')}", "value": cit})
            if crux_engine.valid_citation(cit):
                valid_count += 1
            else:
                invalid.append(item)
    for screen in state.get("candidate_screens", []):
        if not isinstance(screen, dict):
            continue
        for dimension, combined in screen.get("dimensions", {}).items():
            for side in ("analyst", "skeptic"):
                assessment = combined.get(side, {}) if isinstance(combined, dict) else {}
                for cit in assessment.get("evidence", []):
                    item = ({**cit, "crux": f"CandidateScreen:{screen.get('screen_id', '?')}:{dimension}"}
                            if isinstance(cit, dict) else
                            {"crux": f"CandidateScreen:{screen.get('screen_id', '?')}:{dimension}",
                             "value": cit})
                    if crux_engine.valid_citation(cit):
                        valid_count += 1
                    else:
                        invalid.append(item)
    return {"valid_count": valid_count, "invalid": invalid}


def _clean(value):
    return " ".join(str(value or "").split()) or "—"


def _execution_round_label(runtime):
    return execution_integrity.round_label(
        (runtime or {}).get("execution_integrity") or {}
    )


def _attach_execution_marker(markdown, audit):
    """Embed one machine-readable receipt without displacing the report title."""
    lines = str(markdown or "").splitlines()
    receipt_marker = execution_integrity.marker(audit)
    if not lines:
        return receipt_marker + "\n"
    if lines[0] == "---" and len(lines) > 1 and lines[1].startswith(
        "<!-- FACTS_BOX_START"
    ):
        lines.insert(2, receipt_marker)
    else:
        lines.insert(1, receipt_marker)
    return "\n".join(lines).rstrip() + "\n"


def _exploration_history_lines(
    exploration, heading="### 已执行探索与负知识",
    include_control_history=False,
):
    history = [
        item
        for item in exploration.get("authorized_action_history", [])
        if isinstance(item, dict)
    ]
    lines = [heading]
    if not history:
        lines.append("- 尚无经显式授权并完成的探索动作。")
    for item in history[-5:]:
        receipt = item.get("execution_receipt") or {}
        documents = [
            document
            for document in receipt.get("document_receipts", [])
            if isinstance(document, dict)
        ]
        document_text = "；".join(
            f"`{document.get('document_id', '—')}` "
            f"{_clean(document.get('source'))} "
            f"{document.get('date', '—')} "
            f"{document.get('url', '—')}"
            for document in documents
        ) or "无文档回执"
        lines.extend([
            f"- `{item.get('action_id', '—')}` / "
            f"`{item.get('execution_status', 'UNKNOWN')}` / "
            f"假说 `{item.get('hypothesis_id', '—')}`："
            f"route `{item.get('route_id') or receipt.get('route_id') or '—'}`；"
            f"proxy `{item.get('proxy_id') or receipt.get('proxy_id') or '—'}`；"
            f"来源类 {_clean(item.get('source_class'))}；"
            f"查询 {_clean(item.get('bounded_query'))}；"
            f"停止 {_clean(receipt.get('stop_reason'))}；"
            f"assurance="
            f"`{item.get('authorization_assurance') or '—'}`。",
            f"  - 回执: {document_text}；result_sha256="
            f"`{receipt.get('result_sha256', '—')}`；"
            f"negative_knowledge="
            f"{_clean(item.get('negative_knowledge'))}；"
            f"planned={_clean(item.get('planned_proxy') or receipt.get('planned_proxy'))}；"
            f"observed={_clean(item.get('observation') or receipt.get('observation'))}。",
        ])
    if include_control_history:
        terminal = [
            item
            for item in exploration.get("terminal_action_history", [])
            if isinstance(item, dict)
        ]
        lines.append("#### Host 探索动作终态")
        if not terminal:
            lines.append("- 尚无已关闭的 host 探索动作。")
        for item in terminal:
            lines.append(
                f"- `{item.get('action_id', '—')}` / "
                f"`{item.get('status', 'UNKNOWN')}` / "
                f"route `{item.get('route_id') or '—'}`："
                f"action_as_of={item.get('as_of_date') or '—'}；"
                f"source_class={_clean(item.get('source_class'))}；"
                f"query={_clean(item.get('bounded_query'))}；"
                f"reason={_clean(item.get('reason'))}；"
                f"assurance="
                f"`{item.get('authorization_assurance') or '—'}`；"
                f"result_sha256=`{item.get('result_sha256') or '—'}`；"
                f"result_ingested={item.get('result_ingested', False)}；"
                f"proxy_ingested={item.get('proxy_ingested', False)}；"
                f"automatic_retry={item.get('automatic_retry', False)}。"
            )
        designs = [
            item
            for item in exploration.get("design_history", [])
            if isinstance(item, dict)
        ]
        lines.append("#### Typed design 历史")
        if not designs:
            lines.append("- 尚无 typed design 写入。")
        for item in designs:
            lines.append(
                f"- `{item.get('design_id', '—')}` / "
                f"假说 `{item.get('hypothesis_id', '—')}` / "
                f"`{item.get('action_code', 'UNKNOWN')}`："
                f"{_clean(item.get('design_note'))}；"
                f"state `{item.get('state_before', '—')}` → "
                f"`{item.get('state_after', '—')}`。"
            )
        closed_routes = [
            item
            for item in exploration.get("closed_routes", [])
            if isinstance(item, dict)
        ]
        lines.append("#### 已关闭诊断路线")
        if not closed_routes:
            lines.append("- 尚无已关闭诊断路线。")
        for item in closed_routes:
            lines.append(
                f"- `{item.get('route_id', '—')}` / action "
                f"`{item.get('action_id', '—')}` / "
                f"`{item.get('execution_status', 'UNKNOWN')}`："
                f"query={_clean(item.get('bounded_query'))}；"
                f"stop={_clean(item.get('stop_reason'))}。"
            )
    return lines


RELATION_LABELS = {
    "DIRECT_WINNER": "直接受益路径",
    "SUBSTITUTE_WINNER": "替代路径",
    "COMPETITOR_WINNER": "竞争者受益路径",
    "BOTTLENECK_OWNER": "瓶颈所有者",
    "INFRA_ASSET_OWNER": "基础资产所有者",
    "SECOND_ORDER": "二阶研究线索",
    "SHORT_CANDIDATE": "反向风险暴露",
}
SCREEN_CORE_ORDER = ("ECONOMIC_EXPOSURE", "EXPECTATION_GAP", "TRADABILITY", "CATALYST")
SCREEN_SOURCE_GATES = {
    "total_unique_urls",
    "primary_unique_urls",
    "independent_source_orgs",
    "analyst_source_breadth",
    "skeptic_source_breadth",
}


def _relation_label(value):
    cleaned = _clean(value).upper()
    return RELATION_LABELS.get(cleaned, cleaned or "—")


def _screen_gap_summary(screen):
    """Project cheap-first gaps into the first core stop and its consequences."""
    if not isinstance(screen, dict) or not screen:
        return {}
    dimensions = screen.get("dimensions", {}) if isinstance(screen.get("dimensions"), dict) else {}
    primary = next((
        dimension for dimension in SCREEN_CORE_ORDER
        if dimensions.get(dimension, {}).get("state") != "SUPPORTED"
    ), "")
    primary_item = dimensions.get(primary, {}) if primary else {}
    dependent = [
        dimension for dimension in candidate_screen_engine.DIMENSIONS
        if dimension != primary and dimensions.get(dimension, {}).get("state") != "SUPPORTED"
    ]
    dimension_names = set(candidate_screen_engine.DIMENSIONS)
    non_dimension_gaps = [gap for gap in screen.get("gaps", []) if gap not in dimension_names]
    source_gaps = [gap for gap in non_dimension_gaps if gap in SCREEN_SOURCE_GATES]
    process_gaps = [gap for gap in non_dimension_gaps if gap not in SCREEN_SOURCE_GATES]
    return {
        "primary": primary,
        "analyst_answer": primary_item.get("analyst", {}).get("answer", "UNKNOWN"),
        "skeptic_answer": primary_item.get("skeptic", {}).get("answer", "UNKNOWN"),
        "dependent": dependent,
        "source_gaps": source_gaps,
        "process_gaps": process_gaps,
    }


def _cell(value):
    return _clean(value).replace("|", "\\|")


def _phrase(value):
    return _clean(value).rstrip("。；;，, ")


def _phase_status_text(value):
    """Translate control-plane phase states for the reader-facing report."""
    status = _clean(value)
    return {
        "STALE_CONTEXT": "待按当前快照重算",
    }.get(status, status)


def _extract_raw_material(state):
    """Extract ALL agent raw outputs across all rounds for the dynamic layer."""
    material = []
    for rnd in state.get("rounds", []):
        r = rnd.get("round", "?")
        entry = {"round": r, "detective": {}, "inquisitor": {}, "judge_rationale": {}}

        # Detective raw output
        det = rnd.get("detective_raw", {})
        if det and det != {"_": "det"}:
            entry["detective"] = {
                "variant_perception": det.get("variant_perception", ""),
                "bull_thesis": det.get("bull_thesis", ""),
                "market_consensus": det.get("market_consensus", ""),
                "evidence_chain": det.get("evidence_chain", []),
                "crux_evidence": det.get("crux_evidence", []),
                "rebuttals": det.get("rebuttals", []),
                "new_dimension": det.get("new_dimension_this_round", ""),
                "supply_chain_map": det.get("supply_chain_map", ""),
            }

        # Inquisitor raw output
        inq = rnd.get("inquisitor_raw", {})
        if inq and inq != {"_": "inq"}:
            entry["inquisitor"] = {
                "death_path": inq.get("premortem_death_path", {}),
                "lethal_attacks": inq.get("lethal_attack_vectors", []),
                "crux_attacks": inq.get("crux_attacks", []),
                "new_attack_dimension": inq.get("new_attack_dimension_this_round", ""),
                "kill_switch": inq.get("recommended_kill_switch", {}),
            }

        # Judge rationale per crux
        judge = rnd.get("judge_raw", rnd.get("signals", {}))
        if isinstance(judge, dict):
            signals = judge.get("crux_signals", judge)
            for cid, sig in signals.items():
                if isinstance(sig, dict) and sig.get("rationale"):
                    entry["judge_rationale"][cid] = {
                        "signal": sig.get("signal", 0),
                        "rationale": sig.get("rationale", ""),
                    }

        if entry["detective"] or entry["inquisitor"] or entry["judge_rationale"]:
            material.append(entry)
    return material


def _candidate_next_action(candidate_state, blockers=None):
    blockers = set(blockers or [])
    if (candidate_state == opportunity_engine.EVIDENCE_BACKED
            and blockers == {"insufficient_independent_seed_sources"}):
        return (
            "ADD_INDEPENDENT_SOURCE",
            "补充第二个独立来源组织；不得用同一发布者的另一条 URL 冒充交叉验证。",
        )
    return {
        opportunity_engine.VERIFIED_FOR_HUMAN: (
            "HUMAN_REVIEW_PROMOTION_PACKET",
            "人工审阅升级包；若认可，建立一条全新的 DRAFT Thesis。",
        ),
        opportunity_engine.THESIS_CANDIDATE: (
            "RUN_CLAIM_VERIFICATION",
            "只核验决定晋级的最小 claim 集，不重跑整份研究。",
        ),
        opportunity_engine.READY: (
            "RUN_CANDIDATE_SCREEN",
            "运行隔离的 Candidate Analyst / Skeptic 双边筛选。",
        ),
        opportunity_engine.WATCHLIST: (
            "CLOSE_SCREEN_GAPS_OR_WAIT",
            "补齐明确的筛选缺口，或等待已定义催化；不得建立 Thesis。",
        ),
        opportunity_engine.REJECTED: (
            "ARCHIVE_REJECTION",
            "保留否决原因；除非出现新事实，不得复活原 seed。",
        ),
        opportunity_engine.EVIDENCE_BACKED: (
            "COMPLETE_SEED_CONTRACT",
            "补齐经济暴露、预期差、定价锚、催化或反证；当前只是一条线索。",
        ),
    }.get(candidate_state, ("STOP_UNKNOWN_STATE", "停止晋级并检查候选状态。"))


def _trading_vehicle(seed):
    asset_type = _clean(seed.get("asset_type")) or "UNSPECIFIED_ASSET"
    ticker = _clean(seed.get("ticker")) if seed.get("ticker") else ""
    if ticker:
        return f"{asset_type} / {ticker}"
    return f"{asset_type} / 未给出可直接交易代码"


def _screen_dimension_summary(screen, dimension):
    dimensions = screen.get("dimensions") if isinstance(screen, dict) else None
    combined = dimensions.get(dimension) if isinstance(dimensions, dict) else None
    if not isinstance(combined, dict):
        return "UNSCREENED：尚未由双边 CandidateScreen 验证"
    findings = []
    for side, label in (("analyst", "Analyst"), ("skeptic", "Skeptic")):
        item = combined.get(side) if isinstance(combined.get(side), dict) else {}
        answer = _clean(item.get("answer")) or "UNKNOWN"
        finding = _clean(item.get("finding"))
        findings.append(f"{label} {answer}" + (f"（{finding}）" if finding else ""))
    return f"{_clean(combined.get('state')) or 'INCOMPLETE'}：" + "；".join(findings)


def _candidate_cards(state):
    latest_screens = candidate_screen_engine.latest_by_seed(state)
    seed_by_id = {
        seed.get("seed_id"): seed for seed in state.get("opportunity_seeds", [])
        if isinstance(seed, dict) and seed.get("seed_id")
    }
    latest_screen_by_entity = {}
    for seed_id, screen in latest_screens.items():
        seed = seed_by_id.get(seed_id)
        if not seed:
            continue
        identity = opportunity_engine.entity_identity(seed)
        current = latest_screen_by_entity.get(identity)
        order = (str(screen.get("as_of_date") or ""), str(screen.get("screen_id") or ""))
        current_order = (
            str((current or {}).get("as_of_date") or ""),
            str((current or {}).get("screen_id") or ""),
        )
        if current is None or order >= current_order:
            latest_screen_by_entity[identity] = screen

    cards = []
    for entity in opportunity_engine.entity_views(state):
        seed = entity.get("representative_seed") or {}
        if not seed.get("seed_id"):
            continue
        promotion = opportunity_engine.promotion_assessment(state, seed)
        candidate_state = promotion["candidate_state"]
        screen = (
            latest_screens.get(seed.get("seed_id"))
            or latest_screen_by_entity.get(entity.get("entity_identity"))
            or {}
        )
        action_code, action_text = _candidate_next_action(
            candidate_state, promotion["blocking_reasons"]
        )
        gap_task = candidate_gap_engine.open_task_for_seed(
            state, str(seed.get("seed_id") or "")
        )
        gap_resolution = candidate_gap_engine.latest_resolution_for_seed(
            state, str(seed.get("seed_id") or "")
        )
        if gap_task:
            action_code = "EXECUTE_CANDIDATE_GAP_TASK"
            action_text = (
                f"执行 {gap_task['task_id']}：{gap_task['target_claim']}；"
                f"最多 {gap_task['search_budget']} 次搜索，失败时按任务条件终止。"
            )
        elif gap_resolution and gap_resolution.get("status") == "SOURCE_EXHAUSTED":
            action_code = "WAIT_FOR_NEW_INDEPENDENT_SOURCE"
            action_text = "有界搜索已耗尽；等待新来源或新事实，不得重复扩写同一查询。"
        elif gap_resolution and gap_resolution.get("status") == "WAITING_EVENT":
            action_code = "WAIT_FOR_DEFINED_EVENT"
            action_text = gap_resolution.get("reason") or "等待任务定义的观察事件。"
        screen_gaps = _screen_gap_summary(screen)
        if candidate_state == opportunity_engine.WATCHLIST and screen_gaps.get("primary"):
            action_text = (
                f"优先补齐 {screen_gaps['primary']}（Analyst "
                f"{screen_gaps['analyst_answer']} / Skeptic {screen_gaps['skeptic_answer']}）；"
                "其余 UNKNOWN 是 cheap-first 停止后的派生缺口，不得并列成独立研究任务。"
                "只有出现新观察日与新证据后，才用显式 seed_id 做 gap-directed 重筛；"
                "同日不同提交不得覆盖旧记录。"
            )
        cards.append({
            "entity_id": entity.get("entity_id"),
            "seed_id": seed.get("seed_id"),
            "candidate": _clean(seed.get("candidate")),
            "ticker": _clean(seed.get("ticker")) if seed.get("ticker") else "",
            "asset_type": _clean(seed.get("asset_type")),
            "relation_type": _clean(seed.get("relation_type")),
            "relation_label": _relation_label(seed.get("relation_type")),
            "origin_crux": _clean(seed.get("origin_crux")),
            "origin_hypothesis_id": _clean(seed.get("origin_hypothesis_id")),
            "landscape_path_id": _clean(seed.get("landscape_path_id")),
            "candidate_state": candidate_state,
            "promotion_eligibility": promotion["promotion_eligibility"],
            "blocking_reasons": promotion["blocking_reasons"],
            "economic_exposure": _clean(seed.get("economic_exposure")),
            "expectation_gap": _clean(seed.get("why_market_may_miss")),
            "pricing_anchor": opportunity_engine.pricing_anchor_text(seed.get("pricing_anchor")),
            "trading_vehicle": _trading_vehicle(seed),
            "tradability_assessment": _screen_dimension_summary(screen, "TRADABILITY"),
            "catalyst": _clean(seed.get("catalyst")),
            "falsifier": _clean(seed.get("falsifier")),
            "screen_status": screen.get("status", "UNSCREENED"),
            "claim_verification_status": screen.get(
                "claim_verification_status", "NOT_APPLICABLE"
            ),
            "isolation_status": screen.get("isolation_status", "unverified"),
            "screen_gap_summary": screen_gaps,
            "path_count": len(entity.get("paths", [])),
            "path_analysis": opportunity_engine.path_analysis(state, seed),
            "odds_summary": opportunity_engine.odds_summary(seed),
            "scenario_paths": seed.get("scenario_paths") or {},
            "next_action_code": action_code,
            "next_action": action_text,
            "gap_task": gap_task,
            "gap_resolution": gap_resolution,
        })
    priority = {
        opportunity_engine.VERIFIED_FOR_HUMAN: 0,
        opportunity_engine.THESIS_CANDIDATE: 1,
        opportunity_engine.READY: 2,
        opportunity_engine.WATCHLIST: 3,
        opportunity_engine.EVIDENCE_BACKED: 4,
        opportunity_engine.REJECTED: 5,
    }
    cards.sort(key=lambda item: (
        priority.get(item["candidate_state"], 99),
        item["candidate"],
        item["seed_id"],
    ))
    return cards


def _evidence_matrix(state, report_data, exploration):
    rows = []

    def add(citation, track, direction, binding_id, binding_label):
        if not isinstance(citation, dict) or not crux_engine.valid_citation(citation):
            return
        identity = "|".join([
            track,
            str(binding_id or ""),
            str(citation.get("url") or ""),
            str(citation.get("claim") or ""),
        ])
        rows.append({
            "evidence_id": "EV-" + hashlib.sha256(
                identity.encode("utf-8")
            ).hexdigest()[:12].upper(),
            "track": track,
            "direction": direction,
            "binding_id": str(binding_id or ""),
            "binding_label": _clean(binding_label),
            "claim": _clean(citation.get("claim")),
            "source": _clean(citation.get("source")),
            "date": _clean(citation.get("date")),
            "url": _clean(citation.get("url")),
            "source_tier": _clean(citation.get("source_tier")),
        })

    for crux in report_data.get("cruxes", []):
        status = str(crux.get("status") or "").upper()
        direction = (
            "SUPPORTS"
            if status == "RESOLVED_BULL"
            else "CONTRADICTS"
            if status == "RESOLVED_BEAR"
            else "CONTEXT"
        )
        for citation in crux.get(
            "valid_citations",
            crux.get("citations", []),
        ):
            add(
                citation,
                "FORMAL_CRUX",
                direction,
                crux.get("id"),
                crux.get("label"),
            )
    for seed in state.get("opportunity_seeds", []):
        if not isinstance(seed, dict):
            continue
        for citation in seed.get("evidence", []):
            add(
                citation,
                "CANDIDATE_PATH",
                "SUPPORTS_PATH",
                seed.get("seed_id"),
                seed.get("candidate"),
            )
    for hypothesis in exploration.get("hypotheses", []):
        for proxy in hypothesis.get("proxy_trails", []):
            for citation in proxy.get("evidence", []):
                add(
                    citation,
                    "EXPLORATION_PROXY",
                    proxy.get("direction", "AMBIGUOUS"),
                    hypothesis.get("hypothesis_id"),
                    proxy.get("proxy"),
                )
    deduplicated = {
        (
            item["track"],
            item["binding_id"],
            item["url"],
            item["claim"],
        ): item
        for item in rows
    }
    ordered = sorted(
        deduplicated.values(),
        key=lambda item: (
            item["track"],
            item["binding_id"],
            item["date"],
            item["evidence_id"],
        ),
    )
    direction_counts = {}
    for item in ordered:
        direction = item["direction"]
        direction_counts[direction] = direction_counts.get(direction, 0) + 1
    return {
        "schema_version": "trade-nothing.evidence-matrix.v1",
        "row_count": len(ordered),
        "direction_counts": direction_counts,
        "rows": ordered,
        "boundary": (
            "Each row binds to one crux, candidate path, or ProxyTrail; "
            "exploration evidence does not become formal evidence."
        ),
    }


def build_report_view_model(state):
    """Build the deterministic user-facing projection used by every report view.

    The view model contains no raw role payloads. It keeps root-thesis truth,
    candidate maturity, Research Agenda progress, and the next legal action
    separate. Renderers may give bounded conditional research or market advice,
    but cannot turn it into an order, position, target return, or execution.

    An unconverged run still projects a view model.  Its `research_grade` states
    what the run did not establish; suppressing the projection entirely only
    moved report writing outside the engine.
    """
    opportunity_engine.refresh_candidate_states(state)
    rd = crux_engine.report_data(state)
    verdict = rd.get("research_verdict", {})
    cards = _candidate_cards(state)
    landscape = landscape_engine.summary(state)
    exploration = hypothesis_engine.report_view(state, limit=7)
    scenario_paths = hypothesis_engine.scenario_view(state)
    candidate_map = market_map_engine.report_view(state)
    market_bridge = candidate_map.get("market_bridge", {})
    research_agenda = research_agenda_engine.report_view(state)
    research_control = material_change_engine.augment_research_control(
        state, research_agenda.get("research_control", {})
    )
    research_agenda["research_control"] = research_control
    material_change = material_change_engine.report_view(state)
    evidence_plane = research_kernel.evidence_plane_counts(
        research_agenda.get("evidence_items", [])
    )
    agenda_native = research_agenda_engine.is_agenda_native(state)
    legacy_evidence_counts = crux_engine.evidence_counts(state)
    survived = [
        item for item in rd["cruxes"] if item.get("status") == "RESOLVED_BULL"
    ]
    falsified = [
        item for item in rd["cruxes"] if item.get("status") == "RESOLVED_BEAR"
    ]
    monitorable = [
        item for item in rd["cruxes"] if item.get("status") == "MONITORABLE"
    ]
    focus_id = rd.get("binding_crux") or rd.get("focus_crux")
    focus = next((item for item in rd["cruxes"] if item["id"] == focus_id), None)
    if cards:
        next_action_code = cards[0]["next_action_code"]
        next_action = cards[0]["next_action"]
        next_action_candidate = cards[0]["candidate"]
    elif verdict.get("actionability") == "MONITOR":
        next_action_code = "WAIT_FOR_MONITOR"
        next_action = "等待已定义的监控事件；在新事实出现前停止追加搜索。"
        next_action_candidate = ""
    else:
        next_action_code = "STOP_NO_PROMOTABLE_CANDIDATE"
        next_action = "停止候选晋级；本轮没有可进入下一阶段的证据路径。"
        next_action_candidate = ""
    catalyst = (focus or {}).get("catalyst_window", {})
    trigger = (
        catalyst.get("event") if isinstance(catalyst, dict) else ""
    ) or (focus or {}).get("monitor_anchor") or "未定义"
    falsifier = (focus or {}).get("falsifier") or "未定义"
    counts = {
        "lead_count": len(cards),
        "ready_for_screening_count": sum(
            card["candidate_state"] == opportunity_engine.READY for card in cards
        ),
        "screened_count": sum(card["screen_status"] != "UNSCREENED" for card in cards),
        "thesis_candidate_count": sum(
            card["candidate_state"] == opportunity_engine.THESIS_CANDIDATE for card in cards
        ),
        "verified_for_human_count": sum(
            card["candidate_state"] == opportunity_engine.VERIFIED_FOR_HUMAN for card in cards
        ),
        "watchlist_count": sum(
            card["candidate_state"] == opportunity_engine.WATCHLIST for card in cards
        ),
        "rejected_count": sum(
            card["candidate_state"] == opportunity_engine.REJECTED for card in cards
        ),
    }
    formal_action = {
        "code": next_action_code,
        "candidate": next_action_candidate,
        "instruction": next_action,
    }
    temporal = temporal_contract.from_state(state)
    hypotheses = exploration.get("hypotheses", [])
    exploration_gap = {
        "status": (
            "AVAILABLE"
            if hypotheses
            else "DECLARED_BUT_EMPTY"
            if isinstance(state.get("hypothesis_ledger"), dict)
            or isinstance(state.get("landscape_map"), dict)
            else "NOT_RECORDED_IN_ARCHIVED_ARTIFACT"
        ),
        "is_method_gap": not bool(hypotheses),
        "message": (
            "Auditable hypotheses and ProxyTrails are available."
            if hypotheses
            else
            "No auditable exploration hypothesis was recorded. This is a method "
            "gap, not evidence that no adjacent opportunity exists."
        ),
    }
    execution_audit = execution_integrity.audit_state(state)
    return {
        "schema_version": "trade-nothing.report-view-model.v2",
        "topic": _clean(state.get("topic")),
        "decision_question": _clean(state.get("decision_question")),
        "horizon": _clean(state.get("horizon")),
        "as_of_date": _clean(
            state.get("frame_contract", {}).get("as_of_date")
            or state.get("as_of_date")
        ),
        "forecast_target_date": temporal["forecast_target_date"],
        "temporal_contract": temporal,
        "question_type": verdict.get("question_type", rd.get("question_type", "CONJUNCTIVE")),
        "framing": {
            "quality_status": _clean(
                state.get("frame_contract", {}).get("quality_status")
            ),
            "premise_audit": [
                dict(item) for item in state.get("frame_contract", {}).get("premise_audit", [])
                if isinstance(item, dict)
            ],
            "artifact_policy": dict(
                state.get("frame_contract", {}).get("artifact_policy") or {}
            ),
        },
        "verdict": {
            "edge_state": verdict.get("edge_state", "INSUFFICIENT_EVIDENCE"),
            "evidence_direction": verdict.get("evidence_direction", "UNDETERMINED"),
            "actionability": verdict.get("actionability", "NONE"),
            "reason_code": verdict.get("reason_code", "LEGACY_STATE"),
        },
        "root_thesis": {
            "survived": survived,
            "falsified": falsified,
            "monitorable": monitorable,
            "focus": focus,
        },
        "candidate_counts": counts,
        "candidate_cards": cards,
        "tracking_rows": tracking_engine.active_tracked(state),
        "landscape_map": landscape,
        "hypothesis_exploration": exploration,
        "exploration_gap": exploration_gap,
        "research_allocation": exploration.get("research_allocation", []),
        "evidence_matrix": _evidence_matrix(state, rd, exploration),
        "formal_action": formal_action,
        "exploration_action": exploration["exploration_action"],
        "scenario_paths": scenario_paths,
        "candidate_map": candidate_map,
        "market_bridge": market_bridge,
        "research_agenda": research_agenda,
        "evidence_plane": evidence_plane,
        "research_control": research_control,
        "material_change": material_change,
        # Backwards-compatible alias. Formal action remains the only candidate
        # promotion action; exploration_action has research-only authority.
        "next_action": formal_action,
        "change_trigger": {
            "focus_crux": focus_id or "",
            "event": _clean(trigger),
            "falsifier": _clean(falsifier),
        },
        "runtime": {
            "isolation_status": state.get("runtime_contract", {}).get(
                "isolation_status", "unverified"
            ),
            "round_count": len(state.get("rounds", [])),
            "execution_integrity": execution_audit,
            "unique_source_count": (
                evidence_plane["unique_source_url_count"]
                if agenda_native else rd.get("n_unique_sources", 0)
            ),
            "independent_publisher_count": (
                evidence_plane["independent_publisher_count"]
                if agenda_native else legacy_evidence_counts.get("unique_publishers", 0)
            ),
            "primary_source_count": (
                evidence_plane["primary_source_count"]
                if agenda_native else rd.get("n_primary_sources", 0)
            ),
            "evidence_plane": evidence_plane,
            "legacy_crux_audit": {
                "unique_source_url_count": rd.get("n_unique_sources", 0),
                "independent_publisher_count": legacy_evidence_counts.get(
                    "unique_publishers", 0
                ),
                "primary_source_count": rd.get("n_primary_sources", 0),
            },
        },
        "research_grade": crux_engine.research_grade(state),
    }


def _render_audit(state, include_title=True):
    opportunity_engine.refresh_candidate_states(state)
    rd = crux_engine.report_data(state)
    landscape = landscape_engine.summary(state)
    topic = state.get("topic", "")
    agenda_native = research_agenda_engine.is_agenda_native(state)
    agenda_evidence_counts = research_kernel.evidence_plane_counts(
        state.get("research_agenda", {}).get("evidence_items", [])
    )

    # ═══ Build citation registry (deduped, numbered) ═══
    refs, ref_no = [], {}
    crux_refs = {}
    opportunity_refs = {}
    hypothesis_refs = {}
    screen_dimension_refs = {}
    latest_screens = candidate_screen_engine.latest_by_seed(state)
    seed_by_id = {
        seed.get("seed_id"): seed for seed in state.get("opportunity_seeds", [])
        if isinstance(seed, dict) and seed.get("seed_id")
    }
    latest_screen_by_entity = {}
    for seed_id, screen in latest_screens.items():
        seed = seed_by_id.get(seed_id)
        if not seed:
            continue
        identity = opportunity_engine.entity_identity(seed)
        current = latest_screen_by_entity.get(identity)
        if not current or screen.get("as_of_date", "") >= current.get("as_of_date", ""):
            latest_screen_by_entity[identity] = screen
    latest_claims = claim_verification_engine.latest_verifications(state)
    quality = _citation_quality(state)
    exploration_count = hypothesis_engine.summary(state).get(
        "hypothesis_count", 0
    )
    exploration = hypothesis_engine.report_view(
        state, limit=exploration_count
    )
    for c in rd["cruxes"]:
        nums = []
        for cit in c.get("valid_citations", c["citations"]):
            if not crux_engine.valid_citation(cit):
                continue
            k = _cite_key(cit)
            if k not in ref_no:
                ref_no[k] = len(refs) + 1
                refs.append(cit)
            nums.append(ref_no[k])
        crux_refs[c["id"]] = sorted(set(nums))

    # Opportunity evidence survives independently of the root-thesis verdict.
    opportunities = []
    for seed in state.get("opportunity_seeds", []):
        if not isinstance(seed, dict) or not str(seed.get("candidate", "")).strip():
            continue
        effective = opportunity_engine.effective_seed(state, seed)
        valid = [c for c in effective.get("evidence", []) if crux_engine.valid_citation(c)]
        if not valid:
            continue
        item = dict(effective)
        item["evidence"] = valid
        item["maturity"] = opportunity_engine.evidence_maturity(item)
        assessment = opportunity_engine.assess_seed(state, item)
        item["screening_status"] = assessment["screening_status"]
        item["screening_blockers"] = assessment["blockers"]
        item["promotion"] = opportunity_engine.promotion_assessment(state, item)
        item["candidate_state"] = item["promotion"]["candidate_state"]
        item["entity_id"] = opportunity_engine.entity_id(item)
        item["_screen"] = (
            latest_screens.get(item.get("seed_id"))
            or latest_screen_by_entity.get(opportunity_engine.entity_identity(item))
        )
        item["_report_key"] = item.get("seed_id") or f"opportunity-{len(opportunities)}"
        nums = []
        for cit in valid:
            k = _cite_key(cit)
            if k not in ref_no:
                ref_no[k] = len(refs) + 1
                refs.append(cit)
            nums.append(ref_no[k])
        opportunity_refs[item["_report_key"]] = sorted(set(nums))
        screen = item.get("_screen")
        if screen:
            for dimension, combined in screen.get("dimensions", {}).items():
                dimension_nums = []
                for side in ("analyst", "skeptic"):
                    assessment = combined.get(side, {}) if isinstance(combined, dict) else {}
                    for cit in assessment.get("evidence", []):
                        if not crux_engine.valid_citation(cit):
                            continue
                        k = _cite_key(cit)
                        if k not in ref_no:
                            ref_no[k] = len(refs) + 1
                            refs.append(cit)
                        dimension_nums.append(ref_no[k])
                screen_dimension_refs[(screen.get("screen_id"), dimension)] = sorted(set(dimension_nums))
        opportunities.append(item)
    for hypothesis in exploration.get("hypotheses", []):
        hypothesis_id = hypothesis.get("hypothesis_id", "?")
        observation_nums = []
        for cit in hypothesis.get("observation_evidence", []):
            if not crux_engine.valid_citation(cit):
                continue
            key = _cite_key(cit)
            if key not in ref_no:
                ref_no[key] = len(refs) + 1
                refs.append(cit)
            observation_nums.append(ref_no[key])
        hypothesis_refs[(hypothesis_id, "OBSERVATION")] = sorted(
            set(observation_nums)
        )
        for proxy in hypothesis.get("proxy_trails", []):
            nums = []
            for cit in proxy.get("evidence", []):
                if not crux_engine.valid_citation(cit):
                    continue
                key = _cite_key(cit)
                if key not in ref_no:
                    ref_no[key] = len(refs) + 1
                    refs.append(cit)
                nums.append(ref_no[key])
            hypothesis_refs[
                (hypothesis_id, proxy.get("proxy_id", "?"))
            ] = sorted(set(nums))
    entity_views = {
        item["representative_seed_id"]: item
        for item in opportunity_engine.entity_views(state)
    }
    opportunities = [item for item in opportunities if item.get("seed_id") in entity_views]
    for item in opportunities:
        item["_entity_view"] = entity_views[item["seed_id"]]
    screen_priority = {"THESIS_CANDIDATE": 0, "WATCHLIST": 2, "REJECTED": 3}
    opportunity_status_priority = {
        opportunity_engine.READY: 0,
        opportunity_engine.NEEDS_CATALYST: 1,
        opportunity_engine.BLOCKED_ROOT: 2,
        opportunity_engine.BLOCKED_ORIGIN: 3,
        opportunity_engine.OUT_OF_HORIZON: 4,
        opportunity_engine.EVIDENCE_BACKED: 5,
    }
    opportunities.sort(key=lambda s: (
        screen_priority.get((s.get("_screen") or {}).get("status"), 1),
        opportunity_status_priority.get(s.get("screening_status"), 99),
        {"VERIFIED": 0, "PARTIALLY_VERIFIED": 1, "PENDING": 2, "CONTRADICTED": 3}.get(
            (s.get("_screen") or {}).get("claim_verification_status", "PENDING"), 2
        ),
        s.get("first_seen_round", 0),
        _clean(s.get("candidate")),
    ))

    # ═══ Debate-support trace (not a calibrated probability) ═══
    n_rounds = len(state.get("rounds", []))
    execution_audit = execution_integrity.audit_state(state)
    execution_label = execution_integrity.round_label(execution_audit)
    dt = state.get("decision_trace", [])
    is_universe = rd.get("question_type") == "UNIVERSE_SEARCH"
    trace_str = " → ".join(
        f"R{d['round']}: {crux_engine.safe_decision_label(d.get('decision'))}"
        + ("" if is_universe else
           f"({int(d.get('support_weakest', d['p_weakest'])*100)}/100)")
        for d in dt
    ) if dt else "—"

    support_w = (rd.get("support_weakest") or 0.5)
    support_m = (rd.get("support_mean") or 0.5)
    verdict = rd.get("research_verdict", {})

    L = []

    # ─────────── FIXED LAYER ───────────
    if include_title:
        L.append(f"# Trade Nothing v{__version__} 深度研究报告 — {topic}")
        L.append(f"> 决策问题: {state.get('decision_question','')} ｜ 视野: {state.get('horizon','')}")
        L.append(f"> 假设种子: {state.get('thesis_seed','')}")
        L.append("")

    # 结论
    L.append("## 🧭 研究状态")
    L.append(f"- 题型: **{verdict.get('question_type', rd.get('question_type', 'CONJUNCTIVE'))}**")
    L.append(f"- Edge: **{verdict.get('edge_state', 'INSUFFICIENT_EVIDENCE')}** ｜ "
             f"证据方向: **{verdict.get('evidence_direction', 'UNDETERMINED')}** ｜ "
             f"可行动性: **{verdict.get('actionability', 'NONE')}**")
    L.append(f"- 判定依据: `{verdict.get('reason_code', 'LEGACY_STATE')}`。"
             "`NO_EDGE` 只表示未发现可利用预期差，不等于 AVOID、SHORT，也不是交易指令。")
    if is_universe:
        L.append("- 收敛单位: **Landscape 双边覆盖 + 候选收割静默**；"
                 "异质候选证据不生成全局 bull/bear 支持度。")
    elif rd.get("binding_crux"):
        L.append(f"- 约束性 crux (binding): **{rd['binding_crux']}** ｜ "
                 f"最弱辩论支持度 {int(support_w*100)}/100 ｜ 均值支持度 {int(support_m*100)}/100")
    else:
        L.append(f"- 聚合规则: **{rd.get('aggregation_rule', 'LOGIC_GRAPH_MULTI_PATH')}** ｜ "
                 f"当前研究焦点 {rd.get('focus_crux') or '—'} ｜ 最低路径支持度 {int(support_w*100)}/100；"
                 "多路径题型不存在可否定全局的单一 binding crux。")
    if agenda_native:
        L.append(
            f"- 执行真实性: {execution_label} ｜ Agenda evidence: "
            f"{agenda_evidence_counts['canonical_evidence_item_count']} 条 / "
            f"{agenda_evidence_counts['unique_source_url_count']} 个去重 URL / "
            f"{agenda_evidence_counts['independent_publisher_count']} 家独立发布方；"
            f"旧 crux 审计 URL={rd['n_unique_sources']}（仅兼容指标）"
        )
    else:
        L.append(f"- 执行真实性: {execution_label} ｜ 唯一可复核来源: {rd['n_unique_sources']} 个"
                 f" ｜ 其中一级来源: {rd['n_primary_sources']} 个")
    opportunity_counts = opportunity_engine.summary(state)
    L.append(f"- 候选线索: {opportunity_counts['opportunity_seed_count']} 条证据路径 → "
             f"{opportunity_counts['unique_candidate_count']} 个唯一候选 ｜ "
             f"其中 {opportunity_counts['ready_for_screening_count']} 个当前可进入二次筛选")
    if landscape["required"]:
        L.append(
            f"- Landscape 覆盖: {landscape['path_count']} 条计划路径 ｜ "
            f"SUPPORTED {landscape['supported_count']} ｜ REJECTED {landscape['rejected_count']} ｜ "
            f"UNKNOWN {landscape['unknown_count']} ｜ UNPROBED {landscape['unprobed_count']}"
        )
    exploration_summary = exploration.get("summary", {})
    L.append(
        f"- 探索轨: 假说 {exploration_summary.get('hypothesis_count', 0)} ｜ "
        f"HYPOTHESIS_ONLY "
        f"{exploration_summary.get('state_counts', {}).get('HYPOTHESIS_ONLY', 0)} ｜ "
        f"TRACED {exploration_summary.get('state_counts', {}).get('TRACED', 0)} ｜ "
        f"EVIDENCE_BACKED "
        f"{exploration_summary.get('state_counts', {}).get('EVIDENCE_BACKED', 0)}"
    )
    screen_counts = candidate_screen_engine.summary(state)
    L.append(f"- 候选预筛: {screen_counts['screened_candidate_count']} 条已完成 ｜ "
             f"THESIS_CANDIDATE {screen_counts['thesis_candidate_count']} ｜ "
             f"WATCHLIST {screen_counts['watchlist_count']} ｜ REJECTED {screen_counts['rejected_candidate_count']}")
    verification_counts = claim_verification_engine.summary(state)
    L.append(f"- 来源内容对齐: VERIFIED {verification_counts['verified_thesis_candidate_count']} ｜ "
             f"PARTIAL {verification_counts['partially_verified_candidate_count']} ｜ "
             f"PENDING {verification_counts['pending_verification_candidate_count']} ｜ "
             f"CONTRADICTED {verification_counts['contradicted_candidate_count']}")
    L.append("- 口径: 支持度由 Judge 信号经固定规则生成，尚未历史校准；不得解释为胜率、收益率或仓位依据。")
    isolation = state.get("runtime_contract", {}).get("isolation_status", "unverified")
    L.append(f"- 隔离审计: **{isolation}**。只有宿主实际使用独立上下文时，才可声称多智能体隔离；"
             "单模型角色切换必须标注 degraded。")
    L.append("")

    # Framing integrity: hypotheses remain visibly provisional until the debate sources them.
    frame_contract = state.get("frame_contract", {})
    premises = frame_contract.get("premise_audit", [])
    L.append("## 0.1 · 立题完整性闸")
    L.append(f"- 状态: **{frame_contract.get('quality_status', 'LEGACY_UNAUDITED')}** ｜ "
             f"as-of: {_clean(frame_contract.get('as_of_date'))} ｜ "
             f"分析单元: {_clean(frame_contract.get('unit_of_analysis'))}")
    L.append("- `HYPOTHESIS` 与 `URL_CLAIMED_UNVERIFIED` 都不是证据；候选 URL 也不得被正文改写成已证实事实。")
    policy = frame_contract.get("artifact_policy", {})
    if policy:
        L.append(f"- 产物边界: `{policy.get('mode', 'inline_only')}` ｜ 云端或外部写入: "
                 f"`{policy.get('external_or_cloud_write', 'requires_explicit_user_opt_in')}`")
    if premises:
        L.append("")
        L.append("| 前提 | 状态 | as-of | 待核一级来源 / 候选 URL | 用途 |")
        L.append("|:---|:---:|:---|:---|:---|")
        for premise in premises:
            source = premise.get("source_url") or premise.get("required_primary_source") or "—"
            L.append(f"| **{_cell(premise.get('id'))}** {_cell(premise.get('claim'))} | "
                     f"{_cell(premise.get('status'))} | {_cell(premise.get('as_of'))} | "
                     f"{_cell(source)} | {_cell(premise.get('use'))} |")
    else:
        L.append("- 警告: 这是旧状态，未保存 premise_audit；不得把假设种子当作事实。")
    L.append("")

    if landscape["required"]:
        L.append("## 0.2 · Landscape Map 覆盖账本")
        L.append("- 顺序: 预设路径 → 双角色质证 → 聚合状态 → 候选转化。`UNKNOWN` 代表已查但未定，不是支持。")
        L.append("")
        L.append("| 路径 | 原型 | 来源 crux | 状态 | Detective | Inquisitor | 假设 / 经济捕获测试 |")
        L.append("|:---|:---|:---:|:---:|:---:|:---:|:---|")
        for path in landscape["paths"]:
            probes = path.get("probes", {})
            detective = probes.get("detective", {})
            inquisitor = probes.get("inquisitor", {})
            L.append(
                f"| **{_cell(path.get('path_id'))}** | {_cell(path.get('archetype'))} | "
                f"{_cell(path.get('linked_crux_id'))} | **{_cell(path.get('state'))}** | "
                f"R{detective.get('round', '—')} {_cell(detective.get('state', 'UNPROBED'))} | "
                f"R{inquisitor.get('round', '—')} {_cell(inquisitor.get('state', 'UNPROBED'))} | "
                f"{_cell(path.get('hypothesis'))}<br>{_cell(path.get('economic_capture_test'))} |"
            )
        L.append("")

    L.append("## 0.2B · 大胆假说与草蛇灰线")
    L.append(
        "- 探索轨允许大胆猜想先存在，再沿 ProxyTrail 小心求证。它不改变 root verdict、"
        "CandidateScreen 或任何交易状态。"
    )
    action = exploration.get("exploration_action", {})
    L.append(
        f"- 当前探索动作: `{action.get('action_code', 'NO_EXPLORATION_TRACK')}` ｜ "
        f"假说 `{action.get('hypothesis_id') or '—'}` ｜ "
        f"{_clean(action.get('instruction') or action.get('reason'))}"
    )
    L.append(
        f"- 授权状态: `{action.get('authorization_state', 'NOT_REQUIRED')}` ｜ "
        f"执行就绪: `{action.get('executable_after_authorization', False)}` ｜ "
        f"问题: {_clean(action.get('question'))} ｜ "
        f"来源类: {_clean(action.get('source_class'))}。"
    )
    L.append(
        f"- Host action: `{action.get('action_id') or '—'}` ｜ "
        f"host_status=`{action.get('host_action_status') or '—'}` ｜ "
        f"assurance=`{action.get('authorization_assurance') or '—'}` ｜ "
        f"proposal_drifted="
        f"`{action.get('proposal_drifted', False)}`。"
    )
    if action.get("authorization_state") == "NEEDS_ACTION_DESIGN":
        L.append(
            f"- 设计回执目标: `{action.get('design_target_id') or '—'}` ｜ "
            f"expected_state_revision="
            f"`{action.get('design_state_revision', '—')}`；"
            "这两个值只授权写入设计，不授权搜索。"
        )
    L.append(
        f"- 有界查询: {_clean(action.get('bounded_query'))} ｜ "
        f"成功: {_clean(action.get('success_condition'))} ｜ "
        f"停止: {_clean(action.get('stop_condition'))}。"
    )
    action_budget = action.get("budget_boundary", {})
    L.append(
        f"- 预算: queries≤{action_budget.get('max_bounded_queries', 0)}，"
        f"documents≤{action_budget.get('max_documents_read', 0)}，"
        f"new trails≤{action_budget.get('max_new_proxy_trails', 0)}；"
        f"execution_receipt=`{action.get('execution_receipt')}`。"
    )
    L.extend(_exploration_history_lines(
        exploration,
        heading="### 0.2B.1 · 已执行探索与负知识",
        include_control_history=True,
    ))
    hypotheses = exploration.get("hypotheses", [])
    if not hypotheses:
        L.append("- 本次没有初始化探索账本；纯命题质证可保持该状态。")
    else:
        L.append("")
        L.append("| 假说 | 状态 / 探索优先级 | 非共识机制与价值传导 | ProxyTrail / 引用 | 明确赔率门槛 | 反证 / 催化 |")
        L.append("|:---|:---|:---|:---|:---|:---|")
        for hypothesis in hypotheses:
            hypothesis_id = hypothesis.get("hypothesis_id", "?")
            priority = hypothesis.get("exploration_priority", {})
            proxies = []
            for proxy in hypothesis.get("proxy_trails", [])[:3]:
                nums = hypothesis_refs.get(
                    (hypothesis_id, proxy.get("proxy_id", "?")), []
                )
                refs_text = " ".join(f"[{number}]" for number in nums) or "无正式引用"
                proxies.append(
                    f"{_cell(proxy.get('direction'))}"
                    f"{'（争议: ' + _cell(proxy.get('direction_variants')) + '）' if proxy.get('direction_contested') else ''}: "
                    f"{_cell(proxy.get('proxy'))}；"
                    f"替代解释: {_cell(proxy.get('alternative_explanation'))} "
                    f"{refs_text}"
                )
            threshold = hypothesis.get("break_even_threshold", {})
            threshold_text = (
                f"p*={threshold.get('p_star_percent')}%（仅由明示 payoff 推导）"
                if threshold.get("status") == "KNOWN"
                else "UNKNOWN（未明示可比 payoff）"
            )
            mechanism = (
                f"{_cell(hypothesis.get('why_nonconsensus'))}<br>"
                f"{_cell(' -> '.join(hypothesis.get('causal_chain', [])))}<br>"
                f"{_cell(hypothesis.get('value_transfer'))}<br>"
                f"观察: {_cell(hypothesis.get('observation'))}<br>"
                f"最低成本判别: "
                f"{_cell(hypothesis.get('cheap_discriminating_test'))}"
            )
            asymmetry = hypothesis.get("asymmetry_case", {})
            if asymmetry.get("basis"):
                mechanism += (
                    "<br>定性非对称: "
                    f"{_cell(asymmetry.get('upside_shape'))}/"
                    f"{_cell(asymmetry.get('convexity'))} vs "
                    f"{_cell(asymmetry.get('downside_shape'))}；"
                    f"signal={_cell(asymmetry.get('time_to_signal'))}；"
                    f"basis={_cell(asymmetry.get('basis'))}"
                )
            observation_refs = " ".join(
                f"[{number}]"
                for number in hypothesis_refs.get(
                    (hypothesis_id, "OBSERVATION"), []
                )
            )
            observation_boundary = (
                f"{_cell(hypothesis.get('observation_status'))}"
                f"{(' ' + observation_refs) if observation_refs else ''}"
            )
            L.append(
                f"| **{_cell(hypothesis_id)}** {_cell(hypothesis.get('hypothesis'))} | "
                f"`{_cell(hypothesis.get('state'))}` / "
                f"`{_cell(priority.get('band'))}` "
                f"score={priority.get('score', 0)}<br>"
                f"components={_cell(priority.get('components'))}<br>"
                f"reasons={_cell(priority.get('reasons'))} | {mechanism}<br>"
                f"观察边界: {observation_boundary} | "
                f"{'<br>'.join(proxies) or '尚无 ProxyTrail'} | {_cell(threshold_text)} | "
                f"{_cell(hypothesis.get('falsifier'))} / "
                f"{_cell(hypothesis.get('catalyst'))} / "
                f"expiry={_cell(hypothesis.get('expiry_date'))} |"
            )
            contested = hypothesis.get("contested_fields", [])
            if contested:
                L.append(
                    f"| ↳ **争议字段** | 需人工调和 | "
                    f"{_cell(', '.join(contested))} | — | — | "
                    f"{_cell(hypothesis.get('field_variants'))} |"
                )
    L.append(
        "- `EVIDENCE_BACKED` 在本节只表示探索线索已有独立可复核代理证据；"
        "它仍不是 OpportunitySeed、概率、收益预测或仓位依据。"
    )
    L.append("")

    # Evidence quality gate
    invalid = quality["invalid"]
    formal_reference_count = sum(len(numbers) for numbers in crux_refs.values())
    gate_status = (
        "PASS" if not invalid and formal_reference_count > 0 else "FAIL"
    )
    L.append("## 0.3 · 证据质量闸")
    L.append(
        f"- 状态: **{gate_status}** ｜ 正式 crux 引用: "
        f"{formal_reference_count} 条 ｜ 全报告可复核引用: {len(refs)} 条 ｜ "
        f"被剔除正式引用: {len(invalid)} 条"
    )
    L.append("- 探索 ProxyTrail 引用单独展示，不计入正式 crux 证据质量闸。")
    L.append("- 规则: 引用必须含 claim/source/date，且 URL 不能只是主页或裸域名。")
    if invalid:
        for bad in invalid[:10]:
            L.append(f"  - 剔除: {bad.get('crux','?')} | {bad.get('source','?')} | {bad.get('url','')}")
        if len(invalid) > 10:
            L.append(f"  - 另有 {len(invalid) - 10} 条被剔除。")
    L.append("")

    # A · 证明账本
    L.append("## A · 证明账本（脚本物理生成，数值勿改）")
    if is_universe:
        L.append("| crux | 状态 | 支持证据 | 反对证据 | 监控锚点 | 反证 / 催化窗口 | 引用 |")
        L.append("|:---|:---|:---|:---|:---|:---|:---|")
    else:
        L.append("| crux | 辩论支持度 | 状态 | 多头最强 | 空头最强 | 监控锚点 | 反证 / 催化窗口 | 引用 |")
        L.append("|:---|:---:|:---|:---|:---|:---|:---|:---|")
    for c in rd["cruxes"]:
        rno = " ".join(f"[{n}]" for n in crux_refs[c["id"]]) or "—"
        zero_signal_receipts = sum(
            citation.get("support_effect")
            == "NONE_ZERO_SIGNAL_WASH"
            for citation in c.get("valid_citations", [])
            if isinstance(citation, dict)
        )
        decision_history = [
            item for item in c.get("decision_evidence_history", [])
            if isinstance(item, dict)
        ]
        directional_touches = sum(
            bool(item.get("decision_relevant")) for item in decision_history
        )
        nondiscriminating_touches = sum(
            item.get("disposition") in {
                "NEW_NON_DISCRIMINATING_EVIDENCE",
                "NEW_AGENT_EVIDENCE_NOT_JUDGE_ACCEPTED",
            }
            for item in decision_history
        )
        status_detail = _STATUS.get(c["status"], c["status"])
        if c.get("transition_reason"):
            status_detail += (
                f"<br>reason={_cell(c.get('transition_reason'))}"
            )
        if c.get("monitorable_semantics"):
            status_detail += (
                f"<br>{_cell(c.get('monitorable_semantics'))}"
            )
        if zero_signal_receipts:
            status_detail += (
                f"<br>non-discriminating citations={zero_signal_receipts}"
                "（记录但不移动支持度或重置枯竭）"
            )
        if decision_history:
            status_detail += (
                f"<br>decision touches={directional_touches} directional / "
                f"{nondiscriminating_touches} non-discriminating"
            )
        catalyst = c.get("catalyst_window", {})
        catalyst_text = (f"{catalyst.get('event', '—')} @ {catalyst.get('expected_by', '—')} "
                         f"[{catalyst.get('date_status', 'UNVERIFIED')}; "
                         f"basis={catalyst.get('basis_claim_id', '—')}]"
                         if isinstance(catalyst, dict) else _clean(catalyst))
        if is_universe:
            L.append(f"| **{c['id']} {c['label']}** | {status_detail} "
                     f"| {c.get('best_bull') or '—'} | {c.get('best_bear') or '—'} "
                     f"| {c.get('monitor_anchor','')} | {_cell(c.get('falsifier'))} / {_cell(catalyst_text)} | {rno} |")
        else:
            L.append(f"| **{c['id']} {c['label']}** | {int(c['support_score']*100)}/100 | "
                     f"{status_detail} "
                     f"| {c.get('best_bull') or '—'} | {c.get('best_bear') or '—'} "
                     f"| {c.get('monitor_anchor','')} | {_cell(c.get('falsifier'))} / {_cell(catalyst_text)} | {rno} |")
    L.append("")

    # 每条 crux 支持度轨迹
    if is_universe:
        L.append("### A.1 · Universe 收敛轨迹")
        L.append("- 不展示全局最弱值、均值或方向轨迹；这些数会错误混合不同候选与相反暴露。")
        for cid, cx in state["cruxes"].items():
            L.append(f"- **{cid} {cx['label']}**: {_STATUS.get(cx['status'], cx['status'])}；"
                     f"有效来源 URL {len(cx.get('seen_evidence_keys', []))} 条。")
    else:
        L.append("### A.1 · 辩论支持度演化（非统计概率）")
        for cid, cx in state["cruxes"].items():
            ph = cx["p_history"]
            pts = " → ".join(f"{int(p*100)}" for p in ph)
            status_icon = _STATUS.get(cx["status"], cx["status"])
            transition = (
                f"；transition={cx.get('transition_reason')}；"
                f"{cx.get('monitorable_semantics')}"
                if cx.get("transition_reason")
                else ""
            )
            L.append(
                f"- **{cid} {cx['label']}**: {pts} → "
                f"{status_icon}{transition}"
            )
    L.append("")

    # 证据仪表盘
    L.append("### A.2 · 证据与流程仪表盘")
    L.append("```text")
    L.append("═══════════════════════════════════════════")
    L.append(
        f"  TRADE NOTHING v{__version__} ADVERSARIAL DASHBOARD"
    )
    L.append("═══════════════════════════════════════════")
    L.append(f"  标的: {topic}")
    if agenda_native:
        L.append(
            f"  执行真实性: {execution_label} ｜ Agenda证据: "
            f"{agenda_evidence_counts['canonical_evidence_item_count']} 条 ｜ "
            f"去重URL: {agenda_evidence_counts['unique_source_url_count']} ｜ "
            f"独立发布方: {agenda_evidence_counts['independent_publisher_count']}"
        )
        L.append(f"  兼容crux审计URL: {rd['n_unique_sources']}（不代表产品证据量）")
    else:
        L.append(f"  执行真实性: {execution_label} ｜ 唯一来源: {rd['n_unique_sources']} 个")
    if is_universe:
        L.append(f"  当前研究焦点: {rd.get('focus_crux') or '—'}")
        L.append("  收敛单位: Landscape覆盖 + 连续候选收割静默")
    else:
        L.append(f"  当前焦点 / 最低支持度: {rd.get('focus_crux') or rd.get('binding_crux')} "
                 f"({int(support_w*100)}/100)")
        L.append(f"  命题均值支持度: {int(support_m*100)}/100")
    L.append(f"  决策演化: {trace_str}")
    L.append(
        "  零信号引用: NONE_ZERO_SIGNAL_WASH 仅记录新事实，"
        "不移动辩论支持度"
    )
    L.append("  交易输出: 禁止自动给出目标价、预期收益或仓位")
    L.append("═══════════════════════════════════════════")
    L.append("```")
    L.append("")

    # Deterministic opportunity layer. These are screening inputs, not recommendations.
    L.append("### A.3 · 候选线索地图（未筛选不等于机会）")
    L.append("- 根命题的研究状态与候选线索相互独立：即使根命题为 `NO_EDGE`，"
             "通过证据反查的替代者、竞争者或瓶颈所有者仍会保留。")
    L.append("- `READY_FOR_SCREENING` 只允许进入双边 CandidateScreen；`THESIS_CANDIDATE` 还必须通过"
             "页面快照与 claim 对齐，才会生成需要人工确认的新 Thesis 草稿。")
    L.append("- 只有 `VERIFIED_FOR_HUMAN` 可供人工建立独立 DRAFT Thesis；报告通过不代表候选可升级。")
    if not opportunities:
        L.append("- 本轮没有通过证据反查的候选；不以行业主题词或无来源公司名凑数。")
    for index, seed in enumerate(opportunities[:10], 1):
        ticker = f" · {seed['ticker']}" if seed.get("ticker") else ""
        effective_status = seed.get("candidate_state", opportunity_engine.EVIDENCE_BACKED)
        status_icon = "✅" if effective_status == opportunity_engine.VERIFIED_FOR_HUMAN else "⛔"
        screen = seed.get("_screen")
        screen_status = screen.get("status") if screen else "UNSCREENED"
        claim_status = screen.get("claim_verification_status", "PENDING") if screen else "NOT_APPLICABLE"
        refs_text = " ".join(
            f"[{n}]" for n in opportunity_refs.get(seed.get("_report_key"), [])
        ) or "—"
        agents = ", ".join(seed.get("source_agents", [])) or "—"
        L.append("")
        L.append(f"#### {index}. {_clean(seed.get('candidate'))}{ticker} — {status_icon} {effective_status} ｜ "
                 f"P1 {screen_status} ｜ P2 {claim_status}")
        entity_view = seed.get("_entity_view", {})
        if len(entity_view.get("paths", [])) > 1:
            L.append(f"- **实体去重**: 同一候选保留 {len(entity_view['paths'])} 条独立价值路径；"
                     "本报告只展示代表路径，证据不得跨路径拼接晋级。")
        L.append(f"- **关系 / 来源 crux**: {_relation_label(seed.get('relation_type'))}"
                 f" / {_clean(seed.get('origin_crux'))} ｜ 首见 R{seed.get('first_seen_round', '?')} ｜ agent: {agents}")
        if seed.get("landscape_path_id"):
            L.append(f"- **Landscape 绑定**: {_clean(seed.get('landscape_path_id'))} → "
                     f"{_clean(seed.get('origin_crux'))}")
        if seed.get("origin_hypothesis_id"):
            L.append(
                f"- **探索谱系**: {_clean(seed.get('origin_hypothesis_id'))} → "
                f"{_clean(seed.get('origin_crux'))}；谱系不降低 Seed 证据门。"
            )
        L.append(f"- **价值传导**: {_clean(seed.get('causal_path'))}")
        L.append(f"- **经济暴露**: {_clean(seed.get('economic_exposure'))}")
        L.append(f"- **市场可能漏看**: {_clean(seed.get('why_market_may_miss'))}")
        L.append(f"- **定价锚**: {opportunity_engine.pricing_anchor_text(seed.get('pricing_anchor'))}")
        L.append(f"- **催化 / 证伪**: {_clean(seed.get('catalyst'))} / {_clean(seed.get('falsifier'))}")
        promotion = seed.get("promotion", {})
        L.append(f"- **Thesis 升级资格**: `{promotion.get('promotion_eligibility', 'BLOCKED')}`")
        blockers = promotion.get("blocking_reasons") or seed.get("screening_blockers") or []
        if blockers:
            L.append(f"- **当前阻塞**: {', '.join(blockers)}")
        L.append(f"- **证据**: {refs_text}")
        if seed.get("field_variants"):
            L.append(f"- **冲突提醒**: 跨轮字段存在 {len(seed['field_variants'])} 处不同表述，二次筛选时必须对读。")
        if screen:
            source_gate = screen.get("source_gate", {})
            L.append(f"- **CandidateScreen**: `{screen_status}` ｜ as-of {screen.get('as_of_date', '—')} ｜ "
                     f"隔离 {screen.get('isolation_status', 'unverified')} ｜ "
                     f"独立 URL {source_gate.get('n_unique_urls', 0)} ｜ 一级来源 {source_gate.get('n_primary_urls', 0)}"
                     f" ｜ 来源机构 {source_gate.get('n_source_orgs', 0)}")
            L.append(f"- **Claim Verification**: `{claim_status}` ｜ "
                     "P2 验证快照哈希与精确片段；它证明 claim 与快照内容对齐，不证明来源本身真实。")
            if screen.get("gaps"):
                gap_summary = _screen_gap_summary(screen)
                if gap_summary.get("primary"):
                    L.append(
                        f"- **首要筛选缺口**: {gap_summary['primary']} ｜ Analyst "
                        f"{gap_summary['analyst_answer']} ｜ Skeptic {gap_summary['skeptic_answer']}"
                    )
                if gap_summary.get("dependent"):
                    L.append(f"- **派生未研究项**: {', '.join(gap_summary['dependent'])}")
                if gap_summary.get("source_gaps"):
                    L.append(f"- **来源门槛**: {', '.join(gap_summary['source_gaps'])}")
                if gap_summary.get("process_gaps"):
                    L.append(f"- **流程门槛**: {', '.join(gap_summary['process_gaps'])}")
            L.append("")
            L.append("<details><summary>展开八维双边筛选矩阵</summary>")
            L.append("")
            L.append("| 维度 | 合并状态 | Analyst | Skeptic | P2 内容对齐 | 引用 |")
            L.append("|:---|:---:|:---|:---|:---:|:---|")
            for dimension in candidate_screen_engine.DIMENSIONS:
                combined = screen.get("dimensions", {}).get(dimension, {})
                analyst = combined.get("analyst", {})
                skeptic = combined.get("skeptic", {})
                nums = screen_dimension_refs.get((screen.get("screen_id"), dimension), [])
                refs_text = " ".join(f"[{n}]" for n in nums) or "—"
                side_states = []
                for side, assessment in (("A", analyst), ("S", skeptic)):
                    evidence = assessment.get("fresh_evidence", assessment.get("evidence", []))
                    verdicts = [
                        latest_claims.get(claim_verification_engine.claim_id(c), {}).get("effective_verdict")
                        for c in evidence if claim_verification_engine.claim_id(c)
                    ]
                    if "CONTRADICTS" in verdicts:
                        aligned = "✗"
                    elif "SUPPORTS" in verdicts:
                        aligned = "✓"
                    else:
                        aligned = "…"
                    side_states.append(f"{side}:{aligned}")
                L.append(f"| {dimension} | {combined.get('state', 'INCOMPLETE')} | "
                         f"{analyst.get('answer', 'UNKNOWN')}: {_cell(analyst.get('finding'))} | "
                         f"{skeptic.get('answer', 'UNKNOWN')}: {_cell(skeptic.get('finding'))} | "
                         f"{' '.join(side_states)} | {refs_text} |")
            L.append("")
            L.append("</details>")
            packet = screen.get("promotion_packet")
            relevant_verifications = [
                item for item in latest_claims.values()
                if any(context.get("screen_id") == screen.get("screen_id")
                       for context in item.get("contexts", []))
            ]
            if relevant_verifications:
                L.append("")
                L.append("<details><summary>展开页面快照与 claim 对齐账本</summary>")
                L.append("")
                L.append("| claim | verdict | snapshot | 精确片段 |")
                L.append("|:---|:---:|:---|:---|")
                for verification in sorted(
                    relevant_verifications,
                    key=lambda item: ref_no.get(_cite_key(item.get("citation", {})), 10**9),
                ):
                    citation = verification.get("citation", {})
                    ref = ref_no.get(_cite_key(citation))
                    ref_text = f"[{ref}]" if ref else verification.get("claim_id", "—")
                    snapshot = verification.get("snapshot_manifest", {})
                    hash_text = _clean(snapshot.get("text_sha256"))[:12]
                    L.append(f"| {ref_text} | {verification.get('effective_verdict', 'INSUFFICIENT')} | "
                             f"`{hash_text}` | {_cell(verification.get('exact_quote'))} |")
                L.append("")
                L.append("</details>")
            if packet:
                L.append("")
                L.append(f"- **升级包**: `{packet.get('status')}` — {_clean(packet.get('required_next_step'))}")
                L.append(f"- **新 Thesis 决策问题草稿**: {_clean(packet.get('decision_question_seed'))}")
    if len(opportunities) > 10:
        L.append(f"- 另有 {len(opportunities) - 10} 条证据线索留在 state；本报告只展示成熟度优先的前 10 条。")
    L.append("")

    # 引用
    L.append("## 📚 引用 (References)")
    if refs:
        for i, c in enumerate(refs, 1):
            num = f" — {c.get('number')}" if c.get("number") else ""
            src = c.get("source", "?")
            date = c.get("date", "")
            url = c.get("url", "")
            L.append(f"- [{i}] {c.get('claim','')}{num}（{src}"
                     f"{', '+date if date else ''}）{url}")
    else:
        L.append("- （无结构化引用——警告：本轮证据缺乏可核验来源，结论可信度低）")
    L.append("")
    # ─────────── COMPACT USER SYNTHESIS ───────────
    # Raw Detective/Inquisitor/Judge payloads remain in state for explicit audit only.
    L.append("---")
    L.append("")
    L.append("## B · 决策摘要（确定性用户视图）")
    L.append("")
    L.append("<!-- BATTLE_LOG_START -->")
    L.append("### 一句话裁决")
    L.append(f"- **{verdict.get('edge_state', 'INSUFFICIENT_EVIDENCE')} / "
             f"{verdict.get('evidence_direction', 'UNDETERMINED')} / "
             f"{verdict.get('actionability', 'NONE')}**；该三维状态分别回答是否发现预期差、"
             "证据方向和是否值得进入候选筛选，不是交易动作、胜率或收益判断。")
    L.append("")
    binding_item = next((item for item in rd["cruxes"] if item["id"] == rd.get("binding_crux")), None)
    L.append("### 约束性 Crux / 当前研究焦点")
    if binding_item:
        nums = crux_refs.get(binding_item["id"], [])
        ref_text = " ".join(f"[{n}]" for n in nums) or "—"
        L.append(f"- **{binding_item['id']} {binding_item['label']}** — {binding_item['status']} {ref_text}")
        L.append(f"- 最强多头: {binding_item.get('best_bull') or '—'} {ref_text}")
        L.append(f"- 最强空头: {binding_item.get('best_bear') or '—'} {ref_text}")
        L.append(f"- 翻案条件: {binding_item.get('falsifier') or '—'} {ref_text}")
    else:
        focus_item = next((item for item in rd["cruxes"] if item["id"] == rd.get("focus_crux")), None)
        if focus_item:
            nums = crux_refs.get(focus_item["id"], [])
            ref_text = " ".join(f"[{n}]" for n in nums) or "—"
            L.append(f"- 多路径题型无单一 binding crux；当前研究焦点为 **{focus_item['id']} "
                     f"{focus_item['label']}** — {focus_item['status']} {ref_text}")
        else:
            L.append("- 无可用 binding crux 或当前研究焦点。")
    L.append("")
    L.append("### 证据方向与监控")
    for item in rd["cruxes"]:
        nums = crux_refs.get(item["id"], [])
        ref_text = " ".join(f"[{n}]" for n in nums) or "—"
        catalyst = item.get("catalyst_window", {}) if isinstance(item.get("catalyst_window"), dict) else {}
        trigger = catalyst.get("event") or item.get("monitor_anchor") or "—"
        route_classes = [
            str(route.get("publisher_class") or "")
            for route in item.get("evidence_plan", [])
            if isinstance(route, dict) and route.get("publisher_class")
        ]
        route_text = " / ".join(route_classes) or "—"
        L.append(f"- **{item['id']} {item['status']}**: 监控 {trigger}；"
                 f"证伪 {item.get('falsifier') or '—'}；冻结来源路线 {route_text}。{ref_text}")
    L.append("")
    L.append("### 候选线索边界")
    L.append(f"- 证据路径已按唯一候选去重展示；当前只有 "
             f"{opportunity_counts['ready_for_screening_count']} 个候选具备双边筛查资格。")
    L.append("- 未完成 CandidateScreen 与页面快照对齐的候选，均不得表述为投资结论。")
    L.append("<!-- BATTLE_LOG_END -->")
    return "\n".join(L)


def _render_decision_brief(view):
    verdict = view["verdict"]
    counts = view["candidate_counts"]
    root = view["root_thesis"]
    grade = view.get("research_grade") or {}
    candidate_lifecycle = grade.get("candidate_lifecycle") or {}
    survived = "；".join(
        f"{item['id']} {item['label']}" for item in root["survived"][:3]
    ) or "无已确认的偏多 crux"
    falsified = "；".join(
        f"{item['id']} {item['label']}" for item in root["falsified"][:3]
    ) or "无已确认被推翻的 crux"
    monitoring = "；".join(
        f"{item['id']} {item['label']}" for item in root["monitorable"][:3]
    ) or "无"
    formal_action = view["formal_action"]
    exploration = view.get("hypothesis_exploration", {})
    exploration_action = view.get("exploration_action", {})
    landscape = view.get("landscape_map", {})
    scenario = view.get("scenario_paths", {})
    exploration_budget = exploration_action.get("budget_boundary", {})
    target = (
        f"（{formal_action['candidate']}）" if formal_action["candidate"] else ""
    )
    universe = view["question_type"] == "UNIVERSE_SEARCH"
    challenge_heading = "## 研究轴证据状态" if universe else "## 原想法经质证后发生了什么"
    challenge_lines = (
        [
            f"- **存在正向证据**: {survived}。",
            f"- **存在负向证据**: {falsified}。",
            f"- **仍需候选级判断**: {monitoring}。",
            "- 这些是跨候选研究轴的证据状态，不构成候选宇宙的整体多空方向。",
        ]
        if universe else [
            f"- **活下来**: {survived}。",
            f"- **被推翻**: {falsified}。",
            f"- **仍需监控**: {monitoring}。",
        ]
    )
    threshold = scenario.get("break_even_threshold", {})
    threshold_text = (
        f"p*={threshold.get('p_star_percent')}%（只由明示同单位情景幅度推导）"
        if threshold.get("status") == "KNOWN"
        else f"UNKNOWN（{threshold.get('reason', '未明示可比情景幅度')}）"
    )
    scenario_lines = [
        "## 对称场景与非对称边界",
        f"- 路径审计: `{scenario.get('status', 'MISSING')}`；"
        f"赔率门槛: {threshold_text}；这不是概率、预期收益或仓位。",
    ]
    for path in scenario.get("paths", []):
        scenario_lines.append(
            f"- **{path.get('path_type')}**: {_clean(path.get('summary'))}；"
            f"触发 {_clean(path.get('trigger_event'))}；"
            f"传导 {_clean(path.get('transmission_chain'))}；"
            f"监控 {_clean(path.get('monitor_anchor'))}；"
            f"反证 {_clean(path.get('falsifier'))}。"
        )
    if scenario.get("issues"):
        scenario_lines.append(
            f"- 路径缺口: `{', '.join(scenario.get('issues', []))}`。"
        )
    exploration_history_lines = _exploration_history_lines(
        exploration,
        heading="### 已执行探索与负知识",
        include_control_history=True,
    )
    temporal = view.get("temporal_contract", {})
    temporal_lines = [
        "## 时间语义合同",
        f"- 状态 `{temporal.get('status', 'MISSING')}`；证据截止 "
        f"`{temporal.get('evidence_as_of_date') or 'UNKNOWN'}`；预测目标 "
        f"`{temporal.get('forecast_target_date') or 'RELATIVE_HORIZON'}`；"
        f"视野 `{temporal.get('decision_horizon') or 'UNKNOWN'}`。",
        f"- {temporal.get('message') or '时间合同缺失。'}",
    ]
    allocation_lines = [
        "## 研究资源与风险收益匹配",
        "- 这里只比较信息价值、非对称形状、信号速度和验证成本；"
        "不是投资排序、概率、预期收益或仓位。",
    ]
    for item in view.get("research_allocation", [])[:5]:
        asymmetry = item.get("asymmetry_case", {})
        budget = item.get("validation_budget", {})
        allocation_lines.append(
            f"- **#{item.get('rank')} {item.get('hypothesis_id')}** "
            f"`{item.get('attention_band')}`："
            f"upside={asymmetry.get('upside_shape', 'UNKNOWN')}/"
            f"{asymmetry.get('convexity', 'UNKNOWN')}，"
            f"downside={asymmetry.get('downside_shape', 'UNKNOWN')}，"
            f"signal={asymmetry.get('time_to_signal', 'UNKNOWN')}；"
            f"最小测试 {_clean(item.get('minimum_test'))}；"
            f"预算 queries≤{budget.get('max_bounded_queries', '—')} / "
            f"docs≤{budget.get('max_documents_read', '—')}。"
        )
    if len(allocation_lines) == 2:
        gap = view.get("exploration_gap", {})
        allocation_lines.append(
            f"- **探索方法缺口** `{gap.get('status', 'MISSING')}`："
            f"{gap.get('message') or '没有可审计探索产物。'}"
        )
    evidence_lines = [
        "## 证据矩阵（按对象绑定）",
        f"- 共 {view.get('evidence_matrix', {}).get('row_count', 0)} 条；"
        f"{view.get('evidence_matrix', {}).get('boundary', '')}",
    ]
    for item in view.get("evidence_matrix", {}).get("rows", [])[:12]:
        evidence_lines.append(
            f"- `{item.get('track')}` / `{item.get('binding_id') or '—'}` / "
            f"`{item.get('direction')}`：{_clean(item.get('claim'))} — "
            f"{_clean(item.get('source'))}，{item.get('date') or '日期未知'}，"
            f"{_clean(item.get('url'))}"
        )
    return "\n".join([
        f"# Decision Brief — {view['topic']}",
        f"> 决策问题: {view['decision_question']} ｜ 视野: {view['horizon']} ｜ "
        f"题型: {view['question_type']} ｜ 证据截止: "
        f"{view.get('as_of_date') or 'UNKNOWN'} ｜ 预测目标: "
        f"{view.get('forecast_target_date') or 'RELATIVE_HORIZON'}",
        "",
        *temporal_lines,
        "",
        "## 一句话结论",
        f"- Edge: **{verdict['edge_state']}** ｜ 证据方向: **{verdict['evidence_direction']}** ｜ "
        f"可行动性: **{verdict['actionability']}**。",
        f"- 这回答的是命题、证据和研究动作，不是买卖建议；依据代码: `{verdict['reason_code']}`。",
        "",
        challenge_heading,
        *challenge_lines,
        "" if not landscape.get("required") else "## 发现路径覆盖",
        "" if not landscape.get("required") else (
            f"- 计划 {landscape['path_count']}；SUPPORTED {landscape['supported_count']}；"
            f"REJECTED {landscape['rejected_count']}；UNKNOWN {landscape['unknown_count']}；"
            f"UNPROBED {landscape['unprobed_count']}。"
        ),
        "",
        "## 候选成熟度",
        f"- 唯一候选 {counts['lead_count']}；可筛选 {counts['ready_for_screening_count']}；"
        f"已筛选 {counts['screened_count']}；待 claim 核验 {counts['thesis_candidate_count']}；"
        f"可供人工建 Thesis {counts['verified_for_human_count']}。",
        "- 根命题成立不等于候选可用；只有 `VERIFIED_FOR_HUMAN` 才能交给人工建立全新 Thesis。",
        "",
        "## 正式晋级动作",
        f"- `{formal_action['code']}`{target}: {formal_action['instruction']}",
        "- 该动作由证据与候选成熟度决定；探索轨不能覆盖或绕过它。",
        "",
        "## 探索动作（无晋级与交易权限）",
        f"- `{exploration_action.get('action_code', 'NO_EXPLORATION_TRACK')}`"
        f"（{exploration_action.get('hypothesis_id') or '—'}）: "
        f"{exploration_action.get('instruction') or exploration_action.get('reason') or '无'}",
        f"- 假说 {exploration.get('summary', {}).get('hypothesis_count', 0)} 条；"
        f"ProxyTrail {exploration.get('summary', {}).get('proxy_trail_count', 0)} 条。"
        "探索排序只分配研究注意力，不是概率、预期收益或仓位。",
        f"- 授权状态 `{exploration_action.get('authorization_state', 'NOT_REQUIRED')}`；"
        f"执行就绪 `{exploration_action.get('executable_after_authorization', False)}`；"
        f"来源类 {_clean(exploration_action.get('source_class'))}；"
        f"有界查询 {_clean(exploration_action.get('bounded_query'))}。",
        f"- Host action `{exploration_action.get('action_id') or '—'}`；"
        f"host_status="
        f"`{exploration_action.get('host_action_status') or '—'}`；"
        f"assurance="
        f"`{exploration_action.get('authorization_assurance') or '—'}`；"
        f"proposal_drifted="
        f"`{exploration_action.get('proposal_drifted', False)}`。",
        (
            f"- 设计回执目标 `{exploration_action.get('design_target_id') or '—'}`；"
            f"expected_state_revision="
            f"`{exploration_action.get('design_state_revision', '—')}`；"
            "仅允许写入设计，不允许搜索。"
            if exploration_action.get("authorization_state")
            == "NEEDS_ACTION_DESIGN"
            else ""
        ),
        f"- 问题: {_clean(exploration_action.get('question'))}；"
        f"成功: {_clean(exploration_action.get('success_condition'))}；"
        f"停止: {_clean(exploration_action.get('stop_condition'))}；"
        "没有独立授权与执行回执不得执行。",
        f"- 预算: queries≤{exploration_budget.get('max_bounded_queries', 0)}，"
        f"documents≤{exploration_budget.get('max_documents_read', 0)}，"
        f"new trails≤{exploration_budget.get('max_new_proxy_trails', 0)}；"
        f"execution_receipt="
        f"`{exploration_action.get('execution_receipt')}`。",
        *exploration_history_lines,
        "",
        *allocation_lines,
        "",
        *scenario_lines,
        "",
        *evidence_lines,
        "",
        "## 什么会改变结论",
        f"- 焦点 crux: `{view['change_trigger']['focus_crux'] or '—'}`；"
        f"观察事件: {view['change_trigger']['event']}；"
        f"反证条件: {view['change_trigger']['falsifier']}。",
        "",
        "## 运行边界",
        f"- 执行 `{_clean(view['runtime'].get('execution_integrity', {}).get('execution_mode'))}`；"
        f"{_execution_round_label(view['runtime'])}；隔离 `{view['runtime']['isolation_status']}`；"
        f"可复核来源 {view['runtime']['unique_source_count']}；一级来源 "
        f"{view['runtime']['primary_source_count']}。",
        f"- 报告等级 **{grade.get('report_grade', 'UNKNOWN')}**；"
        f"未满足闸门 {'、'.join(grade.get('unmet_gates') or []) or '无'}；"
        f"对外发布={grade.get('publication_allowed', False)}；"
        f"个股排序={grade.get('ranking_allowed', False)}。",
        f"- 候选流程（不影响报告等级）：筛查="
        f"{candidate_lifecycle.get('screening_status', 'UNKNOWN')}；claim 核验="
        f"{candidate_lifecycle.get('verification_status', 'UNKNOWN')}；待办="
        f"{'、'.join(candidate_lifecycle.get('pending_steps') or []) or '无'}；可排序 seed="
        f"{'、'.join(candidate_lifecycle.get('rankable_seed_ids') or []) or '无'}。",
        "- 支持度、候选状态和模拟收益均不是概率、预期收益、交易指令或仓位输入。",
    ])


def _candidate_gate_label(card):
    """Short human label for where a candidate is gated (deterministic, no scoring)."""
    state = card["candidate_state"]
    if state == opportunity_engine.VERIFIED_FOR_HUMAN:
        return "可升级"
    if state == opportunity_engine.THESIS_CANDIDATE:
        return "待核验"
    gap = card.get("screen_gap_summary", {}).get("primary")
    if gap:
        return f"筛选缺 {gap}"
    blockers = card.get("blocking_reasons") or []
    if blockers:
        return f"缺 {'、'.join(blockers[:2])}"
    return state


def _render_candidate_cards(view):
    lines = [
        "# Candidate Cards",
        "> 先讲机会结构，再讲证据状态。故事是路径假设，状态是证据门；任何候选都不是推荐。",
        "",
    ]
    cards = view["candidate_cards"]
    if not cards:
        lines.extend([
            "## 0 个候选",
            "- 本轮没有形成具备有效证据路径的唯一候选；不得用行业关键词或知名公司凑数。",
        ])
        return "\n".join(lines)
    # Tracking list: paths with favorable odds but incomplete evidence stay visible
    # with their upgrade/abandon checkpoints. Tracking is not a recommendation.
    tracking_rows = view.get("tracking_rows") or []
    if tracking_rows:
        lines.extend([
            "## 跟踪清单（赔率可行但证据未完备：值得跟踪，不是推荐）",
            "| 候选 | 赔率姿态 | 检查点·升级 | 检查点·放弃 | 失败信号 | 下一动作 |",
            "|------|------|------|------|------|------|",
        ])
        for row in tracking_rows:
            ticker = f" · {row['ticker']}" if row.get("ticker") else ""
            chain_brief = (
                f"链{row['chain_counts']['confirmed']}实"
                f"/{row['chain_counts']['unverified']}虚"
                f"/{row['chain_counts']['observed']}观"
            )
            lines.append(
                f"| {_clean(row['candidate'])}{ticker} | {row['odds_posture']} "
                f"({chain_brief}) | {_clean(row['upgrade_checkpoint'])} | "
                f"{_clean(row['abandon_checkpoint'])} | "
                f"{_clean(row['failure_signal']) or '—'} | "
                f"{_clean(row['gap_next_action'])} |"
            )
        lines.append("")
    # Research pipeline overview: every candidate visible with its logic-chain
    # density and odds posture before any single-card detail. Deterministic only.
    lines.append("## 研究管线（全部候选：逻辑确定性 × 赔率姿态 × 卡点）")
    lines.append("| 候选 | 逻辑链（有证据/待验证/待观测） | 赔率姿态 | 状态 | 卡点 |")
    lines.append("|------|------|------|------|------|")
    for card in cards:
        path = card.get("path_analysis") or {}
        chain_info = (
            f"{path.get('confirmed', 0)}/{path.get('unverified', 0)}"
            f"/{path.get('observed', 0)}"
            if path.get("chain")
            else "—"
        )
        odds = card.get("odds_summary") or {}
        if odds.get("has_numeric_payoff"):
            be = odds.get("break_even") or {}
            odds_posture = f"break-even {be.get('p_star_percent')}%"
        elif odds.get("qualitative"):
            odds_posture = odds["qualitative"]
        else:
            odds_posture = "未声明"
        lines.append(
            f"| {_clean(card['candidate'])} | {chain_info} | {odds_posture} | "
            f"`{card['candidate_state']}` | {_candidate_gate_label(card)} |"
        )
    lines.append("")
    for index, card in enumerate(cards, 1):
        ticker = f" · {card['ticker']}" if card["ticker"] else ""
        lines.append(f"## {index}. {card['candidate']}{ticker}")
        story_parts = [card["relation_label"]]
        exposure = card["economic_exposure"]
        if exposure and exposure not in {"—", "-"}:
            story_parts.append(exposure)
        lines.append(
            f"- **故事**: {' → '.join(story_parts)}（源 crux {card['origin_crux']} · "
            f"Landscape `{card['landscape_path_id'] or 'legacy-unmapped'}`）。"
        )
        gap = card["expectation_gap"]
        if gap and gap not in {"—", "-"}:
            lines.append(f"  - **市场可能漏看**: {gap.rstrip('。')}。")
        path = card.get("path_analysis") or {}
        chain = path.get("chain") or []
        if chain:
            lines.append("- **逻辑链确定性**(研究骨架，非已证因果):")
            for node in chain:
                marks = []
                if node.get("evidence_touched"):
                    marks.append("✅ 有证据触达")
                else:
                    marks.append("⚠️ 待验证")
                if node.get("observable"):
                    marks.append("📌 有待观测事件")
                lines.append(
                    f"  - {node['node']} — {'｜'.join(marks) if marks else '⚠️ 待验证'}"
                )
        odds = card.get("odds_summary") or {}
        if odds:
            odds_line = "- **赔率结构**: "
            pieces = []
            if odds.get("qualitative"):
                pieces.append(odds["qualitative"])
            be = odds.get("break_even") or {}
            if be.get("status") == "KNOWN":
                pieces.append(f"break-even 成功率 {be.get('p_star_percent')}%")
            elif be.get("reason"):
                pieces.append(f"break-even 不可算（{be['reason']}）")
            if odds.get("basis"):
                pieces.append(f"依据: {odds['basis'].rstrip('。')}")
            if pieces:
                lines.append(odds_line + "；".join(pieces) + "。")
        scenario_paths = card.get("scenario_paths") or {}
        if scenario_paths:
            lines.append("- **对称场景**:")
            for key, label in (("bull", "上行"), ("base", "基准"), ("bear", "下行")):
                value = _clean(scenario_paths.get(key))
                if value:
                    lines.append(f"  - {label}: {value.rstrip('。')}。")
        if card["catalyst"] and card["catalyst"] not in {"—", "-"}:
            lines.append(f"- **检查点·升级**: {card['catalyst'].rstrip('。')}。")
        if card["falsifier"] and card["falsifier"] not in {"—", "-"}:
            lines.append(f"- **检查点·放弃**: {card['falsifier'].rstrip('。')}。")
        lines.append(f"- **锚**: {card['pricing_anchor']}。")
        lines.append(
            f"- **可交易载体**: {card['trading_vehicle']}；"
            f"可交易性 `{card['tradability_assessment']}`。"
        )
        lines.extend([
            f"- **Seed ID**: `{card['seed_id']}`。",
            f"- **候选状态**: `{card['candidate_state']}` ｜ 升级资格: "
            f"`{card['promotion_eligibility']}` ｜ P1 `{card['screen_status']}` ｜ "
            f"P2 `{card['claim_verification_status']}` ｜ 隔离 `{card['isolation_status']}` ｜ "
            f"独立路径 {card['path_count']} 条，路径之间不得拼接证据晋级。",
        ])
        if card.get("origin_hypothesis_id") not in {"", "—", None}:
            lines.append(
                f"- **探索谱系**: `{card['origin_hypothesis_id']}`；"
                "该绑定只解释发现来源，不降低 Seed 证据门。"
            )
        audit_lines = []
        blocking = card.get("blocking_reasons") or []
        if blocking:
            audit_lines.append(f"- **阻塞原因**: {', '.join(blocking)}。")
        gap_summary = card.get("screen_gap_summary", {})
        if gap_summary.get("primary"):
            audit_lines.append(
                f"- **首要筛选缺口**: {gap_summary['primary']} ｜ Analyst "
                f"{gap_summary['analyst_answer']} ｜ Skeptic {gap_summary['skeptic_answer']}。"
            )
            if gap_summary.get("dependent"):
                audit_lines.append(f"- **派生未研究项**: {', '.join(gap_summary['dependent'])}。")
            if gap_summary.get("source_gaps"):
                audit_lines.append(f"- **来源门槛**: {', '.join(gap_summary['source_gaps'])}。")
            if gap_summary.get("process_gaps"):
                audit_lines.append(f"- **流程门槛**: {', '.join(gap_summary['process_gaps'])}。")
        gap_task = card.get("gap_task") or {}
        if gap_task:
            audit_lines.append(
                f"- **候选补证任务**: `{gap_task['task_id']}` ｜ blocker "
                f"`{gap_task['blocker_code']}` ｜ 目标: {gap_task['target_claim']} ｜ "
                f"来源: {', '.join(gap_task['required_source_types'])} ｜ "
                f"预算: {gap_task['search_budget']} 次。"
            )
            audit_lines.append(
                f"- **任务终止条件**: 成功 — {gap_task['success_condition']}；"
                f"失败 — {gap_task['failure_condition']}"
            )
        gap_resolution = card.get("gap_resolution") or {}
        if gap_resolution:
            audit_lines.append(
                f"- **候选补证结果**: `{gap_resolution.get('status')}` — "
                f"{gap_resolution.get('reason') or '无附加说明'}。"
            )
        if audit_lines:
            lines.append("<details><summary>审计细节：阻塞、筛选缺口、补证任务</summary>")
            lines.append("")
            lines.extend(audit_lines)
            lines.append("")
            lines.append("</details>")
        lines.extend([
            f"- **下一动作**: `{card['next_action_code']}` — {card['next_action']}",
            "",
        ])
    return "\n".join(lines).rstrip()


def _render_insight_cards(view):
    exploration = view.get("hypothesis_exploration", {})
    hypotheses = exploration.get("hypotheses", [])
    lines = [
        "# Insight Cards — 可能被漏掉的东西",
        "> 先允许猜想存在，再沿草蛇灰线求证。这里的状态没有候选晋级或交易权限。",
        "",
    ]
    if not hypotheses:
        lines.extend([
            "## 0 条探索假说",
            "- 本次没有初始化探索轨；这不改变正式证据结论。",
        ])
        return "\n".join(lines)
    for index, item in enumerate(hypotheses, 1):
        priority = item.get("exploration_priority", {})
        context = item.get("context", {})
        trails = item.get("proxy_trails", [])
        observation_status = item.get(
            "observation_status", "UNVERIFIED_CLUE"
        )
        observation_text = _clean(item.get("observation"))
        if (
            observation_status == "CITED_PROXY_TRAIL"
            and observation_text == "—"
        ):
            observation_text = (
                f"见下方 {item.get('proxy_evidence_count', 0)} 条"
                " ProxyTrail 引用"
            )
        threshold = item.get("break_even_threshold", {})
        threshold_text = (
            f"p*={threshold.get('p_star_percent')}%（仅由明示 payoff 机械推导）"
            if threshold.get("status") == "KNOWN"
            else "UNKNOWN（未明示可比 upside/downside）"
        )
        lines.extend([
            f"## {index}. {item.get('hypothesis_id', '—')} — "
            f"`{item.get('state', 'HYPOTHESIS_ONLY')}`",
            f"- **猜想**: {_clean(item.get('hypothesis'))}",
            f"- **观察 / 推断边界**: "
            f"`{observation_status}` "
            f"{observation_text} / "
            f"{_clean(item.get('inference') or item.get('value_transfer'))}",
            f"- **如果为真，意外在哪里**: "
            f"{_clean(item.get('surprise_if_true') or item.get('why_nonconsensus'))}",
            f"- **因果链**: {_clean(' -> '.join(item.get('causal_chain', [])))}",
            f"- **最强替代解释**: {_clean(item.get('strongest_alternative_explanation'))}",
            f"- **最低成本判别测试**: "
            f"{_clean(item.get('cheap_discriminating_test'))}",
            f"- **反证 / 催化**: {_clean(item.get('falsifier'))} / "
            f"{_clean(item.get('catalyst'))}",
            f"- **到期边界**: {_clean(item.get('expiry_date'))}；"
            "到期只触发人工 park/supersede 复核，不自动删改状态。",
            f"- **探索排序**: `{priority.get('band', 'PARK')}`；"
            f"score={priority.get('score', 0)}；"
            f"components={_clean(priority.get('components'))}；"
            f"reasons={_clean(priority.get('reasons'))}。"
            "只分配研究注意力，不是概率或预期收益。",
            f"- **明示赔率边界**: {threshold_text}；不估计实际成功率。",
            f"- **定性非对称声明**: "
            f"{_clean(item.get('asymmetry_case', {}).get('upside_shape'))}/"
            f"{_clean(item.get('asymmetry_case', {}).get('convexity'))} vs "
            f"{_clean(item.get('asymmetry_case', {}).get('downside_shape'))}；"
            f"signal={_clean(item.get('asymmetry_case', {}).get('time_to_signal'))}；"
            f"basis={_clean(item.get('asymmetry_case', {}).get('basis'))}。"
            "它只参与研究队列；无证据、概率、预期收益或仓位权限。",
            f"- **谱系**: crux `{context.get('origin_crux') or '—'}`；"
            f"crux 集合 `{', '.join(context.get('origin_cruxes', [])) or '—'}`；"
            f"Landscape 集合 "
            f"`{', '.join(context.get('landscape_path_ids', [])) or '—'}`。",
        ])
        scenario_paths = item.get("scenario_paths", {})
        if scenario_paths:
            lines.append("- **假说场景**:")
            for path_type in ("bull", "base", "bear"):
                lines.append(
                    f"  - `{path_type.upper()}`: "
                    f"{_clean(scenario_paths.get(path_type))}"
                )
        contested = item.get("contested_fields", [])
        if contested:
            lines.append(
                f"- **未调和争议字段**: `{', '.join(contested)}`；"
                f"变体 {_clean(item.get('field_variants'))}。"
            )
        if trails:
            lines.append("- **ProxyTrail**:")
            for proxy in trails[:3]:
                bindings = proxy.get("authorized_route_bindings", [])
                binding_text = ", ".join(
                    f"{item.get('action_id', '—')}@"
                    f"{item.get('route_id', '—')}"
                    for item in bindings
                    if isinstance(item, dict)
                ) or "—"
                evidence_links = " ".join(
                    f"[{_clean(citation.get('source'))}]"
                    f"({citation.get('url')})"
                    for citation in proxy.get("evidence", [])[:2]
                    if citation.get("url")
                ) or "无有效引用"
                direction_bindings = "；".join(
                    f"{binding.get('direction', 'AMBIGUOUS')}@"
                    f"R{binding.get('round', '—')}/"
                    f"{binding.get('source_agent') or '—'}/"
                    f"{binding.get('origin_crux') or '—'}/"
                    f"{','.join(binding.get('evidence_ids', [])) or 'no-evidence'}/"
                    f"{binding.get('authorized_action_id') or 'no-action'}"
                    for binding in proxy.get("direction_bindings", [])[:6]
                    if isinstance(binding, dict)
                ) or "—"
                lines.append(
                    f"  - `{proxy.get('proxy_id') or '—'}` / "
                    f"action-route `{binding_text}` / "
                    f"`{proxy.get('direction', 'AMBIGUOUS')}` "
                    f"variants={_clean(proxy.get('direction_variants'))} "
                    f"contested={proxy.get('direction_contested', False)} "
                    f"bindings={_clean(direction_bindings)}；"
                    f"crux `{proxy.get('origin_crux') or '—'}`；"
                    f"计划 {_clean(proxy.get('planned_proxy'))} → "
                    f"实际观察 {_clean(proxy.get('proxy'))}；诊断链: "
                    f"{_clean(proxy.get('causal_link'))}；"
                    f"替代解释: "
                    f"{_clean(proxy.get('alternative_explanation'))}；"
                    f"查询: {_clean(proxy.get('bounded_query'))}；"
                    f"停止: {_clean(proxy.get('stop_condition'))}；"
                    f"路线争议: "
                    f"{_clean(proxy.get('route_contested_fields'))} "
                    f"{_clean(proxy.get('route_field_variants'))}；"
                    f"证据 {len(proxy.get('evidence', []))} 条 {evidence_links}。"
                )
        else:
            lines.append("- **ProxyTrail**: 尚无；先设计一条支持线索和一条反证线索。")
        lines.append("")
    lines.extend(_exploration_history_lines(
        exploration, heading="## 已执行探索与负知识"
    ))
    lines.append("")
    lines.append(
        "`EVIDENCE_BACKED` 在 Insight Cards 中仍不是 OpportunitySeed；"
        "正式晋级必须重新满足 Seed admission、CandidateScreen 与 Claim Verification。"
    )
    return "\n".join(lines).rstrip()


def render_audit(state):
    """Render the complete evidence ledger for explicit audit use."""
    return _render_audit(state, include_title=True)


def render_facts_box(view):
    """Render the deterministic facts layer embedded verbatim in a Decision Brief."""
    verdict = view["verdict"]
    root = view["root_thesis"]
    counts = view["candidate_counts"]
    formal = view["formal_action"]
    exploration_action = view.get("exploration_action") or {}
    runtime = view["runtime"]
    question_type = view.get("question_type", "CONJUNCTIVE")

    def facts_text(value):
        return (
            _clean(value)
            .replace("FACTS_BOX_START", "FACTS-BOX-START")
            .replace("FACTS_BOX_END", "FACTS-BOX-END")
        )

    def summary(items):
        return "；".join(
            f"{facts_text(item.get('id'))} {facts_text(item.get('label'))}"
            for item in items
        ) or "无"

    def table_cell(value, limit=None):
        text = facts_text(value)
        if limit is not None:
            text = text[:limit]
        return text.replace("|", r"\|")

    survived_items = root.get("survived", [])
    falsified_items = root.get("falsified", [])
    monitorable_items = root.get("monitorable", [])
    crux_items = survived_items + falsified_items + monitorable_items
    seen = {item.get("id") for item in crux_items}
    focus = root.get("focus")
    if isinstance(focus, dict) and focus.get("id") not in seen:
        crux_items.append(focus)

    crux_rows = []
    for item in crux_items:
        status = item.get("status")
        status_text = facts_text(status)
        if status in _STATUS:
            status_text += f" · {_STATUS[status]}"
        crux_rows.append(
            f"| {table_cell(item.get('id'))} {table_cell(item.get('label'))} "
            f"| {table_cell(status_text)} "
            f"| {table_cell(item.get('best_bull'), 80)} "
            f"| {table_cell(item.get('best_bear'), 80)} |"
        )

    target = (
        f"（{facts_text(formal.get('candidate'))}）"
        if formal.get("candidate")
        else ""
    )
    as_of_date = view.get("as_of_date")
    if not as_of_date or as_of_date == "—":
        as_of_date = "UNKNOWN"
    forecast_target_date = (
        view.get("forecast_target_date") or "RELATIVE_HORIZON"
    )
    if forecast_target_date == "—":
        forecast_target_date = "RELATIVE_HORIZON"
    temporal = view.get("temporal_contract")
    temporal_line = ""
    if isinstance(temporal, dict):
        temporal_line = (
            f"**时间合同**: 状态={facts_text(temporal.get('status'))} | "
            f"需人工消歧={temporal.get('requires_human_resolution', False)}"
        )
    if question_type == "UNIVERSE_SEARCH":
        crux_summary = (
            f"**研究轴质证**: 正向证据 {summary(survived_items)} | "
            f"负向证据 {summary(falsified_items)} | "
            f"仍需监控 {summary(monitorable_items)}"
        )
    else:
        crux_summary = (
            f"**经质证后**: 活下来 {summary(survived_items)} | "
            f"被推翻 {summary(falsified_items)} | "
            f"仍需监控 {summary(monitorable_items)}"
        )
    landscape = view.get("landscape_map", {})
    landscape_line = ""
    if landscape.get("required"):
        landscape_line = (
            f"**发现路径覆盖**: 计划 {landscape.get('path_count', 0)} | "
            f"SUPPORTED {landscape.get('supported_count', 0)} | "
            f"REJECTED {landscape.get('rejected_count', 0)} | "
            f"UNKNOWN {landscape.get('unknown_count', 0)} | "
            f"UNPROBED {landscape.get('unprobed_count', 0)}"
        )
    lines = [
        "---",
        "<!-- FACTS_BOX_START — 以下内容由 report_v2.py 确定性生成，LLM 不得修改 -->",
        "",
        f"**研究对象**: {facts_text(view['topic'])}",
        f"**决策问题**: {facts_text(view['decision_question'])} | "
        f"**题型**: {facts_text(question_type)} | "
        f"**视野**: {facts_text(view['horizon'])}",
        f"**证据截止**: {facts_text(as_of_date)} | "
        f"**预测目标**: {facts_text(forecast_target_date)}",
    ]
    if temporal_line:
        lines.append(temporal_line)
    grade = view.get("research_grade") or {}
    candidate_lifecycle = grade.get("candidate_lifecycle") or {}
    tiers = grade.get("claim_tiers") or {}
    ev = grade.get("evidence_counts") or {}
    py = grade.get("payload_yield") or {}

    def tier_text(name):
        return "、".join(tiers.get(name) or []) or "无"

    lines.extend([
        f"**结论**: Edge=**{facts_text(verdict['edge_state'])}** | "
        f"方向=**{verdict['evidence_direction']}** | "
        f"可行动性=**{verdict['actionability']}** | "
        f"依据=`{facts_text(verdict.get('reason_code'))}`",
        f"**报告等级**: **{facts_text(grade.get('report_grade', 'UNKNOWN'))}** | "
        f"未满足闸门={facts_text('、'.join(grade.get('unmet_gates') or []) or '无')} | "
        f"对外发布={grade.get('publication_allowed', False)} | "
        f"个股排序={grade.get('ranking_allowed', False)}",
        f"**候选流程（不影响报告等级）**: 筛查="
        f"{facts_text(candidate_lifecycle.get('screening_status', 'UNKNOWN'))} | "
        f"claim核验={facts_text(candidate_lifecycle.get('verification_status', 'UNKNOWN'))} | "
        f"待办={facts_text('、'.join(candidate_lifecycle.get('pending_steps') or []) or '无')} | "
        f"可排序seed={facts_text('、'.join(candidate_lifecycle.get('rankable_seed_ids') or []) or '无')}",
        f"**断言分档**: VERIFIED={facts_text(tier_text('VERIFIED'))} | "
        f"SINGLE_SOURCE={facts_text(tier_text('SINGLE_SOURCE'))} | "
        f"HYPOTHESIS={facts_text(tier_text('HYPOTHESIS'))}",
        f"**运行证据覆盖**: {_execution_round_label(runtime)} | "
        f"{runtime.get('evidence_plane', {}).get('canonical_evidence_item_count', ev.get('valid_citations', 0))} 条正式证据 | "
        f"{runtime['unique_source_count']} 去重来源 URL | "
        f"{runtime.get('independent_publisher_count', ev.get('unique_publishers', 0))} 家独立出版方 | "
        f"{runtime['primary_source_count']} 一级来源 | "
        f"隔离={facts_text(runtime['isolation_status'])}",
        f"**载荷采纳**: 提交 {py.get('submitted', 0)} | 采纳 {py.get('accepted', 0)} | "
        f"丢弃 {py.get('rejected', 0)}（{py.get('discard_rate', 0):.0%}）| "
        f"应交未交 {py.get('omitted', 0)}"
        + (
            f" | 主因 {facts_text(py['top_rejection_reasons'][0][0])}"
            if py.get("top_rejection_reasons") else ""
        ),
        "",
        "| Crux | 状态 | 多头最强证据 | 空头最强证据 |",
        "|------|------|------------|------------|",
        *crux_rows,
        "",
        crux_summary,
    ])
    if landscape_line:
        lines.append(landscape_line)
    candidate_cards = view.get("candidate_cards", [])
    truncated = len(candidate_cards) > 6
    visible = candidate_cards[:6]
    candidate_state_line = _clean("；".join(
        f"{facts_text(card['candidate'])}（{_candidate_gate_label(card)}）"
        for card in visible
    )) or "无"
    if truncated:
        candidate_state_line += f"；另有 {len(candidate_cards) - 6} 个候选（见候选卡片）"
    lines.extend([
        f"**候选线索**: 唯一候选 {counts['lead_count']} 个 | "
        f"可筛选 {counts['ready_for_screening_count']} | "
        f"已筛选 {counts['screened_count']} | "
        f"待核验 {counts['thesis_candidate_count']} | "
        f"可供人工 {counts['verified_for_human_count']}",
        f"**候选状态**: {candidate_state_line}",
        f"**正式动作**: `{facts_text(formal['code'])}`{target} — "
        f"{facts_text(formal['instruction'])}",
        f"**探索动作**: "
        f"`{facts_text(exploration_action.get('action_code'))}`"
        f"（{facts_text(exploration_action.get('hypothesis_id'))}） | "
        f"授权={facts_text(exploration_action.get('authorization_state'))} — "
        f"{facts_text(
            exploration_action.get('instruction')
            or exploration_action.get('reason')
        )}",
        "",
        "> ⚠️ 支持度是辩论强度指标，不是概率。候选线索不是投资建议。",
        "> 完整证据账本见配套 Evidence Ledger 文件。",
        "",
        "<!-- FACTS_BOX_END -->",
        "---",
    ])
    return "\n".join(lines)


def _candidate_name(item):
    ticker = _clean(item.get("ticker"))
    return (
        f"{_clean(item.get('candidate'))}（{ticker}）"
        if ticker != "—"
        else _clean(item.get("candidate"))
    )


def _candidate_source_links(item, limit=3):
    citations = []
    field_evidence = item.get("field_evidence", {}) if isinstance(item, dict) else {}
    if isinstance(field_evidence, dict):
        for values in field_evidence.values():
            if isinstance(values, list):
                citations.extend(value for value in values if isinstance(value, dict))
    bridge_snapshot = (
        item.get("bridge", {}).get("market_snapshot", {})
        if isinstance(item, dict) and isinstance(item.get("bridge"), dict) else {}
    )
    if isinstance(bridge_snapshot, dict):
        citations.extend(
            value for value in bridge_snapshot.get("evidence", [])
            if isinstance(value, dict)
        )
    seen = set()
    links = []
    for citation in citations:
        url = _clean(citation.get("url"))
        if url == "—" or url in seen:
            continue
        seen.add(url)
        label = _clean(
            citation.get("evidence_id") or citation.get("source") or "source"
        )
        links.append(f"[{label}]({url})")
        if len(links) >= limit:
            break
    return "、".join(links) or "—"


def _setup_gap_text(item):
    checks = item.get("setup_checks") if isinstance(item, dict) else {}
    if not isinstance(checks, dict) or not checks:
        return "未声明可核验设置"
    gaps = []
    setup_labels = {
        "ECONOMIC_SETUP": "产业兑现",
        "EVENT_SETUP": "事件驱动",
    }
    field_labels = {
        "mechanism": "作用机制",
        "economic_exposure": "经济暴露",
        "catalyst": "触发条件",
        "price_or_expectation": "价格与预期",
        "crowding_or_position": "拥挤与筹码",
    }

    def fields(values):
        return "、".join(field_labels.get(value, value) for value in values)

    for setup_type, check in checks.items():
        if not isinstance(check, dict) or check.get("ready") is True:
            continue
        parts = []
        if check.get("missing_content"):
            parts.append("缺描述：" + fields(check["missing_content"]))
        if check.get("missing_evidence"):
            parts.append("缺证据：" + fields(check["missing_evidence"]))
        if check.get("conflicting_fields"):
            parts.append("待裁决：" + fields(check["conflicting_fields"]))
        if "INVALID_OR_STALE_CATALYST_WINDOW" in check.get("reason_codes", []):
            parts.append("事件窗口无效或已过期")
        gaps.append(
            f"{setup_labels.get(setup_type, setup_type)}（"
            + ("；".join(parts) or "待核验")
            + "）"
        )
    return "；".join(gaps) if gaps else "条件与字段证据完整"


def _bridge_gap_text(issues):
    """Translate internal bridge diagnostics into a small reader-facing gap set."""
    categories = []
    mappings = (
        ("STALE_CONTEXT", "市场解释待按当前快照重算"),
        ("TRUSTED_MARKET_SNAPSHOT", "缺少同口径可信行情"),
        ("DUAL_UNIVERSE", "经济暴露池与市场交易池尚未同时覆盖"),
        ("MARKET_PHASE", "市场阶段仍缺充分验证"),
        ("VALUE_PATH", "产业价值转移路径仍缺证据闭环"),
        ("ECONOMIC_STRENGTH", "经济暴露强度仍未坐实"),
        ("ALTERNATIVE", "横向替代比较仍不完整"),
        ("COMPARISON", "横向替代比较仍不完整"),
    )
    rows = [str(item or "") for item in issues or []]
    for marker, label in mappings:
        if any(marker in item for item in rows) and label not in categories:
            categories.append(label)
    if not categories and rows:
        categories.append("仍有结构化映射项待核验")
    return "；".join(categories[:3]) or "产业与市场映射完整"


def _setup_lines(items):
    if not items:
        return ["- 当前没有满足完整条件描述的具名载体；保留为探索，不把空白误写成机会。"]
    lines = []
    for item in items:
        window = item.get("catalyst_window") or {}
        expected_by = _clean(window.get("expected_by")) if isinstance(window, dict) else "—"
        lines.extend([
            f"### {item.get('attention_order', '—')}. {_candidate_name(item)}",
            f"- **角色 / 边界**：`{_clean(item.get('market_role'))}` / "
            f"`{_clean(item.get('evidence_boundary'))}`",
            f"- **为何会动**：{_clean(item.get('mechanism'))}",
            f"- **兑现路径**：{_clean(item.get('economic_exposure'))}",
            f"- **触发 / 窗口**：{_clean(item.get('catalyst'))} / {expected_by}",
            f"- **价格与筹码**：{_clean(item.get('price_or_expectation'))}；"
            f"{_clean(item.get('crowding_or_position'))}",
            f"- **失效条件**：{_clean(item.get('invalidation'))}",
            f"- **最强替代解释**：{_clean(item.get('strongest_alternative_explanation'))}",
            f"- **关键来源**：{_candidate_source_links(item)}",
            "",
        ])
    return lines


def _render_opportunity_brief(view):
    """Render the bounded discovery product; it stops at conditional setups."""
    candidate_map = view.get("candidate_map", {})
    candidates = candidate_map.get("candidates", [])
    result_type = candidate_map.get("result_type", "EXPLORE")
    setup_count = sum(
        item.get("attention_band") == "SETUP_CANDIDATE" for item in candidates
    )
    if result_type == "SETUP_READY":
        judgment = (
            f"发现 {setup_count} 个条件描述完整的具名机会；当前顺序只代表优先核验，"
            "成立与否取决于各自触发、失效和价格/筹码条件。"
        )
    elif result_type == "NO_USABLE_SETUP":
        judgment = (
            "在具名载体、替代路径、价格/筹码和事件窗口均已覆盖的范围内，"
            "没有形成可用的条件型机会。"
        )
    else:
        judgment = (
            "已经形成市场路径或具名线索，但关键触发、失效、价格或筹码仍有缺口；"
            "当前应继续低成本判别，不把线索包装成结论。"
        )

    lines = [
        "# Opportunity Brief",
        "",
        f"> **一句话判断｜`{result_type}`**：{judgment}",
        "",
        f"- **主题**：{_clean(view.get('topic'))}",
        f"- **观察时点**：{_clean(view.get('as_of_date'))}",
        f"- **研究视野**：{_clean(view.get('horizon'))}",
        "",
        "## 1. 市场如何运行",
        "",
    ]
    mechanics = candidate_map.get("market_mechanics", [])
    mechanics_fields = [
        ("event_change", "事件变化"),
        ("narrative", "市场叙事"),
        ("capital_flow", "资金扩散"),
        ("carrier_selection", "载体选择"),
        ("crowding_path", "价格与拥挤"),
        ("realization_path", "经济兑现"),
        ("strongest_alternative", "替代解释"),
    ]
    if mechanics:
        for field, label in mechanics_fields:
            values = []
            for item in mechanics:
                value = _clean(item.get(field))
                if value != "—" and value not in values:
                    values.append(value)
            if values:
                lines.append(f"- **{label}**：{'；'.join(values[:2])}")
    else:
        if candidate_map.get("stale_market_mechanics_count"):
            lines.append(
                "- 宿主行情已更新；旧市场机制解释仅留审计历史，当前链条待按同一快照重算。"
            )
        else:
            lines.append("- 尚未形成结构化的事件 → 叙事 → 资金 → 载体 → 兑现链；这是当前首要缺口。")

    lines.extend([
        "",
        "## 2. 具体候选地图",
        "",
        "| 核验序 | 具名载体 | 市场角色 | 设置类型 | 作用机制 | 证据边界 | 完整度 | 关键缺口 |",
        "|---:|---|---|---|---|---|---|---|",
    ])
    if candidates:
        for item in candidates:
            lines.append(
                f"| {item.get('attention_order', '—')} | {_cell(_candidate_name(item))} | "
                f"{_cell(' / '.join(item.get('market_roles') or [item.get('market_role')]))} | "
                f"{_cell(' / '.join(item.get('setup_types') or ['仅观察']))} | "
                f"{_cell(item.get('mechanism'))} | `{_cell(item.get('evidence_boundary'))}` | "
                f"`{_cell(item.get('attention_band'))}` | {_cell(_setup_gap_text(item))} |"
            )
    else:
        lines.append("| — | 未发现具名载体 | — | — | — | `HYPOTHESIS` | `EXPLORE` | 具名映射缺失 |")

    event_items = [
        item for item in candidate_map.get("event_setups", [])
        if item.get("attention_band") == "SETUP_CANDIDATE"
    ]
    economic_items = [
        item for item in candidate_map.get("economic_setups", [])
        if item.get("attention_band") == "SETUP_CANDIDATE"
    ]
    lines.extend(["", "## 3. 事件驱动设置", ""])
    lines.extend(_setup_lines(event_items))
    lines.extend(["## 4. 产业兑现设置", ""])
    lines.extend(_setup_lines(economic_items))

    lines.extend(["## 5. 情景树", ""])
    scenario_rows = []
    scenario = view.get("scenario_paths", {})
    for path in scenario.get("paths", []) if isinstance(scenario, dict) else []:
        scenario_rows.append({
            "name": path.get("path_type"),
            "outcome": path.get("summary"),
            "trigger": path.get("trigger_event"),
            "transmission": path.get("transmission_chain"),
            "falsifier": path.get("falsifier"),
        })
    if not scenario_rows:
        # Candidate-specific scenario labels support event shapes such as full
        # success / partial success / failure / delay without forcing odds.
        seen = set()
        for item in candidates:
            for name, outcome in (item.get("scenario_fit") or {}).items():
                key = (_clean(name), _clean(outcome))
                if key in seen or key[1] == "—":
                    continue
                seen.add(key)
                scenario_rows.append({
                    "name": name,
                    "outcome": outcome,
                    "trigger": item.get("catalyst"),
                    "transmission": item.get("mechanism"),
                    "falsifier": item.get("invalidation"),
                })
    if scenario_rows:
        lines.extend([
            "| 情景 | 可观察结果 | 触发 | 市场传导 | 失效/反证 |",
            "|---|---|---|---|---|",
        ])
        for row in scenario_rows[:8]:
            lines.append(
                f"| {_cell(row.get('name'))} | {_cell(row.get('outcome'))} | "
                f"{_cell(row.get('trigger'))} | {_cell(row.get('transmission'))} | "
                f"{_cell(row.get('falsifier'))} |"
            )
    else:
        lines.append("- 情景尚未结构化；不得用单一路径代替成功、部分兑现、失败与延期分支。")

    lines.extend([
        "",
        "## 6. 触发与失效总表",
        "",
        "| 具名载体 | 触发 | 失效 | 价格/预期 | 筹码/拥挤 |",
        "|---|---|---|---|---|",
    ])
    if candidates:
        for item in candidates:
            lines.append(
                f"| {_cell(_candidate_name(item))} | {_cell(item.get('catalyst'))} | "
                f"{_cell(item.get('invalidation'))} | {_cell(item.get('price_or_expectation'))} | "
                f"{_cell(item.get('crowding_or_position'))} |"
            )
    else:
        lines.append("| — | — | — | — | — |")

    lines.extend([
        "",
        "## 7. 证据边界",
        "",
        "- `FACT`：至少两个独立发布方的有效来源直接支持该映射。",
        "- `SINGLE_SOURCE`：只有一个有效发布方，尚未交叉核验。",
        "- `INFERENCE`：来源支持事实底座，但从事实到载体的映射仍是推断。",
        "- `HYPOTHESIS`：尚无有效来源；保留为待验证线索。",
    ])
    for item in candidates:
        citations = item.get("evidence", [])
        if not citations:
            continue
        links = []
        for citation in citations[:3]:
            source = _clean(citation.get("source"))
            url = _clean(citation.get("url"))
            date = _clean(citation.get("date"))
            links.append(f"[{source}（{date}）]({url})")
        lines.append(
            f"- **{_candidate_name(item)}** `{_clean(item.get('evidence_boundary'))}`："
            + "；".join(links)
        )

    coverage = candidate_map.get("coverage", {})
    research_grade = view.get("research_grade", {})
    framing = view.get("framing", {})
    verdict = view.get("verdict", {})
    lines.extend([
        "",
        "## 8. 最便宜的下一项检验",
        "",
        f"- { _clean(candidate_map.get('cheapest_next_test')) }",
        "",
        "## 9. 审计附录",
        "",
        f"- **结果类型**：`{result_type}`",
        f"- **具名载体数**：{len(candidates)}",
        f"- **完整条件设置数**：{setup_count}",
        f"- **覆盖检查**：具名载体={'是' if coverage.get('concrete_instrument_search') else '否'}；"
        f"替代路径={'是' if coverage.get('alternative_paths') else '否'}；"
        f"价格/筹码={'是' if coverage.get('price_and_crowding') else '否'}；"
        f"事件窗口={'是' if coverage.get('event_window') else '否'}",
        f"- **执行真实性**：`{_clean(view.get('runtime', {}).get('execution_integrity', {}).get('execution_mode'))}`；"
        f"{_execution_round_label(view.get('runtime', {}))}",
        f"- **研究底座等级**：`{_clean(research_grade.get('report_grade'))}`；"
        f"未满足项={_clean(', '.join(research_grade.get('unmet_gates', [])))}",
        f"- **证据姿态**：{_clean(verdict.get('edge_state'))} / "
        f"{_clean(verdict.get('evidence_direction'))} / {_clean(verdict.get('actionability'))}",
        f"- **立题质量**：`{_clean(framing.get('quality_status'))}`",
        "- **边界**：本报告止于条件型机会摘要；核验序不是收益排序，也不构成操作建议。",
    ])
    for premise in framing.get("premise_audit", [])[:5]:
        lines.append(
            f"- **立题前提** `{_clean(premise.get('status'))}`："
            f"{_clean(premise.get('claim'))}（as-of={_clean(premise.get('as_of'))}）"
        )
    notes = candidate_map.get("coverage_notes", [])
    for note in notes[:3]:
        lines.append(f"- **覆盖备注**：{_clean(note)}")
    for route in candidate_map.get("coverage_routes", [])[:8]:
        lines.append(
            f"- **覆盖路径 `{_clean(route.get('coverage_field'))}` / "
            f"`{_clean(route.get('route_kind'))}`**："
            f"{_clean(route.get('query'))} -> `{_clean(route.get('outcome'))}`；"
            f"检查={_clean(', '.join(route.get('checked_urls', [])))}"
        )
    if candidate_map.get("missing_route_kinds"):
        lines.append(
            "- **候选空间尚缺路径**："
            + _clean(", ".join(candidate_map.get("missing_route_kinds", [])))
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_deep_research_report(view):
    """Render the topic-led research product with explicit, bounded advice."""
    agenda = view.get("research_agenda", {})
    questions = agenda.get("questions", [])
    directions = agenda.get("research_directions", [])
    evidence_items = agenda.get("evidence_items", [])
    evidence_plane = view.get("evidence_plane", {})
    blind_spots = agenda.get("blind_spots", [])
    baseline_findings = agenda.get("baseline_findings", [])
    candidate_map = view.get("candidate_map", {})
    market_bridge = view.get("market_bridge", {})
    candidates = candidate_map.get("candidates", [])
    setup_candidates = [
        item for item in candidates
        if item.get("attention_band") == "SETUP_CANDIDATE"
    ]
    answered = [item for item in questions if item.get("answer_status") == "ANSWERED"]
    addressed = [item for item in questions if research_kernel.answer_has_progress(item)]
    unresolved = [item for item in questions if item.get("answer_status") != "ANSWERED"]
    initial_questions = [
        item for item in questions if int(item.get("first_seen_round", 0) or 0) == 0
    ]
    derived_questions = sorted(
        [item for item in questions if int(item.get("first_seen_round", 0) or 0) > 0],
        key=lambda item: (
            0 if research_kernel.answer_has_progress(item) else 1,
            0 if item.get("blocks_current_recommendation") is True else 1,
            {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(item.get("decision_impact"), 3),
            -int(item.get("first_seen_round", 0) or 0),
            item.get("question_id", ""),
        ),
    )
    display_questions = initial_questions + derived_questions[
        :max(0, 10 - len(initial_questions))
    ]
    display_directions = sorted(
        directions,
        key=lambda item: (
            0 if item.get("origin") == "ROUND_DISCOVERY" else 1,
            0 if item.get("next_move") == "OPEN_NEW_DIRECTION" else 1,
            0 if item.get("load_bearing") is True else 1,
            item.get("direction_id", ""),
        ),
    )[:8]
    display_blind_spots = sorted(
        blind_spots,
        key=lambda item: (
            0 if item.get("blocks_current_recommendation") is True else 1,
            {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(item.get("decision_impact"), 3),
            0 if item.get("research_cost") == "LOW" else 1,
            -int(item.get("first_seen_round", 0) or 0),
            item.get("blind_spot_id", ""),
        ),
    )[:8]
    display_candidates = candidates[:10]
    result_type = candidate_map.get("result_type", "EXPLORE")
    research_grade = view.get("research_grade", {})
    research_control = view.get("research_control", {})
    material_change = view.get("material_change", {})
    material_gate = material_change.get("delivery_gate", {})
    material_ready = material_gate.get("decision_ready") is True
    material_items = material_change.get("current_items", [])
    material_leads = material_change.get("open_leads", [])
    material_coverage = material_change.get("coverage", [])
    mechanics = candidate_map.get("market_mechanics", [])
    priorities_by_horizon = market_bridge.get("priorities_by_horizon", {})
    bridge_priority_count = int(market_bridge.get("priority_count", 0) or 0)
    bridge_result_type = market_bridge.get("result_type", "NO_CANDIDATE_MAP")

    if not material_ready:
        conclusion = (
            f"当前存在 {material_gate.get('blocker_count', 0)} 个重大事实门缺口；"
            "报告可以交付研究进展，但不得把当前结论或标的排序表述为完整、"
            "当期有效的决策建议。先补齐事实面或核实已知重大线索。"
        )
    elif bridge_priority_count:
        conclusion = (
            f"课题已形成 {bridge_priority_count} 个按时间视野区分的横向条件性优先项；"
            "它们同时说明产业价值路径、市场载体选择、最接近替代项和切换条件，"
            "不再由字段完整度自动生成推荐。"
        )
    elif setup_candidates:
        conclusion = (
            f"已有 {len(setup_candidates)} 个字段和证据较完整的具名设置，但尚未形成"
            "有效的产业—市场横向比较；完整性不等于吸引力，因此当前不输出条件性优先项。"
        )
    elif result_type == "NO_USABLE_SETUP":
        conclusion = (
            "在具名载体、价格/筹码、事件窗口及经济链、市场载体、竞争替代、"
            "失败分支、资本关系五类候选路径均已覆盖的范围内，"
            "没有形成可用的条件型机会；应报告负结果，同时保留新盲点带来的重开条件。"
        )
    elif candidates:
        conclusion = (
            f"课题已映射 {len(candidates)} 个具名载体，但尚未形成条件完整的设置；"
            "当前最有价值的动作是补齐价格/筹码、催化或失效条件，而不是停止机会挖掘。"
        )
    else:
        conclusion = (
            "当前轮次尚未形成可信的具名载体映射；这表示研究仍有结构性空白，"
            "不表示课题没有潜在市场机会。"
        )

    lines = [
        "# Deep Research Report",
        "",
        f"> **核心判断｜`{bridge_result_type}`**：{conclusion}",
        "",
        f"- **研究课题**：{_clean(agenda.get('research_objective') or view.get('decision_question'))}",
        f"- **主题 / 时点 / 视野**：{_clean(view.get('topic'))} / "
        f"{_clean(view.get('as_of_date'))} / {_clean(view.get('horizon'))}",
        f"- **进展**：完整回答 {len(answered)}；已有证据边界的阶段性答案 "
        f"{len(addressed)}；问题总数 {len(questions)}；"
        f"研究方向 {len(directions)}（活跃 {agenda.get('active_direction_count', 0)}）；"
        f"正式证据 {len(evidence_items)}（一手 "
        f"{evidence_plane.get('primary_source_count', 0)}；宿主行情 "
        f"{evidence_plane.get('host_market_evidence_count', 0)}；独立发布方 "
        f"{evidence_plane.get('independent_publisher_count', 0)}）；"
        f"新增盲点 {len(blind_spots)}；交付状态 "
        f"`{_clean(research_control.get('product_readiness'))}`",
        f"- **是否建议续研**："
        f"{'是（需额外授权）' if research_control.get('more_research_recommended') else '否'}；"
        f"当前最低成本动作=`{_clean(research_control.get('next_test_mode'))}`；"
        f"原因={_clean(', '.join(research_control.get('reason_codes', [])))}",
        f"- **候选字段完整性**：`{_clean(result_type)}`；它不决定推荐权。",
        "",
        "### 当前事实门（先看这里）",
        "",
        f"- **状态**：`{_clean(material_gate.get('status'))}`；"
        f"decision-ready={'是' if material_ready else '否'}；"
        f"阻断项={material_gate.get('blocker_count', 0)}。",
    ]
    if material_items:
        lines.extend([
            "- **会改写结论的当前变化**：",
            "",
            "| 影响 | 主体 | 生效日 | 变化 | 为什么重要 | 边界 |",
            "|---|---|---|---|---|---|",
        ])
        for item in material_items[:8]:
            lines.append(
                f"| `{_cell(item.get('decision_impact'))}` | "
                f"{_cell(item.get('entity_name'))} | {_cell(item.get('effective_date'))} | "
                f"{_cell(item.get('claim'))} | {_cell(item.get('materiality_rationale'))} | "
                f"`{_cell(item.get('status'))}` |"
            )
    else:
        lines.append("- **当前变化**：尚未登记会改写结论的已核实变化。")
    if material_leads:
        lines.append(
            "- **尚未核实的重大线索**：" + "；".join(
                f"{_clean(item.get('claim'))}（{_clean(item.get('source_url'))}）"
                for item in material_leads[:5]
            )
        )
    missing_coverage = [
        item for item in material_coverage
        if item.get("outcome") in {"MISSING", "INSUFFICIENT"}
    ]
    if missing_coverage:
        lines.append(
            "- **未完成事实面**：" + "、".join(
                f"{_clean(item.get('entity_name'))}/{_clean(item.get('route_kind'))}"
                for item in missing_coverage[:8]
            )
        )
    lines.extend([
        "",
        "## 1. 结论与建议",
        "",
    ])
    if not material_ready:
        lines.append(
            "- **当前不输出 decision-ready 推荐**：以下候选、价值路径与市场映射"
            "仍作为研究线索保留；它们不能越过重大事实门。"
        )
    elif bridge_priority_count:
        horizon_labels = {
            "EVENT_DAYS": "事件窗口",
            "TACTICAL_WEEKS": "战术数周",
            "EARNINGS_QUARTERS": "财报季度",
            "STRUCTURAL_YEARS": "长期产业",
        }
        rendered = 0
        for horizon in (
            "EVENT_DAYS", "TACTICAL_WEEKS", "EARNINGS_QUARTERS", "STRUCTURAL_YEARS"
        ):
            for item in priorities_by_horizon.get(horizon, []):
                if rendered >= 8:
                    break
                bridge = item.get("bridge", {})
                alternative = bridge.get("closest_alternative", {})
                alternative_name = _candidate_name(alternative) if alternative else "—"
                phase = market_bridge.get("phase_by_horizon", {}).get(horizon, {})
                rendered += 1
                lines.extend([
                    f"### {horizon_labels.get(horizon, horizon)}：条件性优先关注 {_candidate_name(item)}",
                    f"- **产业 × 市场投影**：`{_clean(bridge.get('projection'))}` / "
                    f"`{_clean(bridge.get('recommendation_level'))}`；当前阶段="
                    f"`{_clean(phase.get('phase'))}`（{_phase_status_text(phase.get('status'))}）",
                    f"- **产业依据**：{_clean(bridge.get('economic_exposure_strength', {}).get('rationale'))}",
                    f"- **市场选择依据**：{_clean(bridge.get('market_recognition', {}).get('rationale'))}",
                    f"- **相对选择**：当前相对 {alternative_name} 优先，因为"
                    f"{_clean(bridge.get('why_prefer_now'))}",
                    f"- **切换条件**：{_clean(bridge.get('switch_condition'))}",
                    f"- **失效 / 边界**：{_clean(item.get('invalidation'))}；"
                    f"产业强度={_clean(bridge.get('economic_exposure_strength', {}).get('effective'))}；"
                    f"市场确认={_clean(bridge.get('market_recognition', {}).get('effective'))}",
                    f"- **关键来源**：{_candidate_source_links(item)}",
                    "",
                ])
            if rendered >= 8:
                break
    elif setup_candidates:
        lines.append(
            "- **当前无横向条件性优先项**：以下完整 setup 仍缺价值路径、时间阶段或"
            "有效替代比较，不能仅凭字段齐全升级为推荐："
            + "、".join(_candidate_name(item) for item in setup_candidates[:5]) + "。"
        )
    elif candidates:
        for index, item in enumerate(candidates[:5], start=1):
            bridge = item.get("bridge", {})
            lines.extend([
                f"- **研究优先级 {index}｜{_candidate_name(item)}**："
                f"{_phrase(item.get('mechanism'))}。产业×市场投影="
                f"`{_clean(bridge.get('projection'))}`；下一步先验证"
                f"{_phrase(item.get('cheap_discriminating_test'))}；当前缺口="
                f"{_clean(_setup_gap_text(item))} / "
                f"{_clean(_bridge_gap_text(bridge.get('issues', [])))}。"
                f"来源={_candidate_source_links(item)}",
            ])
    else:
        lines.append(
            "- **建议**：按 Research Agenda 的未回答问题继续搜索，并强制完成具体载体、"
            "价格/筹码、事件窗口，以及经济链、市场载体、竞争替代、失败分支和"
            "资本关系五类候选空间映射。"
        )

    lines.extend([
        "",
        "## 2. 课题拆解与逐轮答案",
        "",
        "| 状态 | 研究问题 | 当前答案 | 最强质证 | 尚缺信息 | 证据边界 |",
        "|---|---|---|---|---|---|",
    ])
    if display_questions:
        for item in display_questions:
            lines.append(
                f"| `{_cell(item.get('answer_status'))}` | {_cell(item.get('question'))} | "
                f"{_cell(item.get('current_answer'))} | "
                f"{_cell(item.get('strongest_challenge'))} | "
                f"{_cell(item.get('missing_information'))} | "
                f"`{_cell(item.get('evidence_boundary'))}` |"
            )
    else:
        lines.append("| `OPEN` | 归档运行未记录 Research Agenda | — | — | 需重建立题工作单 | `HYPOTHESIS` |")
    if len(questions) > len(display_questions):
        lines.append(
            f"\n> 默认正文仅显示初始问题及最有信息量的新问题；另有 "
            f"{len(questions) - len(display_questions)} 项保留在审计视图。"
        )
    if baseline_findings:
        lines.extend([
            "",
            "### 既有关键发现处置（仅用于重跑防遗漏）",
            "",
            "| 处置 | 既有发现 | 为什么重要 | 本轮理由 | 本轮证据 |",
            "|---|---|---|---|---|",
        ])
        for item in baseline_findings[:8]:
            lines.append(
                f"| `{_cell(item.get('disposition'))}` | {_cell(item.get('claim'))} | "
                f"{_cell(item.get('why_it_matters'))} | {_cell(item.get('rationale'))} | "
                f"{_cell(', '.join(item.get('evidence_ids', [])))} |"
            )
        lines.append(
            "\n> 既有发现只是检索线索；只有本轮 canonical evidence 才能标记为 "
            "`REVERIFIED` 或 `SUPERSEDED`。"
        )

    lines.extend([
        "",
        "## 3. 研究方向判断与新观点",
        "",
        "| 判断 | 证据边界 | 类型 | 待质证论点/方向 | 本轮结论 | 下一研究动作 | 最强反例 |",
        "|---|---|---|---|---|---|---|",
    ])
    if display_directions:
        for item in display_directions:
            lines.append(
                f"| `{_cell(item.get('research_judgment'))}` | "
                f"`{_cell(item.get('evidence_boundary'))}` | "
                f"{_cell(item.get('direction_kind'))} | {_cell(item.get('proposition'))} | "
                f"{_cell(item.get('rationale'))} | `{_cell(item.get('next_move'))}` | "
                f"{_cell(item.get('strongest_challenge'))} |"
            )
    else:
        lines.append("| `UNRESOLVED` | `HYPOTHESIS` | — | 归档运行未记录研究方向 | — | `CONTINUE` | — |")
    if len(directions) > len(display_directions):
        lines.append(f"\n> 另有 {len(directions) - len(display_directions)} 条方向保留在审计视图。")
    new_directions = [
        item for item in directions if item.get("origin") == "ROUND_DISCOVERY"
    ]
    if new_directions:
        lines.extend(["", "### 由质证产生的新观点", ""])
        for item in new_directions[:5]:
            lines.append(
                f"- **{_clean(item.get('proposition'))}**：来源="
                f"{_clean(item.get('origin_reason'))}；会改变="
                f"{_clean(item.get('why_it_matters'))}；判别测试="
                f"{_clean(item.get('discriminating_test'))}。"
            )
        if len(new_directions) > 5:
            lines.append(f"- 其余 {len(new_directions) - 5} 条新方向保留在审计视图。")

    lines.extend(["", "## 4. 产业价值转移与市场时间结构", ""])
    value_paths = market_bridge.get("value_paths", [])
    if value_paths:
        lines.extend(["### 产业价值转移", ""])
        for item in value_paths[:8]:
            lines.append(
                f"- **`{_clean(item.get('path_id'))}`｜{_clean(item.get('realization_horizon'))}**："
                f"{_clean(item.get('state_change'))} → {_clean(item.get('constraint_change'))} → "
                f"{_clean(item.get('profit_pool_shift'))}；证伪={_clean(item.get('falsifier'))}；"
                f"边界=`{_clean(item.get('evidence_boundary'))}`。"
            )
    else:
        lines.append("- 尚未形成可回指 Research Agenda 的价值转移路径。")

    universe_by_horizon = market_bridge.get("universe_by_horizon", {})
    host_snapshots = market_bridge.get("host_market_snapshots", [])
    lines.extend(["", "### 当前宿主可信市场快照（权威数据平面）", ""])
    if host_snapshots:
        lines.extend([
            "| 标的 | 会话 | 5日超额 | 20日超额 | 60日超额 | 20日量比 | 换手率 | 回执 |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ])
        for entry in sorted(
            host_snapshots,
            key=lambda item: (
                _clean(item.get("market_session_date")),
                _clean(item.get("candidate_identity")),
            ),
            reverse=True,
        )[:12]:
            snapshot = entry.get("market_snapshot", {})
            candidate = entry.get("candidate", {})
            label = _clean(candidate.get("name"))
            if candidate.get("ticker"):
                label += f"（{_clean(candidate.get('ticker'))}）"
            lines.append(
                f"| {_cell(label)} | {_cell(entry.get('market_session_date'))} | "
                f"{_cell(snapshot.get('excess_5d'))} | {_cell(snapshot.get('excess_20d'))} | "
                f"{_cell(snapshot.get('excess_60d'))} | "
                f"{_cell(snapshot.get('volume_ratio_20d'))} | "
                f"{_cell(snapshot.get('turnover_rate'))} | "
                f"`{_cell(entry.get('receipt_id'))}` |"
            )
        lines.append(
            "\n> 本表由宿主回执绑定，优先于角色叙事中的‘无行情/行情未知’历史表述；"
            "角色解释只能解释这些事实，不能覆盖其存在性。"
        )
    else:
        lines.append("- 未摄入宿主可信行情；价格、相对强弱与拥挤判断保持降级。")

    lines.extend(["", "### 经济暴露池 × 市场交易池", ""])
    if universe_by_horizon:
        lines.extend([
            "| 时间视野 | 双池覆盖 | 经济暴露池 | 市场交易池 | 构造规则 |",
            "|---|---|---|---|---|",
        ])
        for horizon in (
            "EVENT_DAYS", "TACTICAL_WEEKS", "EARNINGS_QUARTERS", "STRUCTURAL_YEARS"
        ):
            universe = universe_by_horizon.get(horizon)
            if not universe:
                continue
            economic = universe.get("types", {}).get("ECONOMIC_EXPOSURE", {})
            market = universe.get("types", {}).get("MARKET_TRADING", {})
            economic_snapshots = economic.get("snapshots", [])
            market_snapshots = market.get("snapshots", [])
            economic_first = economic_snapshots[0] if economic_snapshots else {}
            market_first = market_snapshots[0] if market_snapshots else {}
            rules = "；".join(filter(None, [
                _clean(economic_first.get("construction_rule")),
                _clean(market_first.get("construction_rule")),
            ]))
            lines.append(
                f"| `{_cell(horizon)}` | {'完整' if universe.get('complete') else '不足'} | "
                f"{_cell(economic_first.get('universe_name'))} "
                f"({len(economic.get('member_identities', []))}) | "
                f"{_cell(market_first.get('universe_name'))} "
                f"({len(market.get('member_identities', []))}) | {_cell(rules)} |"
            )
    else:
        lines.append("- 尚未冻结经济暴露池与市场交易池；两只候选互相比不能证明方向覆盖。")

    phase_by_horizon = market_bridge.get("phase_by_horizon", {})
    lines.extend(["", "### 市场时间结构", ""])
    if phase_by_horizon:
        lines.extend([
            "| 时间视野 | 阶段判断 | 状态 | 当前主要定价变量 | 产业时钟 | 市场时钟 | 最强替代解释 |",
            "|---|---|---|---|---|---|---|",
        ])
        for horizon in (
            "EVENT_DAYS", "TACTICAL_WEEKS", "EARNINGS_QUARTERS", "STRUCTURAL_YEARS"
        ):
            phase = phase_by_horizon.get(horizon)
            if not phase:
                continue
            snapshots = phase.get("snapshots", [])
            first = snapshots[0] if snapshots else {}
            alternatives = "；".join(
                _clean(item.get("strongest_alternative_phase"))
                for item in snapshots[:2]
            )
            lines.append(
                f"| `{_cell(horizon)}` | `{_cell(phase.get('phase'))}` | "
                f"{_cell(_phase_status_text(phase.get('status')))} | "
                f"{_cell(first.get('dominant_pricing_variable'))} | "
                f"{_cell(first.get('industry_clock'))} | {_cell(first.get('market_clock'))} | "
                f"{_cell(alternatives)} |"
            )
    else:
        lines.append("- 尚未形成带 as-of 和证据的市场阶段判断；不得用固定天数假装阶段推进。")

    lines.extend(["", "### 事件—资金—载体运行链", ""])
    mechanics_fields = [
        ("event_change", "事件变化"),
        ("narrative", "叙事形成"),
        ("capital_flow", "资金扩散"),
        ("carrier_selection", "载体选择"),
        ("crowding_path", "价格与筹码反馈"),
        ("realization_path", "产业兑现"),
        ("strongest_alternative", "最强替代解释"),
    ]
    if mechanics:
        for field, label in mechanics_fields:
            values = []
            for item in mechanics:
                value = _clean(item.get(field))
                if value != "—" and value not in values:
                    values.append(value)
            if values:
                lines.append(f"- **{label}**：{'；'.join(values[:3])}")
    else:
        if candidate_map.get("stale_market_mechanics_count"):
            lines.append(
                "- 宿主行情已在既有市场机制解释之后更新；旧解释仅留审计历史，"
                "当前事件 → 资金 → 载体链等待同一快照上下文重算。"
            )
        else:
            lines.append("- 尚未形成事件 → 叙事 → 资金 → 载体 → 产业兑现链；应作为下一轮首要任务。")

    lines.extend([
        "",
        "## 5. 具体载体与机会结构",
        "",
        "| 核验序 | 具名载体 | 产业×市场投影 | 市场角色 | 时间视野 | 作用机制 | 相对替代 | 边界 |",
        "|---:|---|---|---|---|---|---|---|",
    ])
    if display_candidates:
        for item in display_candidates:
            bridge = item.get("bridge", {})
            alternative = bridge.get("closest_alternative", {})
            lines.append(
                f"| {item.get('attention_order', '—')} | {_cell(_candidate_name(item))} | "
                f"`{_cell(bridge.get('projection'))}` / "
                f"`{_cell(bridge.get('recommendation_level'))}` | "
                f"{_cell(' / '.join(item.get('market_roles') or [item.get('market_role')]))} | "
                f"{_cell(' / '.join(bridge.get('horizon_fit') or ['未建立']))} | "
                f"{_cell(item.get('mechanism'))} | "
                f"{_cell(_candidate_name(alternative) if alternative else '—')}；"
                f"{_cell(bridge.get('why_prefer_now'))} | "
                f"`{_cell(item.get('evidence_boundary'))}`；"
                f"{_cell(_bridge_gap_text(bridge.get('issues', [])))}；"
                f"{_candidate_source_links(item)} |"
            )
    else:
        lines.append("| — | 尚无具名载体 | — | — | — | — | — | `HYPOTHESIS` |")
    if len(candidates) > len(display_candidates):
        lines.append(f"\n> 另有 {len(candidates) - len(display_candidates)} 个探索候选保留在审计视图。")

    event_items = [item for item in candidate_map.get("event_setups", []) if item in setup_candidates]
    economic_items = [item for item in candidate_map.get("economic_setups", []) if item in setup_candidates]
    lines.extend(["", "## 6. 事件驱动与产业链兑现", "", "### 事件驱动", ""])
    lines.extend(_setup_lines(event_items))
    lines.extend(["### 产业链兑现", ""])
    lines.extend(_setup_lines(economic_items))

    lines.extend(["## 7. 新盲点与前瞻推演", ""])
    if display_blind_spots:
        for item in display_blind_spots:
            lines.extend([
                f"### {_clean(item.get('statement'))}",
                f"- **为何此前容易漏掉**：{_clean(item.get('why_missed'))}",
                f"- **可能改变什么**：{_clean(item.get('potential_impact'))}",
                f"- **最低成本验证**：{_clean(item.get('cheapest_test'))}",
                "",
            ])
    else:
        lines.append("- 尚未记录新盲点；下一轮必须追问二阶影响、失败受益者、替代解释与价格反身性。")
    if len(blind_spots) > len(display_blind_spots):
        lines.append(f"- 其余 {len(blind_spots) - len(display_blind_spots)} 项盲点保留在审计视图。")

    lines.extend(["## 8. 情景、触发与失效", ""])
    scenario = view.get("scenario_paths", {})
    paths = scenario.get("paths", []) if isinstance(scenario, dict) else []
    if paths:
        lines.extend([
            "| 情景 | 可观察结果 | 触发 | 传导 | 失效/反证 |",
            "|---|---|---|---|---|",
        ])
        for path in paths[:8]:
            lines.append(
                f"| {_cell(path.get('path_type'))} | {_cell(path.get('summary'))} | "
                f"{_cell(path.get('trigger_event'))} | {_cell(path.get('transmission_chain'))} | "
                f"{_cell(path.get('falsifier'))} |"
            )
    else:
        candidate_paths = []
        seen_paths = set()
        for item in candidates[:5]:
            for name, outcome in (item.get("scenario_fit") or {}).items():
                key = (_clean(name), _clean(outcome), _candidate_name(item))
                if key in seen_paths or key[1] == "—":
                    continue
                seen_paths.add(key)
                candidate_paths.append((item, name, outcome))
        if candidate_paths:
            lines.extend([
                "| 载体 | 情景 | 可观察结果 | 触发 | 失效/反证 |",
                "|---|---|---|---|---|",
            ])
            for item, name, outcome in candidate_paths[:12]:
                lines.append(
                    f"| {_cell(_candidate_name(item))} | {_cell(name)} | {_cell(outcome)} | "
                    f"{_cell(item.get('catalyst'))} | {_cell(item.get('invalidation'))} |"
                )
        else:
            for item in candidates[:5]:
                lines.append(
                    f"- **{_candidate_name(item)}**：触发={_clean(item.get('catalyst'))}；"
                    f"失效={_clean(item.get('invalidation'))}；"
                    f"替代解释={_clean(item.get('strongest_alternative_explanation'))}。"
                )
            if not candidates:
                lines.append("- 情景尚未结构化。")

    lines.extend([
        "",
        "## 9. 未回答问题与下一验证动作",
        "",
    ])
    next_question_ids = {
        item.get("question_id")
        for item in research_control.get("next_questions", [])
        if isinstance(item, dict)
    }
    next_questions = [
        item for item in unresolved if item.get("question_id") in next_question_ids
    ] or unresolved[:5]
    if next_questions:
        for item in next_questions[:5]:
            lines.append(
                f"- `{_clean(item.get('answer_status'))}` **{_clean(item.get('question'))}**："
                f"`{_clean(item.get('next_test_availability') or 'UNKNOWN')}` — "
                f"{_clean(item.get('next_question') or item.get('missing_information') or item.get('success_condition'))}"
            )
    elif questions:
        lines.append("- 当前工作单问题均已回答；仅在新事实或盲点改变结论时继续扩展。")
    else:
        lines.append("- 归档运行未记录 Research Agenda；需先重建课题工作单，不能视为问题均已回答。")
    active_directions = [
        item for item in directions if item.get("next_move") != "ANSWER"
    ]
    for item in active_directions[:5]:
        lines.append(
            f"- **方向 `{_clean(item.get('direction_id'))}`｜"
            f"{_clean(item.get('next_move'))}｜"
            f"`{_clean(item.get('next_test_availability') or 'UNKNOWN')}`**："
            f"{_clean(item.get('unresolved_question') or item.get('discriminating_test'))}"
        )
    deferred = research_control.get("deferred_next_tests", [])
    if deferred:
        lines.extend(["", "### 等待新信息的验证（不应消耗新一轮搜索）", ""])
        for item in deferred[:8]:
            lines.append(
                f"- `{_clean(item.get('availability'))}` "
                f"`{_clean(item.get('kind'))}:{_clean(item.get('id'))}` — "
                f"{_clean(item.get('test'))}"
            )
    lines.append(f"- **最便宜的总体下一检验**：{_clean(candidate_map.get('cheapest_next_test'))}")
    for note in candidate_map.get("coverage_notes", [])[:5]:
        lines.append(f"- **覆盖备注**：{_clean(note)}")
    for route in candidate_map.get("coverage_routes", [])[:8]:
        lines.append(
            f"- **覆盖路径 `{_clean(route.get('coverage_field'))}` / "
            f"`{_clean(route.get('route_kind'))}`**："
            f"{_clean(route.get('query'))} -> `{_clean(route.get('outcome'))}`；"
            f"检查={_clean(', '.join(route.get('checked_urls', [])))}"
        )
    if candidate_map.get("missing_route_kinds"):
        lines.append(
            "- **候选空间尚缺路径**："
            + _clean(", ".join(candidate_map.get("missing_route_kinds", [])))
        )

    lines.extend([
        "",
        "## 10. 证据边界与方法限制",
        "",
        "- `FACT`：至少两个独立发布方的有效来源直接支持；`SINGLE_SOURCE`：单一发布方；",
        "  `INFERENCE`：事实底座存在但结论仍含映射推断；`HYPOTHESIS`：待验证研究线索。",
        f"- **未满足研究闸**：{_clean(', '.join(research_grade.get('unmet_gates', [])))}",
        f"- **兼容审计等级**：`{_clean(research_grade.get('report_grade'))}`；"
        "它衡量旧证据工作流完成度，不衡量机会质量。",
        f"- **研究控制**：`{_clean(research_control.get('recommended_action'))}`；"
        "该状态由 Agenda 的可回答性与高影响低成本盲点决定；"
        "FORMAL/PROVISIONAL 仅为兼容审计等级。",
        f"- **执行真实性 / 证据**："
        f"`{_clean(view.get('runtime', {}).get('execution_integrity', {}).get('execution_mode'))}`；"
        f"{_execution_round_label(view.get('runtime', {}))} / "
        f"{view.get('runtime', {}).get('evidence_plane', {}).get('canonical_evidence_item_count', 0)} 条 canonical evidence / "
        f"{view.get('runtime', {}).get('unique_source_count', 0)} 个去重 URL / "
        f"{view.get('runtime', {}).get('independent_publisher_count', 0)} 家独立发布方。",
        "- **边界**：报告可以给出条件性优先级与研究建议，但不自动产生订单、仓位、"
        "目标收益、候选晋级或任何外部执行。支持度是研究控制指标，不是成功概率。",
        "- **排序语义**：核验序不是收益排序；条件性建议不构成操作建议。",
    ])
    verdict = view.get("verdict", {})
    framing = view.get("framing", {})
    lines.extend([
        f"- **证据姿态**：{_clean(verdict.get('edge_state'))} / "
        f"{_clean(verdict.get('evidence_direction'))} / {_clean(verdict.get('actionability'))}",
        f"- **立题质量**：`{_clean(framing.get('quality_status'))}`",
    ])
    for premise in framing.get("premise_audit", [])[:5]:
        lines.append(
            f"- **立题前提** `{_clean(premise.get('status'))}`："
            f"{_clean(premise.get('claim'))}（as-of={_clean(premise.get('as_of'))}）"
        )
    evidence_rows = []
    seen_evidence = set()
    for citation in evidence_items:
        if not isinstance(citation, dict):
            continue
        key = (_clean(citation.get("url")), _clean(citation.get("claim")))
        if key in seen_evidence:
            continue
        seen_evidence.add(key)
        evidence_rows.append((
            f"Evidence {_clean(citation.get('evidence_id'))}", citation
        ))
    for question in questions:
        for citation in question.get("evidence", []):
            if not isinstance(citation, dict):
                continue
            key = (_clean(citation.get("url")), _clean(citation.get("claim")))
            if key in seen_evidence:
                continue
            seen_evidence.add(key)
            evidence_rows.append((
                f"Research Agenda {question.get('question_id', '—')}", citation
            ))
    for item in candidates:
        for citation in item.get("evidence", []):
            if not isinstance(citation, dict):
                continue
            key = (_clean(citation.get("url")), _clean(citation.get("claim")))
            if key in seen_evidence:
                continue
            seen_evidence.add(key)
            evidence_rows.append((_candidate_name(item), citation))
    if evidence_rows:
        lines.extend(["", "### 证据索引", ""])
        for subject, citation in evidence_rows[:20]:
            lines.append(
                f"- **{subject}**：{_clean(citation.get('claim'))} — "
                f"[{_clean(citation.get('source'))}（{_clean(citation.get('date'))}）]"
                f"({_clean(citation.get('url'))})"
            )
    return "\n".join(lines).rstrip() + "\n"


def _render_evidence_ledger(view):
    """Render the canonical evidence plane, not the legacy audit report."""
    agenda = view.get("research_agenda", {})
    items = [
        item for item in agenda.get("evidence_items", []) if isinstance(item, dict)
    ]
    items.sort(key=lambda item: (
        _clean(item.get("date")), _clean(item.get("evidence_id"))
    ))
    counts = research_kernel.evidence_plane_counts(items)
    lines = [
        "# Evidence Ledger",
        "",
        f"> **课题**：{_clean(view.get('topic'))}  ",
        f"> **证据截止**：{_clean(view.get('as_of_date'))}  ",
        f"> **canonical evidence**：{counts['canonical_evidence_item_count']} 条；"
        f"去重 URL={counts['unique_source_url_count']}；"
        f"独立发布方={counts['independent_publisher_count']}。",
        "",
        "本文件只展示统一证据账本与宿主行情回执。legacy crux 是兼容审计副轨，"
        "不替代 Research Agenda 证据，也不阻止报告交付。",
        "",
        "## 1. Canonical evidence items",
        "",
        "| Evidence ID | 来源类型 | 绑定 | 立场 | 直接支持的事实 | 数字 | 来源与日期 |",
        "|---|---|---|---|---|---|---|",
    ]
    if not items:
        lines.append("| — | — | — | — | 当前没有 canonical evidence | — | — |")
    for item in items:
        binding = item.get("binding", {}) if isinstance(item.get("binding"), dict) else {}
        binding_text = ", ".join(filter(None, [
            "/".join(item.get("question_ids", [])),
            "/".join(item.get("direction_ids", [])),
            _clean(binding.get("candidate_identity"))
            if binding.get("candidate_identity") else "",
        ])) or "未绑定回答，仅作事实底座"
        source_label = _clean(item.get("source"))
        source_url = _clean(item.get("url"))
        source_cell = (
            f"[{source_label}]({source_url})（{_clean(item.get('date'))}）"
            if source_url != "—" else f"{source_label}（{_clean(item.get('date'))}）"
        )
        lines.append(
            f"| `{_cell(item.get('evidence_id'))}` | "
            f"`{_cell(item.get('origin') or 'MODEL_RESEARCH')}` | "
            f"{_cell(binding_text)} | `{_cell(item.get('stance'))}` | "
            f"{_cell(item.get('claim'))} | {_cell(item.get('number'))} | {source_cell} |"
        )
        supporting = [
            _clean(url) for url in item.get("supporting_urls", []) if _clean(url) != "—"
        ] if isinstance(item.get("supporting_urls"), list) else []
        if supporting:
            lines.append(
                f"|  | supporting URLs |  |  | "
                f"{'；'.join(f'[source]({url})' for url in supporting)} |  |  |"
            )

    aliases = agenda.get("evidence_aliases", {})
    lines.extend(["", "## 2. Duplicate aliases", ""])
    if aliases:
        for alias, canonical in sorted(aliases.items()):
            lines.append(f"- `{_clean(alias)}` → `{_clean(canonical)}`")
    else:
        lines.append("- 无。")

    host_snapshots = view.get("market_bridge", {}).get("host_market_snapshots", [])
    lines.extend(["", "## 3. Host market snapshot receipts", ""])
    if host_snapshots:
        lines.extend([
            "| 候选 | 市场日 | Adapter receipt | Upstream receipt | Canonical evidence | 关键指标 |",
            "|---|---|---|---|---|---|",
        ])
        for entry in host_snapshots:
            snapshot = entry.get("market_snapshot", {})
            metrics = "；".join(
                f"{key}={snapshot.get(key)}" for key in (
                    "excess_5d", "excess_20d", "excess_60d",
                    "volume_ratio_20d", "turnover_rate",
                ) if snapshot.get(key) is not None
            )
            candidate = entry.get("candidate", {})
            lines.append(
                f"| {_cell(candidate.get('name'))}（{_cell(candidate.get('ticker'))}） | "
                f"{_cell(entry.get('market_session_date'))} | "
                f"`{_cell(entry.get('receipt_id'))}` | "
                f"`{_cell(entry.get('upstream_acquisition_receipt_id'))}` | "
                f"{_cell(', '.join(entry.get('canonical_evidence_ids', [])))} | "
                f"{_cell(metrics)} |"
            )
    else:
        lines.append("- 无已接受的宿主行情快照。")
    lines.extend([
        "",
        "## 4. Boundary",
        "",
        "- 宿主行情证据只支持价格、相对强弱、估值与活动度，不支持客户、订单、收入、利润或现金。",
        "- `FACT / SINGLE_SOURCE / INFERENCE / HYPOTHESIS` 是断言边界，不是收益概率。",
        "- 完整执行回执只证明运行真实性，不证明研究结论或 Alpha。",
    ])
    return "\n".join(lines).rstrip() + "\n"


def render(state, view="research"):
    """Render the Deep Research Report by default; legacy views stay explicit."""
    model = build_report_view_model(state)
    audit = model["runtime"]["execution_integrity"]
    if view == "research":
        rendered = _render_deep_research_report(model)
    elif view == "opportunity":
        rendered = _render_opportunity_brief(model)
    elif view == "facts_box":
        rendered = render_facts_box(model)
    elif view == "brief":
        rendered = _render_decision_brief(model)
    elif view == "insights":
        rendered = _render_insight_cards(model)
    elif view == "cards":
        rendered = _render_candidate_cards(model)
    elif view == "audit":
        rendered = render_audit(state)
    elif view == "evidence":
        rendered = _render_evidence_ledger(model)
    elif view != "full":
        raise ValueError(
            "unknown report view: expected research, opportunity, facts_box, brief, insights, cards, evidence, audit, or full"
        )
    else:
        rendered = "\n\n".join([
            _render_deep_research_report(model),
            "# Audit Appendix\n"
            "<details><summary>展开完整证据、状态、来源与运行审计</summary>\n\n"
            + _render_audit(state, include_title=False)
            + "\n\n</details>",
        ])
    return _attach_execution_marker(rendered, audit)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="", help="path to a v2 state json")
    ap.add_argument(
        "--view",
        default="research",
        choices=["research", "opportunity", "facts_box", "brief", "insights", "cards", "evidence", "audit", "full"],
        help="report view to render",
    )
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        # minimal mock state to prove rendering
        st = crux_engine.new_state("绿色算力(demo)", "是否做多(3-6月)", "3-6M", [
            {"id": "C6", "label": "需求/供给过剩/绿证", "monitor_anchor": "上架率、绿证均价"},
            {"id": "C2", "label": "液冷/PFAS介质", "monitor_anchor": "冷板式市占率"}])
        st["thesis_seed"] = "绿电算力=热力学强制+能源套利，非合规成本"
        crux_engine.submit_round(st, 1, {
            "C6": {"signal": -1.0, "best_bear": "利用率30%、绿证核发76亿vs交易9.3亿", "best_bull": "头部MFU55%",
                   "citations": [{"claim": "全国GPU平均利用率", "number": "~30%", "source": "工信部", "url": "http://miit/x", "date": "2026-03"}]},
            "C2": {"signal": 1.0, "best_bull": "冷板式>90%市占，水-乙二醇免疫PFAS", "best_bear": "氟化液断供",
                   "citations": [{"claim": "巨化氟化液产能", "number": "1000吨/年", "source": "巨化股份公告", "url": "http://cninfo/y", "date": "2026-05"}]}})
        crux_engine.submit_round(st, 2, {
            "C6": {"signal": -0.5, "citations": []},
            "C2": {"signal": 0.5, "citations": []}})
        crux_engine.submit_round(st, 3, {
            "C6": {"signal": 0.0, "citations": []},
            "C2": {"signal": 0.5, "citations": []}})
        st["last_convergence"] = {"decision": "converge", "reason": "renderer selftest"}
        print(render(st, view=a.view))
    elif a.state:
        print(render(json.load(open(a.state, encoding="utf-8")), view=a.view))
