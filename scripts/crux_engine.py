# -*- coding: utf-8 -*-
"""
Trade Nothing v0.10 — Crux Engine  (parallel to deepthink_engine.py; -deepthink2)

Replaces the degenerate single-posterior + LFI layer with a per-CRUX ledger:

  * Each load-bearing crux carries its own bounded log-odds.
  * Per round, ONE decorrelated update per crux (judge signal), with mean-reversion
    decay and a hard clamp |L| <= ln(L_MAX_ODDS) -> a single crux can never exceed
    ~80/20 from debate alone. No 0%/100% pinning.
  * Convergence = decision-readiness: stop when every crux is RESOLVED or converted
    to a MONITORABLE watch-item AND the decision is stable. Achievable (unlike
    "no attack survives", which never converged: open_attacks went 2->30).
  * Crux-scoping: a RESOLVED crux is RETIRED -> no more sub-agents fired on it ->
    fewer searches per round + faster convergence (the cost win).
  * Citations live on the ledger per crux (verifiability).

All numbers are computed here from judge-supplied signals; the LLM never writes a
probability. Determinism of control flow is preserved; the small "judge" model only
supplies a bounded signal in [-1,1] + rationale + citations per crux per round.
"""
import math
import json
from urllib.parse import urlparse

# ── tunables (configurable; defaults from the 绿色算力 PoC) ──
K            = 0.9              # per-round gain. strong evidence (|s|=1) -> ±0.9 log-odds
DECAY        = 0.88             # mean-reversion of stale belief toward 0.5
L_MAX        = math.log(4.0)    # clamp -> single-crux prob bounded to [0.20, 0.80]
MIN_ROUNDS   = 3
MAX_ROUNDS   = 12               # hard fuse (should rarely be hit now)
EPS_STABLE   = 0.03             # |Δp| below this over a touch = "settled"
OPEN_PATIENCE = 3               # rounds a crux may stay contested before forced MONITORABLE
MIN_CONTESTED = 3               # min contested rounds before a crux is eligible for retirement
DRY_ROUNDS   = 3                # no NEW crux introduced for this many rounds = adversary went dry
MIN_VALID_CITATIONS = 2         # a crux needs real source anchors before it may retire

def _sig(x):   return 1.0 / (1.0 + math.exp(-x))
def _clamp(x, lo, hi): return max(lo, min(hi, x))


def is_concrete_url(url):
    """Reject homepage/domain-only citations; accept URLs with a real path/query."""
    if not isinstance(url, str) or not url.strip():
        return False
    try:
        p = urlparse(url.strip())
    except Exception:
        return False
    if p.scheme not in ("http", "https") or not p.netloc:
        return False
    return bool((p.path and p.path != "/") or p.query)


def valid_citation(c):
    """Minimum citable anchor for engine scoring and report references."""
    if not isinstance(c, dict):
        return False
    return bool(c.get("claim") and c.get("source") and c.get("date") and is_concrete_url(c.get("url", "")))


def _numbered_citation(c):
    return valid_citation(c) and bool(str(c.get("number", "")).strip())


def _valid_citation_count(cx):
    return sum(1 for c in cx.get("citations", []) if valid_citation(c))


def _normalize_signal(js):
    """Make the evidence gate physical: unsupported signals cannot move probabilities."""
    if not isinstance(js, dict):
        js = {}
    out = dict(js)
    try:
        s = float(out.get("signal", 0.0))
    except Exception:
        s = 0.0
    s = _clamp(s, -1.0, 1.0)
    citations = out.get("citations", []) if isinstance(out.get("citations", []), list) else []
    valid = [c for c in citations if valid_citation(c)]
    flags = list(out.get("quality_flags", [])) if isinstance(out.get("quality_flags", []), list) else []
    if citations and len(valid) < len(citations):
        flags.append(f"dropped_invalid_citations:{len(citations) - len(valid)}")
    if s != 0.0 and not valid:
        s = 0.0
        flags.append("signal_zeroed_no_valid_citation")
    elif abs(s) > 0.5 and not any(_numbered_citation(c) for c in valid):
        s = 0.5 if s > 0 else -0.5
        flags.append("signal_capped_no_numbered_citation")
    out["signal"] = s
    out["citations"] = valid
    if flags:
        out["quality_flags"] = sorted(set(flags))
    return out


