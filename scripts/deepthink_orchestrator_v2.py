#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trade Nothing v0.10 — Crux Orchestrator  (-deepthink2; parallel to deepthink_orchestrator.py)

Deterministic state machine. Control flow lives in code; the LLM only produces content.

Flow:
  --frame  TOPIC                       -> emit Framer prompt (DEEP). Host runs framer.md.
  --init   TOPIC --frame-json J        -> ingest frame; No-Edge early-exit OR create crux state
                                          + emit Round-1 dispatch (Detective+Inquisitor on all cruxes).
  --submit TOPIC --det J --inq J --judge J
                                       -> add any new cruxes; engine.submit_round(judge signals);
                                          decide: dispatch ONLY open cruxes, or ready_for_report.
  --report TOPIC                       -> emit crux ledger + battle-log synthesis instruction (DEEP).

Model tiering (see model_tiers.py): Detective/Inquisitor/Framer/synthesis = DEEP;
Judge scoring = FAST. Detective & Inquisitor each round are scoped to OPEN cruxes only
(crux-scoping) -> fewer searches, faster convergence.
"""
import os, sys, re, json, argparse
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import crux_engine
try:
    from model_tiers import model_for
except Exception:
    def model_for(t): return "deep"

STATE_DIR = os.path.join(SCRIPT_DIR, ".state")


def _slug(topic):
    codes = re.findall(r"\d{6}", topic or "")
    pre = f"{codes[0]}_" if codes else ""
    words = re.findall(r"[一-龥\w]+", (topic or "").lower())
    cleaned = [w for w in words if w not in {"研究","分析","关于","价格","走势","标的"}] or ["general"]
    return (pre + "_".join(cleaned))[:40].rstrip("_")

def _path(topic):
    return os.path.join(STATE_DIR, f"{_slug(topic)}_v2_state.json")

def _load(topic):
    p = _path(topic)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None

def _save(topic, state):
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump(state, open(_path(topic), "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def _agent_has_evidence(detective, inquisitor):
    """Judge may only score evidence that exists in the isolated agent outputs."""
    det = detective if isinstance(detective, dict) else {}
    inq = inquisitor if isinstance(inquisitor, dict) else {}
    return any([
        bool(det.get("evidence_chain")),
        bool(det.get("rebuttals")),
        bool(det.get("supply_chain_map")),
        bool(inq.get("lethal_attack_vectors")),
        bool(inq.get("recommended_kill_switch")),
    ])


def _sanitize_judge_for_agent_support(judge, detective, inquisitor):
    """Prevent a Judge from inventing citations after thin/empty agent rounds."""
    if not isinstance(judge, dict):
        return {}
    out = json.loads(json.dumps(judge, ensure_ascii=False))
    if _agent_has_evidence(detective, inquisitor):
        return out
    for sig in out.get("crux_signals", {}).values():
        if not isinstance(sig, dict):
            continue
        try:
            nonzero = float(sig.get("signal", 0.0)) != 0.0
        except Exception:
            nonzero = False
        if nonzero:
            sig["signal"] = 0.0
            flags = sig.get("quality_flags", [])
            if not isinstance(flags, list):
                flags = []
            flags.append("signal_zeroed_empty_agent_evidence")
            sig["quality_flags"] = sorted(set(flags))
    return out


# ── prompt assembly ──────────────────────────────────────────────────────────
def _open_cruxes(state):
    return [cid for cid, cx in state["cruxes"].items() if not cx["retired"]]

def frame_prompt(topic):
    return (f"[Framer · framer.md] Topic: {topic}\n"
            "立题：输出 decision_question / thesis_seed / 2–5 candidate_cruxes(每条带 monitor_anchor) / "
            "forbidden_consensus / no_edge_precheck / suggested_max_rounds。严格按 framer.md 的 JSON 输出。")

def dispatch_prompts(state, round_num):
    open_ids = _open_cruxes(state)
    fc = state.get("forbidden_consensus", [])
    lines = []
    for cid in open_ids:
        cx = state["cruxes"][cid]
        lines.append(f"- [{cid}] {cx['label']}: {cx.get('definition','')}\n"
                     f"    对方当前最强点(bear): {cx.get('best_bear') or '（暂无）'}\n"
                     f"    我方当前最强点(bull): {cx.get('best_bull') or '（暂无）'}\n"
                     f"    监控锚点: {cx.get('monitor_anchor','')}")
    scope = "\n".join(lines)
    resolved = [f"{cid}({state['cruxes'][cid]['label']})" for cid, cx in state["cruxes"].items()
                if cx["retired"] and cx["status"].startswith("RESOLVED")]
    # ── 退休 crux 上下文（不需重辩，但供产业链交叉引用）──
    retired_ctx = ""
    retired_cruxes = [(cid, cx) for cid, cx in state["cruxes"].items() if cx["retired"]]
    if retired_cruxes:
        rc_lines = [f"  - {cid}({cx['label']}): {cx['status']}, P={int(cx['p_history'][-1]*100)}%, "
                    f"bull={cx.get('best_bull') or '?'}, bear={cx.get('best_bear') or '?'}"
                    for cid, cx in retired_cruxes]
        retired_ctx = ("\n📋 已收敛 crux 上下文（不需重辩，但供产业链交叉引用）:\n"
                       + "\n".join(rc_lines))
    # ── 产业链深挖指令 ──
    chain_directive = (
        "\n🔗 产业链深挖（每轮必做）:\n"
        "  1. 对每个 OPEN crux，追溯上游原材料→中游制造→下游终端的完整价值链节点\n"
        "  2. 识别 crux 之间的因果耦合（如 C1 的成本结构如何约束 C3 的技术路线选型）\n"
        "  3. 至少引用一个具体公司/项目/产能/招标/海关数据点（带具体页面/公告/API URL，禁止主页）\n"
        "  4. 挖掘供应链隐性瓶颈（良率、交期、原材料集中度、产能利用率、库存周期）\n"
        "  5. 如发现 crux 之间存在跨环节传导链条，在 JSON 的 new_dimension_this_round 中明确标注"
    )
    common = (f"决策问题: {state['decision_question']} | 视野: {state['horizon']}\n"
              f"本轮重点质证以下 OPEN crux:\n{scope}\n"
              f"{retired_ctx}\n"
              f"平庸共识禁区(禁用): {fc}\n"
              f"{chain_directive}\n"
              "硬约束: 每个数据点必须带 来源+具体URL+日期；禁止主页级URL；禁止模糊措辞；每轮至少一个新维度。")
    det = (f"[Detective · detective.md · model={model_for('detective')}] Round {round_num}\n{common}\n"
           "任务: 对每个 OPEN crux 用**带URL的硬数据**加固多头/反驳空头。\n"
           "额外要求: 输出中必须包含 supply_chain_map 字段描述本轮新发现的产业链节点。\n"
           "输出 detective.md 的 JSON。")
    inq = (f"[Inquisitor · inquisitor.md · model={model_for('inquisitor')}] Round {round_num}\n{common}\n"
           "任务: 对每个 OPEN crux 发起带数据的致命攻击；若发现新攻击面，明确提出(交由法官登记为 new crux)。\n"
           f"⭐ FREE-ROAM(每轮1个名额): 可对以下任一**已收敛** crux 用**新硬数据**发起攻击试图重开，"
           f"或提出全新攻击面 —— 防止对'已结论'的晚期黑天鹅漏检: {resolved or '（暂无已收敛 crux）'}\n"
           "输出 inquisitor.md 的 JSON。")
    judge = (f"[Judge · judge.md · model={model_for('judge_scoring')}] Round {round_num}\n"
             f"读 Detective/Inquisitor 两份 JSON，对 OPEN crux {open_ids} 各打一个 signal∈[-1,1]+引用，"
             "并把任何新攻击面填进 new_cruxes。严格按 judge.md 的 JSON 输出。")
    return {"open_cruxes": open_ids, "detective_prompt": det, "inquisitor_prompt": inq, "judge_prompt": judge}


# ── commands ─────────────────────────────────────────────────────────────────
def cmd_frame(topic):
    return {"status": "need_framing", "topic": topic, "model": model_for("crux_extraction"),
            "framer_prompt": frame_prompt(topic),
            "instruction": "运行 framer，然后调用 --init --frame-json '<framer输出>'。"}

def cmd_init(topic, frame):
    pre = frame.get("no_edge_precheck", {})
    if pre and pre.get("is_researchable") is False:
        return {"status": "no_edge", "topic": topic, "reason": pre.get("reason", ""),
                "instruction": "立题门判定无非对称角度。输出 No-Edge 声明，不派任何子智能体。"}
    cruxes = frame.get("candidate_cruxes", [])
    if not cruxes:
        return {"status": "error", "reason": "framer 未给出 candidate_cruxes。"}
    state = crux_engine.new_state(topic, frame.get("decision_question", topic),
                                  frame.get("horizon", "3-6M"), cruxes)
    state["forbidden_consensus"] = frame.get("forbidden_consensus", [])
    state["thesis_seed"] = frame.get("thesis_seed", "")
    state["suggested_max_rounds"] = frame.get("suggested_max_rounds", 6)
    _save(topic, state)
    out = {"status": "dispatch_subagents", "topic": topic, "round": 1, "thesis_seed": state["thesis_seed"]}
    out.update(dispatch_prompts(state, 1))
    return out

def cmd_submit(topic, detective, inquisitor, judge):
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在，请先 --init。"}
    round_num = len(state["rounds"]) + 1
    judge = _sanitize_judge_for_agent_support(judge, detective, inquisitor)
    for nc in judge.get("new_cruxes", []):
        crux_engine.add_crux(state, nc, round_num)
    signals = judge.get("crux_signals", {})
    conv = crux_engine.submit_round(state, round_num, signals)
    state["last_convergence"] = conv
    # ── 保存 agent 原始输出到 state，供报告层消费 ──
    state["rounds"][-1]["detective_raw"] = detective
    state["rounds"][-1]["inquisitor_raw"] = inquisitor
    state["rounds"][-1]["judge_raw"] = judge
    _save(topic, state)
    dt = state["decision_trace"][-1]
    base = {"topic": topic, "round_completed": round_num,
            "decision": dt["decision"], "binding_crux": dt["weakest"],
            "p_weakest": dt["p_weakest"], "p_mean": dt["p_mean"], "convergence": conv}
    if conv["decision"] == "converge":
        base["status"] = "ready_for_report"
        base["instruction"] = f"引擎判定 {conv['decision']}。调用 --report --topic \"{topic}\"。"
    elif conv["decision"] == "fuse_break":
        base["status"] = "blocked_max_rounds"
        base["open_cruxes"] = [cid for cid, cx in state["cruxes"].items()
                               if cx["status"] in ("PENDING", "OPEN")]
        base["instruction"] = ("达到最大轮次但仍未收敛。禁止生成正式报告；"
                               "请补充硬证据或扩展轮次后继续质证。")
    else:
        base["status"] = "dispatch_subagents"
        base.update(dispatch_prompts(state, round_num + 1))
        base["instruction"] = (f"继续 (Round {round_num+1})，仅对 OPEN crux 派 Detective+Inquisitor，"
                               "再用 Judge 评分后调用 --submit。")
    return base

def cmd_report(topic):
    state = _load(topic)
    if not state:
        return {"status": "error", "reason": "状态不存在。"}
    conv = state.get("last_convergence", {})
    if conv.get("decision") != "converge":
        unresolved = [cid for cid, cx in state.get("cruxes", {}).items()
                      if cx.get("status") in ("PENDING", "OPEN")]
        return {"status": "blocked_unconverged", "topic": topic,
                "convergence": conv, "unresolved_cruxes": unresolved,
                "instruction": "禁止生成正式报告：engine 尚未收敛。继续质证或补充硬证据。"}
    import report_v2
    rd = crux_engine.report_data(state)
    return {"status": "report_data_ready", "topic": topic,
            "decision": rd["decision"], "binding_crux": rd["binding_crux"],
            "p_weakest": rd["p_weakest"], "p_mean": rd["p_mean"], "n_citations": rd["n_citations"],
            "model": model_for("battle_log_synthesis"),
            "report_markdown": report_v2.render(state),
            "instruction": ("报告已由脚本生成两层结构：\n"
                            "【固定层 A】证明账本 + 概率轨迹 + 量化仪表盘 + 引用 —— 数值勿改。\n"
                            "【动态层 B】全量工作数据已展开在 📦 区块中。请用 DEEP 模型完成：\n"
                            "  1. 非共识命题与一句话判决\n"
                            "  2. 约束性 crux 深度剖析\n"
                            "  3. 产业链价值地图（≥500字，含 BOM 拆解、chokepoint、crux 因果耦合）\n"
                            "  4. 风险监控矩阵（每条 OPEN/MONITORABLE crux 的翻案指标）\n"
                            "  5. 四情景 R/R 矩阵（Bull/Base/Bear/Black Swan）\n"
                            "  6. 实战监控路线图（周度高频 + 触发事件日历）\n"
                            "将内容写入 <!-- BATTLE_LOG_START/END --> 之间，每个数字挂 [n] 引用。\n"
                            "只能使用 A 层 References 中已有的 [n]，不得新增未登记引用或主页级 URL。\n"
                            "禁止填空式套模板——从原始数据中挖掘，写出有信息增量的分析。")}


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
    g.add_argument("--selftest", action="store_true")
    ap.add_argument("--topic", default="")
    ap.add_argument("--frame-json", default="")
    ap.add_argument("--det", default=""); ap.add_argument("--inq", default=""); ap.add_argument("--judge", default="")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.frame:  out = cmd_frame(a.topic)
    elif a.init: out = cmd_init(a.topic, _jload(a.frame_json))
    elif a.submit: out = cmd_submit(a.topic, _jload(a.det), _jload(a.inq), _jload(a.judge))
    elif a.report: out = cmd_report(a.topic)
    print(json.dumps(out, ensure_ascii=False, indent=2))


# ── end-to-end wiring self-test: drive the full loop on real 绿色算力 signals ──
def selftest():
    topic = "绿色算力景气度与产业链_v2selftest"
    if os.path.exists(_path(topic)): os.remove(_path(topic))
    frame = {
        "decision_question": "绿色算力产业链是否值得做多(3-6月)", "horizon": "3-6M",
        "thesis_seed": "市场把绿色算力定价为ESG合规成本，实为热力学强制+能源套利底座",
        "candidate_cruxes": [
            {"id":"C1","label":"时空错配/储能成本","monitor_anchor":"西部到户综合电价(含储能)、储能EPC元/Wh"},
            {"id":"C2","label":"液冷/PFAS介质","monitor_anchor":"冷板式市占率、巨化/新宙邦氟化液产能"},
            {"id":"C3","label":"WUE水资源红线","monitor_anchor":"西部干冷器节点实测WUE、水预算配额"}],
        "forbidden_consensus": ["产能过剩内卷","ESG合规成本"], "no_edge_precheck": {"is_researchable": True},
        "suggested_max_rounds": 8}
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
        score_ids = set(_open_cruxes(st) + [c["id"] for c in new])
        if r in FREEROAM:                       # free-roam may score a retired crux -> re-open
            score_ids.add(FREEROAM[r][0])
        cs = {}
        for cid in score_ids:
            s = FREEROAM[r][1] if (r in FREEROAM and cid == FREEROAM[r][0]) else SIG.get(cid,{}).get(r,0.0)
            cs[cid] = {"signal": s, "rationale":"(selftest)","best_bull":"(略)","best_bear":"(略)",
                       "citations":([{"claim":"x","number":"1","source":"demo","url":"https://example.com/source","date":"2026-06"}]
                                    if s != 0 else [])}
        judge = {"round": r, "crux_signals": cs, "new_cruxes": new}
        det = {"evidence_chain": [{"claim_node": "[Vision Node: selftest | Constraint: x]",
                                   "source": "demo, https://example.com/source, 2026"}]}
        inq = {"lethal_attack_vectors": [{"attack": "[Audit Attack | Target: selftest]",
                                           "evidence_audit": "demo"}]}
        res = cmd_submit(topic, det, inq, judge)
        print(f"R{r:<2} open→{res.get('open_cruxes','-')} | 决策={res['decision']:<22} "
              f"弱={res['binding_crux']}({int(res['p_weakest']*100)}%) | {res['convergence']['decision']}")
        if res["status"] == "ready_for_report":
            break
        if res["status"] == "blocked_max_rounds":
            break
    rep = cmd_report(topic)
    print(f"\nREPORT status={rep['status']}")
    if rep["status"] == "report_data_ready":
        print(f"决策={rep['decision']} | binding={rep['binding_crux']} "
              f"({int(rep['p_weakest']*100)}%) | 命题均值={int(rep['p_mean']*100)}% | 引用合计={rep['n_citations']}")
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
