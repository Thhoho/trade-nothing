# -*- coding: utf-8 -*-
"""
Trade Nothing v0.10.1 — Compact Formal Report Renderer

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
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crux_engine
import opportunity_engine
import candidate_screen_engine
import claim_verification_engine

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


def render(state):
    if state.get("last_convergence", {}).get("decision") != "converge":
        raise ValueError("formal report blocked: engine state is not converged")
    opportunity_engine.refresh_candidate_states(state)
    rd = crux_engine.report_data(state)
    topic = state.get("topic", "")

    # ═══ Build citation registry (deduped, numbered) ═══
    refs, ref_no = [], {}
    crux_refs = {}
    opportunity_refs = {}
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
        valid = [c for c in seed.get("evidence", []) if crux_engine.valid_citation(c)]
        if not valid:
            continue
        item = dict(seed)
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
    trace_str = " → ".join(
        f"R{d['round']}: {crux_engine.safe_decision_label(d.get('decision'))}"
        f"({int(d.get('support_weakest', d['p_weakest'])*100)}/100)"
        for d in dt
    ) if dt else "—"

    support_w = (rd.get("support_weakest") or 0.5)
    support_m = (rd.get("support_mean") or 0.5)
    verdict = rd.get("research_verdict", {})

    L = []

    # ─────────── FIXED LAYER ───────────
    L.append(f"# Trade Nothing v0.10 深度研究报告 — {topic}")
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
    if rd.get("binding_crux"):
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

    # Evidence quality gate
    invalid = quality["invalid"]
    gate_status = "PASS" if not invalid and refs else "FAIL"
    L.append("## 0.2 · 证据质量闸")
    L.append(f"- 状态: **{gate_status}** ｜ 可复核引用: {len(refs)} 条 ｜ 被剔除引用: {len(invalid)} 条")
    L.append("- 规则: 引用必须含 claim/source/date，且 URL 不能只是主页或裸域名。")
    if invalid:
        for bad in invalid[:10]:
            L.append(f"  - 剔除: {bad.get('crux','?')} | {bad.get('source','?')} | {bad.get('url','')}")
        if len(invalid) > 10:
            L.append(f"  - 另有 {len(invalid) - 10} 条被剔除。")
    L.append("")

    # A · 证明账本
    L.append("## A · 证明账本（脚本物理生成，数值勿改）")
    L.append("| crux | 辩论支持度 | 状态 | 多头最强 | 空头最强 | 监控锚点 | 反证 / 催化窗口 | 引用 |")
    L.append("|:---|:---:|:---|:---|:---|:---|:---|:---|")
    for c in rd["cruxes"]:
        rno = " ".join(f"[{n}]" for n in crux_refs[c["id"]]) or "—"
        catalyst = c.get("catalyst_window", {})
        catalyst_text = (f"{catalyst.get('event', '—')} @ {catalyst.get('expected_by', '—')} "
                         f"[{catalyst.get('date_status', 'UNVERIFIED')}; "
                         f"basis={catalyst.get('basis_claim_id', '—')}]"
                         if isinstance(catalyst, dict) else _clean(catalyst))
        L.append(f"| **{c['id']} {c['label']}** | {int(c['support_score']*100)}/100 | "
                 f"{_STATUS.get(c['status'], c['status'])} "
                 f"| {c.get('best_bull') or '—'} | {c.get('best_bear') or '—'} "
                 f"| {c.get('monitor_anchor','')} | {_cell(c.get('falsifier'))} / {_cell(catalyst_text)} | {rno} |")
    L.append("")

    # 每条 crux 支持度轨迹
    L.append("### A.1 · 辩论支持度演化（非统计概率）")
    for cid, cx in state["cruxes"].items():
        ph = cx["p_history"]
        pts = " → ".join(f"{int(p*100)}" for p in ph)
        status_icon = _STATUS.get(cx["status"], cx["status"])
        L.append(f"- **{cid} {cx['label']}**: {pts} → {status_icon}")
    L.append("")

    # 证据仪表盘
    L.append("### A.2 · 证据与流程仪表盘")
    L.append("```text")
    L.append("═══════════════════════════════════════════")
    L.append("  TRADE NOTHING v0.10 ADVERSARIAL DASHBOARD")
    L.append("═══════════════════════════════════════════")
    L.append(f"  标的: {topic}")
    L.append(f"  博弈深度: {n_rounds} 轮 ｜ 唯一来源: {rd['n_unique_sources']} 个")
    L.append(f"  当前焦点 / 最低支持度: {rd.get('focus_crux') or rd.get('binding_crux')} "
             f"({int(support_w*100)}/100)")
    L.append(f"  命题均值支持度: {int(support_m*100)}/100")
    L.append(f"  决策演化: {trace_str}")
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
    relation_labels = {
        "DIRECT_WINNER": "直接受益",
        "SUBSTITUTE_WINNER": "替代路径",
        "COMPETITOR_WINNER": "竞争者受益",
        "BOTTLENECK_OWNER": "瓶颈所有者",
        "INFRA_ASSET_OWNER": "基础资产所有者",
        "SECOND_ORDER": "二阶机会",
        "SHORT_CANDIDATE": "做空研究候选",
    }
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
        L.append(f"- **关系 / 来源 crux**: {relation_labels.get(seed.get('relation_type'), seed.get('relation_type', '—'))}"
                 f" / {_clean(seed.get('origin_crux'))} ｜ 首见 R{seed.get('first_seen_round', '?')} ｜ agent: {agents}")
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
                L.append(f"- **筛选缺口**: {', '.join(screen['gaps'])}")
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
        L.append(f"- **{item['id']} {item['status']}**: 监控 {trigger}；"
                 f"证伪 {item.get('falsifier') or '—'}。{ref_text}")
    L.append("")
    L.append("### 候选线索边界")
    L.append(f"- 证据路径已按唯一候选去重展示；当前只有 "
             f"{opportunity_counts['ready_for_screening_count']} 个候选具备双边筛查资格。")
    L.append("- 未完成 CandidateScreen 与页面快照对齐的候选，均不得表述为投资结论。")
    L.append("<!-- BATTLE_LOG_END -->")
    return "\n".join(L)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="", help="path to a v2 state json")
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
        print(render(st))
    elif a.state:
        print(render(json.load(open(a.state, encoding="utf-8"))))