def new_state(topic, decision_question, horizon, cruxes):
    """cruxes: list of {id, label, definition, monitor_anchor}"""
    return {
        "topic": topic,
        "decision_question": decision_question,
        "horizon": horizon,
        "config": {"K": K, "DECAY": DECAY, "L_MAX_ODDS": 4.0},
        "cruxes": {c["id"]: {
            "label": c["label"],
            "definition": c.get("definition", ""),
            "monitor_anchor": c.get("monitor_anchor", ""),
            "L": 0.0, "p_history": [0.5], "contested_history": [], "status": "PENDING",
            "retired": False, "first_contested": None, "last_signal": 0.0,
            "introduced": 0,
            "best_bull": None, "best_bear": None, "citations": [],
        } for c in cruxes},
        "max_introduced_round": 0,
        "rounds": [],
        "decision_trace": [],
    }


def add_crux(state, crux, round_num):
    """Adversary discovered a new attack surface mid-debate. Resets the dry-round clock."""
    if crux["id"] in state["cruxes"]:
        return
    state["cruxes"][crux["id"]] = {
        "label": crux["label"], "definition": crux.get("definition", ""),
        "monitor_anchor": crux.get("monitor_anchor", ""),
        "L": 0.0, "p_history": [0.5], "contested_history": [], "status": "PENDING",
        "retired": False, "first_contested": None, "last_signal": 0.0,
        "introduced": round_num,
        "best_bull": None, "best_bear": None, "citations": [],
    }
    state["max_introduced_round"] = max(state["max_introduced_round"], round_num)


def _update_status(cx, r):
    """Classify a crux. Only evaluated on rounds where the crux was contested."""
    if cx["first_contested"] is None:
        return "PENDING"                           # never examined -> blocks convergence
    ch = cx["contested_history"]
    if len(ch) < MIN_CONTESTED:
        return "OPEN"                              # insufficient contested rounds for resolution
    if _valid_citation_count(cx) < MIN_VALID_CITATIONS:
        return "OPEN"                              # stable rhetoric is not evidentiary convergence
    p = ch[-1]
    settled = abs(ch[-1] - ch[-2]) < EPS_STABLE    # stable across last 2 *contested* rounds
    contested_for = r - cx["first_contested"]
    if settled:
        if p >= 0.55:  return "RESOLVED_BULL"
        if p <= 0.45:  return "RESOLVED_BEAR"
        return "MONITORABLE"                       # stuck near coin-flip after real evidence
    if contested_for >= OPEN_PATIENCE and cx["last_signal"] < 0:
        return "MONITORABLE"                       # unresolved late attack -> kill-switch watch
    return "OPEN"


def submit_round(state, round_num, judge_signals):
    """
    judge_signals: { crux_id: {
        "signal": float in [-1,1],            # +bull / -bear, |0.5|=weak |1|=strong
        "rationale": str,
        "citations": [ {claim,number,source,url,date} ],
        "best_bull": str|None, "best_bear": str|None,
    } }
    Signals for RETIRED cruxes are ignored (crux-scoping: we didn't fire agents on them).
    """
    fired = []
    normalized_signals = {}
    for cid, cx in state["cruxes"].items():
        js = _normalize_signal(judge_signals.get(cid, {}))
        normalized_signals[cid] = js
        s = float(js.get("signal", 0.0))
        # a strong NEW attack re-opens a previously settled/retired crux (forced-novelty)
        if cx["retired"] and s <= -0.5:
            cx["retired"] = False
            cx["status"] = "OPEN"
        if cx["retired"]:
            cx["p_history"].append(_sig(cx["L"]))   # carry forward; not re-debated
            continue
        cx["L"] = _clamp(DECAY * cx["L"] + K * s, -L_MAX, L_MAX)
        cx["p_history"].append(_sig(cx["L"]))
        cx["last_signal"] = s
        if s != 0.0:                                # contested this round
            fired.append(cid)
            if cx["first_contested"] is None:
                cx["first_contested"] = round_num
            cx["contested_history"].append(_sig(cx["L"]))
            for c in js.get("citations", []):
                cx["citations"].append({**c, "round": round_num})
            if js.get("best_bull"): cx["best_bull"] = js["best_bull"]
            if js.get("best_bear"): cx["best_bear"] = js["best_bear"]
            cx["status"] = _update_status(cx, round_num)   # re-evaluate only on contest
            if cx["status"] in ("RESOLVED_BULL", "RESOLVED_BEAR", "MONITORABLE") and round_num >= MIN_ROUNDS:
                cx["retired"] = True                # crux-scoping: stop firing agents on it

    probs = {cid: cx["p_history"][-1] for cid, cx in state["cruxes"].items()}
    weakest = min(probs, key=probs.get)
    mean_L = sum(math.log(p/(1-p)) for p in probs.values()) / len(probs)
    decision = _decide(probs[weakest], _sig(mean_L))
    state["rounds"].append({"round": round_num, "fired_cruxes": fired, "signals": normalized_signals})
    state["decision_trace"].append({
        "round": round_num, "weakest": weakest,
        "p_weakest": round(probs[weakest], 4), "p_mean": round(_sig(mean_L), 4),
        "decision": decision,
    })
    return convergence(state, round_num)


