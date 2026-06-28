# -*- coding: utf-8 -*-
"""
Trade Nothing v0.10.1 — Two-Layer Report Renderer (Fixed + Dynamic)

Architecture:
  FIXED LAYER (脚本物理生成，数值勿改):
    - 结论 (decision, binding crux, probabilities)
    - A · 证明账本 (crux table with P%, status, best_bull/bear, monitor_anchor, refs)
    - 量化仪表盘 (Kelly sizing, probability trace, round count)
    - 引用列表

  DYNAMIC LAYER (从全部工作数据中挖掘，LLM 综合):
    - B · 交锋战报与产业地图 — LLM receives ALL raw material (every round's
      detective findings, inquisitor attacks, judge rationale) and synthesizes
      a high-density industry analysis, not fills a template.

Numbers come only from the engine; the LLM cannot alter them.
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crux_engine

_STATUS = {
    "RESOLVED_BULL": "🟢 已证实·偏多", "RESOLVED_BEAR": "🔴 已证实·偏空",
    "MONITORABLE": "🟡 可监控", "OPEN": "⚪ 未决", "PENDING": "⏳ 未检验",
}


def _cite_key(c):
    return c.get("url") or f"{c.get('source','?')}|{c.get('claim','')}"


def _kelly(p, b=2.0):
    """Half-Kelly with entropy discount. p=win prob, b=win/loss ratio."""
    q = 1.0 - p
    if b <= 0 or p <= 0:
        return 0.0
    k = (b * p - q) / b
    return min(0.25, max(0.0, k / 2.0))


def _citation_quality(state):
    invalid = []
    valid_count = 0
    for cid, cx in state.get("cruxes", {}).items():
        for cit in cx.get("citations", []):
            item = {**cit, "crux": cid}
            if crux_engine.valid_citation(cit):
                valid_count += 1
            else:
                invalid.append(item)
    return {"valid_count": valid_count, "invalid": invalid}


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
    rd = crux_engine.report_data(state)
    topic = state.get("topic", "")

    # ═══ Build citation registry (deduped, numbered) ═══
    refs, ref_no = [], {}
    crux_refs = {}
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

    # ═══ Probability trace ═══
    n_rounds = len(state.get("rounds", []))
    dt = state.get("decision_trace", [])
    trace_str = " → ".join(
        f"R{d['round']}: {d['decision']}({int(d['p_weakest']*100)}%)"
        for d in dt
    ) if dt else "—"

    # ═══ Kelly sizing ═══
    p_w = (rd.get("p_weakest") or 0.5)
    p_m = (rd.get("p_mean") or 0.5)
    kelly_pct = _kelly(p_w) * 100

    L = []

    # ─────────── FIXED LAYER ───────────
    L.append(f"# Trade Nothing v0.10 深度研究报告 — {topic}")
    L.append(f"> 决策问题: {state.get('decision_question','')} ｜ 视野: {state.get('horizon','')}")
    L.append(f"> 假设种子: {state.get('thesis_seed','')}")
    L.append("")

    # 结论
    L.append("## 🧭 结论")
    L.append(f"- **决策: {rd['decision']}**")
    L.append(f"- 约束性 crux (binding): **{rd['binding_crux']}** ｜ "
             f"最弱承重概率 {int(p_w*100)}% ｜ 命题均值 {int(p_m*100)}%")
    L.append(f"- 博弈深度: {n_rounds} 轮 ｜ 结构化引用: {rd['n_citations']} 条")
    L.append("")

    # Evidence quality gate
    invalid = quality["invalid"]
    gate_status = "PASS" if not invalid and refs else "FAIL"
    L.append("## 0 · 证据质量闸")
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
    L.append("| crux | P | 状态 | 多头最强 | 空头最强 | 监控锚点（翻案触发） | 引用 |")
    L.append("|:---|:---:|:---|:---|:---|:---|:---|")
    for c in rd["cruxes"]:
        rno = " ".join(f"[{n}]" for n in crux_refs[c["id"]]) or "—"
        L.append(f"| **{c['id']} {c['label']}** | {int(c['p']*100)}% | "
                 f"{_STATUS.get(c['status'], c['status'])} "
                 f"| {c.get('best_bull') or '—'} | {c.get('best_bear') or '—'} "
                 f"| {c.get('monitor_anchor','')} | {rno} |")
    L.append("")

    # 每条 crux 概率轨迹
    L.append("### A.1 · 概率演化轨迹")
    for cid, cx in state["cruxes"].items():
        ph = cx["p_history"]
        pts = " → ".join(f"{int(p*100)}%" for p in ph)
        status_icon = _STATUS.get(cx["status"], cx["status"])
        L.append(f"- **{cid} {cx['label']}**: {pts} → {status_icon}")
    L.append("")

    # 量化仪表盘
    L.append("### A.2 · 量化仪表盘")
    L.append("```text")
    L.append("═══════════════════════════════════════════")
    L.append("  TRADE NOTHING v0.10 ADVERSARIAL DASHBOARD")
    L.append("═══════════════════════════════════════════")
    L.append(f"  标的: {topic}")
    L.append(f"  博弈深度: {n_rounds} 轮 ｜ 引用: {rd['n_citations']} 条")
    L.append(f"  最弱 crux: {rd['binding_crux']} ({int(p_w*100)}%)")
    L.append(f"  命题均值: {int(p_m*100)}%")
    L.append(f"  决策演化: {trace_str}")
    L.append(f"  Half-Kelly 建议仓位: {kelly_pct:.1f}%")
    L.append("═══════════════════════════════════════════")
    L.append("```")
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
    L.append("### 可用于 B 层的引用白名单")
    if refs:
        L.append("```json")
        L.append(json.dumps({
            str(i): {
                "claim": c.get("claim", ""),
                "number": c.get("number", ""),
                "source": c.get("source", ""),
                "date": c.get("date", ""),
                "url": c.get("url", ""),
            }
            for i, c in enumerate(refs, 1)
        }, ensure_ascii=False, indent=2))
        L.append("```")
    else:
        L.append("```json\n{}\n```")
    L.append("")

    # ─────────── DYNAMIC LAYER ───────────
    L.append("---")
    L.append("")
    L.append("## B · 交锋战报与产业地图（由 deep 模型从全量工作数据综合，禁止填空式套模板）")
    L.append("")

    # Dump raw material
    raw_material = _extract_raw_material(state)
    L.append("### 📦 全量工作数据（以下为全部轮次的 agent 原始产出，供综合时引用挖掘）")
    L.append("")
    L.append("<details><summary>点击展开全部原始数据</summary>")
    L.append("")
    for entry in raw_material:
        r = entry["round"]
        L.append(f"#### Round {r}")
        if entry["detective"]:
            det = entry["detective"]
            if det.get("variant_perception"):
                L.append(f"- **🔍 Variant Perception**: {det['variant_perception']}")
            if det.get("bull_thesis"):
                L.append(f"- **🐂 Bull Thesis**: {det['bull_thesis']}")
            if det.get("supply_chain_map"):
                L.append(f"- **🔗 Supply Chain Map**: {det['supply_chain_map']}")
            for ev in det.get("evidence_chain", []):
                node = ev.get("claim_node", "")
                src = ev.get("source", "")
                if node:
                    L.append(f"  - `{node}` | src: {src}")
            if det.get("new_dimension"):
                L.append(f"- **🆕 New Dimension**: {det['new_dimension']}")
        if entry["inquisitor"]:
            inq = entry["inquisitor"]
            dp = inq.get("death_path", {})
            if dp and dp.get("summary"):
                L.append(f"- **💀 Death Path**: {dp['summary']}")
                if dp.get("transmission_chain"):
                    L.append(f"  - Chain: {dp['transmission_chain']}")
            for atk in inq.get("lethal_attacks", []):
                a = atk.get("attack", "")
                t = atk.get("target_claim_node", "")
                if a:
                    L.append(f"  - ⚔️ `{a}` → target: {t}")
            ks = inq.get("kill_switch", {})
            if ks and ks.get("condition"):
                L.append(f"- **🚨 Kill Switch**: {ks['condition']} "
                         f"(threshold: {ks.get('threshold','?')})")
            if inq.get("new_attack_dimension"):
                L.append(f"- **🆕 New Attack**: {inq['new_attack_dimension']}")
        if entry["judge_rationale"]:
            for cid, jr in entry["judge_rationale"].items():
                sig = jr.get("signal", 0)
                direction = "🐂" if sig > 0 else ("🐻" if sig < 0 else "⚖️")
                L.append(f"  - Judge {cid}: {direction} {sig:+.1f} — {jr.get('rationale','')}")
        L.append("")
    L.append("</details>")
    L.append("")

    # Synthesis instruction
    binding = rd['binding_crux']
    open_cruxes = [c for c in rd["cruxes"] if c["status"] in ("OPEN", "MONITORABLE")]
    open_labels = ", ".join(f"{c['id']}({c['label']})" for c in open_cruxes) or "无"

    L.append("### 📝 综合指令（deep 模型必须完成以下全部内容，替换本段及下方占位）")
    L.append("")
    L.append("> 从上方 📦 全量工作数据 中**挖料综合**，必须覆盖以下模块：")
    L.append("> **硬闸：所有数字、日期、价格、比例、产能、订单量、阈值、目标价都必须复用上方引用白名单中的 [n]。**")
    L.append("> 不在白名单中的数字不得写入 B 层；不得新增引用编号；不得使用主页级 URL；无法引用的内容只能写成定性描述。")
    L.append(">")
    L.append("> **模块 1 · 非共识命题与一句话判决**（≤100字）")
    L.append(">   - 市场一致预期 vs 本研究发现的 variant perception")
    L.append(">")
    L.append(f"> **模块 2 · 约束性 crux 深度剖析**（binding: {binding}）")
    L.append(">   - 为什么这条 crux 是胜负手？它的证伪/翻案条件是什么？")
    L.append(">   - 多头和空头各自最强论点的证据质量对比")
    L.append(">")
    L.append("> **模块 3 · 产业链价值地图**（≥500字，核心产出）")
    L.append(">   - 上游原材料 → 中游制造/集成 → 下游需求/应用的完整链条")
    L.append(">   - 关键公司/项目/产能/良率/交期的具体数据锚点")
    L.append(">   - BOM 拆解中的 chokepoint（不可替代环节）")
    L.append(">   - crux 之间的因果耦合关系")
    L.append(">")
    L.append(f"> **模块 4 · 风险监控矩阵**（OPEN/MONITORABLE crux: {open_labels}）")
    L.append(">   - 每条未完全收敛的 crux：盯什么指标、什么数值意味着翻案")
    L.append(">   - 最危险的死亡路径（从 Inquisitor 的 premortem 中提炼）")
    L.append(">")
    L.append("> **模块 5 · 四情景 R/R 矩阵**")
    L.append(">   | 场景 | 概率 | 触发事件 | 回报预期 |")
    L.append(">   |:---|:---:|:---|:---:|")
    L.append(">   | 🐂 Bull | ?% | ? | +?% |")
    L.append(">   | 🦊 Base | ?% | ? | +?% |")
    L.append(">   | 🐻 Bear | ?% | ? | -?% |")
    L.append(">   | 🦢 Black Swan | ?% | ? | -?% |")
    L.append(">   概率须与 A 层的 crux 概率逻辑自洽。")
    L.append(">")
    L.append("> **模块 6 · 实战监控路线图**")
    L.append(">   - 周度高频追踪指标（海关/招标/价格/库存）")
    L.append(">   - 触发事件日历（财报/政策/产能投产节点）")
    L.append(">")
    L.append("> ⚠️ 每个数字必须挂 [n] 引用。禁止发明无数据锚点的观点。写完后必须运行 `scripts/validate_report_v2.py --report <报告路径> --state <state.json>`。")
    L.append("")
    L.append("<!-- BATTLE_LOG_START -->")
    L.append("（待 deep 模型写入：从全量工作数据综合的交锋战报 + 产业地图 + 风险矩阵）")
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
        print(render(st))
    elif a.state:
        print(render(json.load(open(a.state, encoding="utf-8"))))
