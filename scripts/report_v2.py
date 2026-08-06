# -*- coding: utf-8 -*-
"""
Trade Nothing v0.14.0 — Compact Formal Report Renderer

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
import hypothesis_engine
import tracking_engine
import landscape_engine
import opportunity_engine
import candidate_gap_engine
import candidate_screen_engine
import claim_verification_engine
import temporal_contract
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
    candidate maturity, and the next legal action separate so renderers cannot
    turn a valid report into an investment recommendation.

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
            "unique_source_count": rd.get("n_unique_sources", 0),
            "primary_source_count": rd.get("n_primary_sources", 0),
        },
        "research_grade": crux_engine.research_grade(state),
    }


def _render_audit(state, include_title=True):
    opportunity_engine.refresh_candidate_states(state)
    rd = crux_engine.report_data(state)
    landscape = landscape_engine.summary(state)
    topic = state.get("topic", "")

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
    L.append(f"- 博弈深度: {n_rounds} 轮 ｜ 唯一可复核来源: {rd['n_unique_sources']} 个"
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
    L.append(f"  博弈深度: {n_rounds} 轮 ｜ 唯一来源: {rd['n_unique_sources']} 个")
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
        f"- 隔离 `{view['runtime']['isolation_status']}`；轮次 {view['runtime']['round_count']}；"
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
        f"**运行证据覆盖**: {runtime['round_count']} 轮辩论 | "
        f"{ev.get('valid_citations', 0)} 条有效引用 | "
        f"{runtime['unique_source_count']} 去重来源 URL | "
        f"{ev.get('unique_publishers', 0)} 家独立出版方 | "
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


def render(state, view="full"):
    """Render a facts box, legacy brief, candidate cards, audit, or full report."""
    model = build_report_view_model(state)
    if view == "facts_box":
        return render_facts_box(model)
    if view == "brief":
        return _render_decision_brief(model)
    if view == "cards":
        return _render_candidate_cards(model)
    if view == "audit":
        return render_audit(state)
    if view != "full":
        raise ValueError(
            "unknown report view: expected facts_box, brief, cards, audit, or full"
        )
    return "\n\n".join([
        _render_decision_brief(model),
        _render_insight_cards(model),
        _render_candidate_cards(model),
        "# Audit Appendix\n"
        "<details><summary>展开完整证据、状态、来源与运行审计</summary>\n\n"
        + _render_audit(state, include_title=False)
        + "\n\n</details>",
    ])


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="", help="path to a v2 state json")
    ap.add_argument(
        "--view",
        default="full",
        choices=["facts_box", "brief", "cards", "audit", "full"],
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