def _decide(p_weakest, p_mean):
    if p_weakest >= 0.60 and p_mean >= 0.62:  return "LONG"
    if p_weakest <= 0.40:                     return "NO-EDGE / AVOID"
    return "NO-EDGE (watch binding crux)"


def convergence(state, round_num):
    if round_num >= MAX_ROUNDS:
        return {"decision": "fuse_break", "round": round_num,
                "reason": f"达最大轮次 {MAX_ROUNDS}（应极少触发）。"}
    if round_num < MIN_ROUNDS:
        return {"decision": "continue", "round": round_num,
                "reason": f"轮次 {round_num} < 最低 {MIN_ROUNDS}。"}
    # every crux must be examined and settled or converted to a monitorable watch-item
    unsettled = [cid for cid, cx in state["cruxes"].items()
                 if cx["status"] in ("PENDING", "OPEN")]
    if unsettled:
        return {"decision": "continue", "round": round_num,
                "reason": f"仍有未检验/活跃 crux: {unsettled}（继续，且仅对这些派子智能体）。",
                "open_cruxes": unsettled}
    # completeness guard: adversary must have gone "dry" (no new crux for DRY_ROUNDS)
    if round_num - state["max_introduced_round"] < DRY_ROUNDS:
        return {"decision": "continue", "round": round_num,
                "reason": f"R{state['max_introduced_round']} 才引入新 crux，需再质证 {DRY_ROUNDS} 轮确认审问者已无新攻击面。"}
    # decision stability over last 2 rounds
    if len(state["decision_trace"]) >= 2:
        a, b = state["decision_trace"][-1], state["decision_trace"][-2]
        if a["decision"] != b["decision"] or abs(a["p_weakest"] - b["p_weakest"]) > EPS_STABLE:
            return {"decision": "continue", "round": round_num, "reason": "决策尚未稳定。"}
    return {"decision": "converge", "round": round_num,
            "reason": "每条 crux 已 RESOLVED 或转为可监控，且决策稳定。逻辑就绪。"}


def report_data(state):
    """Crux-organized ledger for the two-layer report (Layer A = proof ledger)."""
    cruxes = []
    for cid, cx in state["cruxes"].items():
        cruxes.append({
            "id": cid, "label": cx["label"], "p": round(cx["p_history"][-1], 3),
            "status": cx["status"], "best_bull": cx["best_bull"], "best_bear": cx["best_bear"],
            "monitor_anchor": cx["monitor_anchor"], "citations": cx["citations"],
            "valid_citations": [c for c in cx["citations"] if valid_citation(c)],
        })
    cruxes.sort(key=lambda c: c["p"])              # weakest (binding) first
    last = state["decision_trace"][-1] if state["decision_trace"] else {}
    return {
        "decision": last.get("decision"),
        "binding_crux": last.get("weakest"),
        "p_weakest": last.get("p_weakest"), "p_mean": last.get("p_mean"),
        "cruxes": cruxes,
        "n_citations": sum(len(c["citations"]) for c in cruxes),
    }


# ─────────────────────────── self-test: replay REAL 绿色算力 ───────────────────────────
if __name__ == "__main__":
    # Faithful to the real run: C1/C2/C3 framed up front; adversary discovers C4@R5, C5@R6, C6@R9.
    INIT = [
        {"id": "C1", "label": "时空错配/储能成本",  "monitor_anchor": "西部到户综合电价(含储能), 储能EPC元/Wh"},
        {"id": "C2", "label": "液冷/PFAS介质",     "monitor_anchor": "冷板式市占率, 巨化/新宙邦氟化液产能"},
        {"id": "C3", "label": "WUE水资源红线",     "monitor_anchor": "西部干冷器节点实测WUE, 水预算配额"},
    ]
    LATE = {5: {"id": "C4", "label": "电网零惯量/RoCoF",  "monitor_anchor": "GFM-BESS循环寿命@阶跃负荷, RoCoF实测"},
            6: {"id": "C5", "label": "变压器/GOES产能墙", "monitor_anchor": "0.18mm取向硅钢良率, 变压器交付周期"},
            9: {"id": "C6", "label": "需求/供给过剩/绿证","monitor_anchor": "智算上架率, 绿证均价, 训练/推理结构占比"}}
    SIG = {
        "C1": {1:-0.5,3:0.5,4:0.5,5:0.5,7:0.5,8:0.5,9:1.0,10:0.5,11:0.5,12:-0.5},
        "C2": {2:-0.5,3:0.5,4:0.5,5:1.0,6:0.5,8:0.5,9:1.0,11:0.5,12:0.5},
        "C3": {1:-0.5,2:0.5,3:0.5,4:1.0,7:0.5,11:-0.5},
        "C4": {5:-0.5,7:0.5,8:0.5,9:1.0,10:0.5,12:-1.0},
        "C5": {6:-0.5,8:0.5,11:1.0,12:-0.3},
        "C6": {9:-1.0,10:-0.5,11:0.2},
    }
    st = new_state("绿色算力景气度与产业链", "绿色算力产业链是否值得做多(3-6月)", "3-6M", INIT)
    OLD = [33.33,24.53,12.4,6.61,3.42,1.14,0.29,0.07,0.0,0.0,0.0,0.0]
    stop_round, active_per_round = None, []
    print("旧引擎单一后验:  " + " → ".join(f"{p:.1f}" for p in OLD) + "   (撞0钉死, 跑满12轮)\n")
    print("新引擎每轮快照 (P% / R=已退休不再派agent):")
    for r in range(1, 13):
        if r in LATE: add_crux(st, LATE[r], r)
        active = [cid for cid, cx in st["cruxes"].items() if not cx["retired"]]
        active_per_round.append(len(active))
        js = {cid: {"signal": SIG[cid].get(r, 0.0), "best_bull": "(略)", "best_bear": "(略)",
                    "citations": ([{"claim": "demo", "number": "1", "source": "demo", "url": "https://example.com/source", "date": "2026"}]
                                  if SIG[cid].get(r, 0.0) != 0 else [])}
              for cid in st["cruxes"]}
        conv = submit_round(st, r, js)
        line = " ".join(f"{cid}:{int(round(st['cruxes'][cid]['p_history'][-1]*100)):>3}"
                        + ("R" if st['cruxes'][cid]['retired'] else " ") for cid in st["cruxes"])
        dt = st["decision_trace"][-1]
        print(f"  R{r:<2}[{len(active)}活跃] {line.ljust(48)} | 弱={dt['weakest']}({int(dt['p_weakest']*100)}%) {dt['decision']:<22} {conv['decision']}")
        if conv["decision"] in ("converge", "fuse_break") and stop_round is None:
            stop_round = r; break
    old_calls = 12 * 6 * 2                     # 12 rounds × 6 cruxes × 2 agents (no scoping)
    new_calls = sum(active_per_round) * 2      # only active cruxes × 2 agents
    stop_label = "收敛" if conv["decision"] == "converge" else f"停止({conv['decision']})"
    print(f"\n→ 新引擎 R{stop_round} {stop_label}, 且正确暴露了 C6(旧引擎在 R6 的 buggy 版本会漏掉它)。")
    print(f"  子智能体调用(crux×agent): 旧≈{old_calls} 次 → 新≈{new_calls} 次  (省 ~{round((1-new_calls/old_calls)*100)}%, 主要来自 crux 收窄)")
    print(f"  平均每轮活跃 crux: {sum(active_per_round)/len(active_per_round):.1f} / 6\n")
    rd = report_data(st)
    print(f"决策: {rd['decision']}  | binding crux: {rd['binding_crux']} ({int(rd['p_weakest']*100)}%) "
          f"| 命题均值 {int(rd['p_mean']*100)}%  (旧引擎: 0.0%)")
    print("每条 crux 终局 (弱→强, 自动带监控锚点+引用计数):")
    for c in rd["cruxes"]:
        print(f"  {c['id']} {c['label'].ljust(18)} {int(c['p']*100):>3}%  {c['status']:<14} "
              f"引用×{len(c['citations'])}  盯: {c['monitor_anchor']}")
