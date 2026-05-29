"""
Trade Nothing v0.9.4 — DeepThink Engine

统一控制器：状态追踪 + 收敛判定 + 12轮熔断 + 未反驳攻击向量 JSON 数据存储。
已升级为工业级/顶刊水平：集成邓氏抽象论证框架、信息商衰减、确定性贝叶斯赔率更新与平庸共识过滤器。
"""

import argparse
import json
import os
import sys
import time
import re
import math
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import List, Set, Tuple, Dict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)

from dungs_argumentation import DungSolver

import threading
_state_local = threading.local()

DEFAULT_STATE_FILE = os.path.join(SCRIPT_DIR, ".deepthink_state.json")

def get_state_file() -> str:
    if not hasattr(_state_local, "state_file"):
        _state_local.state_file = DEFAULT_STATE_FILE
    return _state_local.state_file

def set_state_file(path: str):
    _state_local.state_file = path

def generate_topic_slug(topic: str) -> str:
    """Convert topic text to a clean, lowercase, alphanumeric-and-underscore slug"""
    if not topic:
        return "general"
    
    # Try to extract stock code (6 digits)
    codes = re.findall(r"\d{6}", topic)
    code_prefix = f"{codes[0]}_" if codes else ""
    
    # Clean words
    words = re.findall(r"[\u4e00-\u9fa5\w]+", topic.lower())
    stopwords = {"研究", "分析", "破产", "重整", "关于", "价格", "走势", "突破", "标的", "效率", "技术"}
    cleaned_words = [w for w in words if len(w) > 0 and w not in stopwords]
    
    if not cleaned_words:
        cleaned_words = ["general"]
        
    slug = "_".join(cleaned_words)
    if len(slug) > 30:
        slug = slug[:30].rstrip("_")
    return code_prefix + slug

def resolve_state_file(topic: str = "", state_file_override: str = ""):
    if state_file_override:
        set_state_file(state_file_override)
    elif topic:
        slug = generate_topic_slug(topic)
        state_dir = os.path.join(SCRIPT_DIR, ".state")
        os.makedirs(state_dir, exist_ok=True)
        set_state_file(os.path.join(state_dir, f"{slug}_state.json"))
    else:
        set_state_file(DEFAULT_STATE_FILE)

MIN_ROUNDS = 3
MAX_ROUNDS = 12
LFI_THRESHOLD = 0.15
TIMER_DURATION = 15  # 15s interactive timer


# ─── State ───

_thread_lock = threading.RLock()


def load_state() -> dict:
    state_file = get_state_file()
    if os.path.exists(state_file):
        try:
            from utils import CrossPlatformFileLock
            lock = CrossPlatformFileLock(state_file)
            with lock:
                with open(state_file, "r", encoding="utf-8") as f:
                    with _thread_lock:
                        data = json.load(f)
                        return data
        except Exception:
            pass
    return {
        "rounds": [],
        "started_at": None,
        "topic": None,
        "unrefuted_attacks": [],
        "accumulated_evidence": [],
        "accumulated_claims": [],
        "odds": 1.0,  # Prior odds = 1.0 (P = 50%)
        "posterior": 50.0
    }

def save_state(state: dict):
    state_file = get_state_file()
    os.makedirs(os.path.dirname(os.path.abspath(state_file)), exist_ok=True)
    try:
        from utils import CrossPlatformFileLock
        lock = CrossPlatformFileLock(state_file)
        with lock:
            with open(state_file, "w", encoding="utf-8") as f:
                with _thread_lock:
                    json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] failed to save state file {state_file}: {e}", file=sys.stderr)



# ─── Convergence ───

def get_topic_mode(topic: str) -> str:
    """Classify research target/topic into 'audit' (cyclical/commodity) or 'vision' (high-optionality/tech) mode."""
    if not topic:
        return "audit"
    topic_lower = topic.lower()
    cyclical_keywords = ["solar", "光伏", "新能源", "hjt", "电池", "锂电", "topcon", "储能", "电池柜", "300118", "宁德时代", "隆基"]
    for kw in cyclical_keywords:
        if kw in topic_lower:
            return "audit"
    return "vision"

def classify_argument(arg: str) -> str:
    """Classify Dung graph argument claims based on their node semantic prefix."""
    if "[Proxy Data Anchor" in arg or "[Audit Node" in arg:
        return "audit"
    elif "[Vision Node" in arg:
        return "vision"
    elif "[Narrative Node" in arg:
        return "narrative"
    else:
        return "legacy"

def check_convergence(round_num: int, lfi: float, open_attacks: int, mode: str = "audit",
                      posterior_trace: list = None) -> dict:
    lfi_threshold = LFI_THRESHOLD if mode == "audit" else 0.25
    
    if round_num >= MAX_ROUNDS:
        return {"decision": "fuse_break",
                "reason": f"已达最大轮次 {MAX_ROUNDS}，触发熔断。"}

    if round_num < MIN_ROUNDS:
        return {"decision": "continue",
                "reason": f"轮次 {round_num} < 最低要求 {MIN_ROUNDS}，必须继续进行质证硬化。"}

    if open_attacks > 0:
        return {"decision": "continue",
                "reason": f"存在 {open_attacks} 个未完全反驳的攻击向量（Dung图中残余摩擦节点），必须继续。"}

    # Fix 5: Extreme bias detection — posterior >95% or <5% requires ≥5 rounds
    if posterior_trace and len(posterior_trace) >= 1:
        latest_p = posterior_trace[-1]
        if (latest_p > 95.0 or latest_p < 5.0) and round_num < 5:
            return {"decision": "continue",
                    "reason": f"后验概率 {latest_p:.1f}% 处于极端偏置区（>95% 或 <5%），需要至少 5 轮充分质证。"}

    # Fix 5: Bayesian stability — posterior must stabilize (Δ < 5% in last 2 rounds)
    if posterior_trace and len(posterior_trace) >= 2:
        recent_delta = abs(posterior_trace[-1] - posterior_trace[-2])
        if recent_delta > 5.0:
            return {"decision": "continue",
                    "reason": f"后验概率仍在大幅波动 (Δ={recent_delta:.1f}%)，需要继续质证直至稳定。"}

    if lfi >= lfi_threshold:
        return {"decision": "continue",
                "reason": f"逻辑摩擦力指数 LFI={lfi:.4f} >= {lfi_threshold} ({mode}模式)，论证冲突未平息或信息量未饱和。"}

    return {"decision": "converge",
            "reason": f"LFI={lfi:.4f} < {lfi_threshold} ({mode}模式)，论证冲突完全收敛，未反驳致命漏洞归零。逻辑硬化达成。"}



# ─── NLP Jaccard Novelty Helper ───

def tokenize(text: str) -> set:
    """Helper to extract clean alphanumeric words and individual Chinese characters from text"""
    # Extract English/Alphanumeric words
    en_words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    tokens = set(en_words)
    
    # Extract Chinese characters as unigrams
    zh_chars = re.findall(r"[\u4e00-\u9fa5]", text)
    tokens.update(zh_chars)
    
    return tokens

def calculate_jaccard_novelty(new_texts: List[str], prior_texts: List[str]) -> float:
    """Calculate the Jaccard distance between new claims and prior claims for lexical novelty"""
    if not prior_texts:
        return 1.0
        
    new_tokens = set()
    for t in new_texts:
        new_tokens.update(tokenize(t))
        
    prior_tokens = set()
    for t in prior_texts:
        prior_tokens.update(tokenize(t))
        
    if not new_tokens:
        return 0.0
        
    intersection = new_tokens.intersection(prior_tokens)
    union = new_tokens.union(prior_tokens)
    
    # Jaccard distance = 1 - Jaccard similarity
    return 1.0 - (len(intersection) / len(union))


# ─── Flat Consensus Overlap Filter ───

def check_consensus_flatness(claims: List[str], forbidden_consensus: List[str], mode: str = "audit") -> List[str]:
    """
    Check if any new claim overlaps too much with forbidden clichés using dynamic TF-IDF cosine similarity.
    Returns list of rejected claims.
    """
    from utils import calculate_cosine_similarity
    # Dynamic sector-specific threshold: growth tech sectors are strict (0.70); cyclical sectors are relaxed (0.85)
    threshold = 0.85 if mode == "audit" else 0.70
    rejected = []
    for claim in claims:
        for cliché in forbidden_consensus:
            sim = calculate_cosine_similarity(claim, cliché)
            if sim >= threshold:
                rejected.append(f"Claim: '{claim}' (Semantic similarity {sim*100:.1f}% with cliché: '{cliché}')")
                break
    return rejected


# ─── Bayesian Odds Matrix ───

BAYES_FACTOR_MATRIX = {
    "Hard Proxy Data": {
        "Bull": {"Strong": 4.0, "Weak": 2.0},
        "Bear": {"Strong": 0.25, "Weak": 0.5}
    },
    "Factual Disclosed": {
        "Bull": {"Strong": 3.0, "Weak": 1.5},
        "Bear": {"Strong": 0.33, "Weak": 0.67}
    },
    "Channel Checks": {
        "Bull": {"Strong": 2.0, "Weak": 1.2},
        "Bear": {"Strong": 0.5, "Weak": 0.83}
    },
    "Narrative": {
        "Bull": {"Strong": 1.0, "Weak": 1.0},
        "Bear": {"Strong": 1.0, "Weak": 1.0}
    }
}

def get_bayes_factor(category: str, direction: str, strength: str) -> float:
    """Safely map evidence to Bayes Factor using the structured matrix"""
    cat = category if category in BAYES_FACTOR_MATRIX else "Narrative"
    dir_ = direction if direction in ["Bull", "Bear"] else "Bull"
    str_ = strength if strength in ["Strong", "Weak"] else "Weak"
    
    return BAYES_FACTOR_MATRIX[cat][dir_][str_]


# ─── Timer ───

def run_timer(duration: int = TIMER_DURATION) -> str:
    """Terminal countdown timer with hotkeys"""
    # Headless safety guardrail: if not a TTY, bypass countdown immediately
    if not sys.stdin.isatty():
        sys.stderr.write("⚠️  [DeepThink Engine] 检测到处于无头环境/非TTY，自动跳过倒计时定时器。\n")
        return "continue"

    print(f"\n⏳ [DeepThink Engine] 下一轮将在 {duration}s 后自动开始。", file=sys.stderr)
    print("快捷键: [C]继续 | [S]停止出报告 | [M]手动模式\n", file=sys.stderr)

    start = time.time()
    last_sec = -1
    while True:
        elapsed = time.time() - start
        remaining = int(duration - elapsed)

        if remaining != last_sec:
            sys.stderr.write(f"\r\033[K⏱️  {max(0, remaining)}s ... [C/S/M] ")
            sys.stderr.flush()
            last_sec = remaining

        if elapsed >= duration:
            sys.stderr.write("\n\033[K▶️  超时，自动继续。\n")
            return "continue"

        # Safe fallback non-blocking keyboard input
        try:
            import select
            rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
            if rlist:
                ch = sys.stdin.read(1).lower()
                if ch in ('c', '\r', '\n'):
                    sys.stderr.write("\n\033[K▶️  继续下一轮。\n")
                    return "continue"
                elif ch == 's':
                    sys.stderr.write("\n\033[K🛑  停止递归，生成最终报告。\n")
                    return "stop"
                elif ch == 'm':
                    sys.stderr.write("\n\033[K⏸️  手动模式。\n")
                    return "manual"
        except Exception:
            # Fallback if select/termios is not supported (e.g. non-interactive/cloud context)
            time.sleep(0.1)


# ─── Commands ───

def cmd_start(topic: str):
    state_file = get_state_file()
    if os.path.exists(state_file):
        os.remove(state_file)

    state = {
        "rounds": [],
        "started_at": datetime.now().isoformat(),
        "topic": topic,
        "unrefuted_attacks": [],
        "accumulated_evidence": [],
        "accumulated_claims": [],
        "odds": 1.0,
        "posterior": 50.0
    }
    save_state(state)

    template = (
        f"[SCOPE] 标的: {topic} | 核心命题: [一句可证伪的非共识上涨陈述] | 时间视野: 3-6个月\n"
        f"[PRIOR] P₀ = 50.0% (Odds = 1.0)\n"
        f"[反向溯因] 🔴暴跌70%死亡路径: ___ | 🟢暴涨100%牛市剧本: ___"
    )

    output = {
        "action": "start",
        "topic": topic,
        "session_started": state["started_at"],
        "template": template,
        "instruction": (
            "新分析已初始化。首先调用工具获取边缘数据/共识背景，设定平庸共识禁区，"
            "然后启动 Round 1 的 Detective→Inquisitor→Judge 并行辩论。"
        ),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_checkpoint(args):
    state = load_state()

    if not state["started_at"]:
        state["started_at"] = datetime.now().isoformat()

    # 1. Parse JSON Arguments
    new_arguments = []
    if args.arguments_json:
        try:
            new_arguments = json.loads(args.arguments_json)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse arguments-json: {e}", file=sys.stderr)
            sys.exit(1)

    new_attacks = []
    if args.attacks_json:
        try:
            new_attacks = json.loads(args.attacks_json)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse attacks-json: {e}", file=sys.stderr)
            sys.exit(1)

    new_evidence = []
    if args.evidence_json:
        try:
            new_evidence = json.loads(args.evidence_json)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse evidence-json: {e}", file=sys.stderr)
            sys.exit(1)

    forbidden_consensus = []
    if args.forbidden_consensus_json:
        try:
            forbidden_consensus = json.loads(args.forbidden_consensus_json)
        except json.JSONDecodeError as e:
            print(f"[WARN] Failed to parse forbidden-consensus-json: {e}", file=sys.stderr)

    # Resolve topic mode first
    mode = get_topic_mode(state["topic"])

    # 2. Check Consensus Flatness Guardrail
    if forbidden_consensus:
        flat_claims = check_consensus_flatness(new_arguments, forbidden_consensus, mode=mode)
        if flat_claims:
            print(json.dumps({
                "status": "rejected",
                "reason": "检测到人云亦云的平庸共识，触碰过滤禁区！必须强制重新生成深层非共识命题。",
                "details": flat_claims
            }, ensure_ascii=False, indent=2))
            sys.exit(0)

    # 3. Compute Dung's Abstract Argumentation AFI with Adaptive Constraints
    
    # Process arguments with virtual penalty nodes for Audit Mode
    all_arguments = set(new_arguments)
    all_attacks = set(tuple(a) for a in new_attacks)
    
    # Inject active penalty attacks for unanchored/visionary claims in Audit Mode
    if mode == "audit":
        for arg in list(all_arguments):
            arg_type = classify_argument(arg)
            if arg_type == "vision" or (arg_type == "legacy" and "[Proxy Data Anchor" not in arg):
                penalty_node = "System:AuditHardenedPenalty"
                all_arguments.add(penalty_node)
                all_attacks.add((penalty_node, arg))
                
    # Pull any unresolved arguments from previous rounds
    for r in state["rounds"]:
        prev_args = r.get("arguments", [])
        prev_attacks = r.get("attacks", [])
        all_arguments.update(prev_args)
        all_attacks.update(tuple(a) for a in prev_attacks)
        # Apply historical audit penalty if graph has legacy nodes
        if mode == "audit":
            for arg in prev_args:
                arg_type = classify_argument(arg)
                if arg_type == "vision" or (arg_type == "legacy" and "[Proxy Data Anchor" not in arg):
                    penalty_node = "System:AuditHardenedPenalty"
                    all_arguments.add(penalty_node)
                    all_attacks.add((penalty_node, arg))

    solver = DungSolver(list(all_arguments), list(all_attacks))
    # Fix 4: Compute fuzzy valuations once, derive GE and AFI from it
    fuzzy_V = solver.compute_fuzzy_valuations()
    ge = {arg for arg, val in fuzzy_V.items() if val >= 0.5}
    afi = sum(1.0 - val for val in fuzzy_V.values()) / max(1, len(fuzzy_V))
    
    # Fix 4: Use fuzzy belief threshold 0.3 (not binary GE ≥ 0.5)
    # Attacks with residual belief 0.3-0.5 still represent unresolved friction
    unrefuted_attacks_list = []
    for attacker, target in all_attacks:
        belief = fuzzy_V.get(attacker, 0)
        if belief > 0.3:
            unrefuted_attacks_list.append({
                "attack": f"{attacker} -> {target}",
                "fuzzy_belief": round(belief, 4),
                "reason": f"论点 {attacker} 信念值 {belief:.4f}，攻击关系仍有残余摩擦。"
            })

    # Expectation Gap Index (EGI) calculation normalized to [-1.0, 1.0]
    narrative_count = sum(1 for arg in ge if classify_argument(arg) == "narrative")
    audit_count = sum(1 for arg in ge if classify_argument(arg) in ("audit", "legacy"))
    total_nodes = narrative_count + audit_count
    egi = float(narrative_count - audit_count) / max(1.0, float(total_nodes))

    # 4. Compute Evidence Saturation (Shannon Entropy + Jaccard Novelty)
    state["accumulated_evidence"].extend(new_evidence)
    
    categories = [e.get("category", "Narrative") for e in state["accumulated_evidence"]]
    total_e = len(categories)
    entropy = 0.0
    if total_e > 1:
        cat_counts = {}
        for cat in categories:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        for cat, cnt in cat_counts.items():
            p = cnt / total_e
            entropy -= p * math.log2(p)

    prior_claims_texts = state.get("accumulated_claims", [])
    novelty = calculate_jaccard_novelty(new_arguments, prior_claims_texts)
    state["accumulated_claims"].extend(new_arguments)
    
    prev_entropy = 0.0
    if len(state["rounds"]) > 0:
        prev_entropy = state["rounds"][-1].get("entropy", 0.0)
        
    delta_h = (entropy - prev_entropy) + novelty
    
    round_num = args.round
    # Fix 2: Dampened ES saturation — prevents premature convergence
    # gamma reduced 0.5→0.15; +1.0 in denominator stabilizes early rounds
    gamma = 0.15
    if delta_h > 0:
        es = 1.0 - math.exp(-gamma * round_num / (delta_h + 1.0))
    else:
        # No new information, but don't instant-saturate — gradual cap at 0.7
        es = min(0.7, 0.1 * round_num)

    lfi = 0.6 * afi + 0.4 * (1.0 - es)

    # 5. Deterministic Bayesian Odds Update
    odds = state.get("odds", 1.0)
    for e in new_evidence:
        bf = get_bayes_factor(e.get("category", "Narrative"), e.get("direction", "Bull"), e.get("strength", "Weak"))
        odds *= bf
        
    # Fix 3: Vision optionality premium — capped, first-appearance only
    if mode == "vision":
        prev_vision_nodes = set()
        for r in state.get("rounds", []):
            for node in r.get("grounded_extension", []):
                if classify_argument(node) == "vision":
                    prev_vision_nodes.add(node)
        
        new_vision_count = sum(
            1 for arg in ge
            if classify_argument(arg) == "vision" and arg not in prev_vision_nodes
        )
        # Cap at 2 new Vision Nodes per round, dampened factor 1.3 (was 1.5 uncapped)
        capped = min(new_vision_count, 2)
        odds *= 1.3 ** capped
                
    posterior = (odds / (1.0 + odds)) * 100.0
    
    state["odds"] = odds
    state["posterior"] = posterior

    # Parse raw sub-agent outputs if provided
    detective_raw = {}
    if hasattr(args, 'detective_raw_json') and args.detective_raw_json:
        try:
            detective_raw = json.loads(args.detective_raw_json)
        except (json.JSONDecodeError, TypeError):
            pass

    inquisitor_raw = {}
    if hasattr(args, 'inquisitor_raw_json') and args.inquisitor_raw_json:
        try:
            inquisitor_raw = json.loads(args.inquisitor_raw_json)
        except (json.JSONDecodeError, TypeError):
            pass

    round_data = {
        "round": round_num,
        "lfi": lfi,
        "afi": afi,
        "es": es,
        "entropy": entropy,
        "novelty": novelty,
        "posterior": round(posterior, 2),
        "open_attacks": len(unrefuted_attacks_list),
        "arguments": new_arguments,
        "attacks": new_attacks,
        "new_evidence_count": len(new_evidence),
        "next_action": args.next_action,
        "timestamp": datetime.now().isoformat(),
        "egi": egi,
        "mode": mode,
        "grounded_extension": list(ge),
        "detective_raw_output": detective_raw,
        "inquisitor_raw_output": inquisitor_raw
    }
    state["rounds"].append(round_data)
    state["unrefuted_attacks"] = unrefuted_attacks_list
    save_state(state)

    # Fix 5b: Pass posterior trace for stability and extreme bias checks
    posterior_trace = [r.get("posterior", 50.0) for r in state["rounds"]]
    convergence = check_convergence(round_num, lfi, len(unrefuted_attacks_list), mode=mode,
                                    posterior_trace=posterior_trace)
    bayesian_trace = " → ".join(
        f"R{r['round']}:{r['posterior']}%" for r in state["rounds"]
    )

    if convergence["decision"] in ("converge", "fuse_break"):
        instruction = "输出最终报告：硬门槛检查 → 情景矩阵 → 决策树 → 证据链 → 行动建议。"
        if convergence["decision"] == "fuse_break":
            instruction = ("⚠️ 熔断警告：已达最大轮次，结论可能未完全饱和。"
                           + instruction + " 列出所有未解决分歧。")

        output = {
            "action": convergence["decision"],
            "round_completed": round_num,
            "lfi": round(lfi, 4),
            "afi": round(afi, 4),
            "es": round(es, 4),
            "posterior": f"{round(posterior, 2)}%",
            "bayesian_trace": bayesian_trace,
            "total_rounds": len(state["rounds"]),
            "reason": convergence["reason"],
            "instruction": instruction,
            "egi": egi,
            "mode": mode
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    # Continue → check timer
    if args.no_timer:
        user_choice = "continue"
    else:
        try:
            user_choice = run_timer(TIMER_DURATION)
        except Exception:
            user_choice = "continue"

    if user_choice == "stop":
        output = {
            "action": "stop",
            "round_completed": round_num,
            "posterior": f"{round(posterior, 2)}%",
            "bayesian_trace": bayesian_trace,
            "total_rounds": len(state["rounds"]),
            "reason": "用户主动停止。",
            "instruction": "用户要求停止。输出基于当前证据的最终报告（标注为提前终止）。",
            "egi": egi,
            "mode": mode
        }
    elif user_choice == "manual":
        output = {
            "action": "manual",
            "round_completed": round_num,
            "posterior": f"{round(posterior, 2)}%",
            "bayesian_trace": bayesian_trace,
            "total_rounds": len(state["rounds"]),
            "instruction": "用户选择手动模式。等待用户输入具体指令。",
            "egi": egi,
            "mode": mode
        }
    else:
        output = {
            "action": "continue",
            "round_completed": round_num,
            "next_round": round_num + 1,
            "lfi": round(lfi, 4),
            "afi": round(afi, 4),
            "es": round(es, 4),
            "posterior": f"{round(posterior, 2)}%",
            "bayesian_trace": bayesian_trace,
            "total_rounds": len(state["rounds"]),
            "remaining_before_fuse": MAX_ROUNDS - round_num,
            "reason": convergence["reason"],
            "fetch_hint": args.next_action,
            "egi": egi,
            "mode": mode,
            "instruction": (
                f"进入 Round {round_num + 1} ({mode}模式)。"
                f"先执行工具调用或搜索获取: {args.next_action}。"
                f"然后进行 Detective→Inquisitor→Judge 质证分析。"
            ),
        }

    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_status():
    state = load_state()
    if not state["rounds"]:
        print(json.dumps({"status": "idle", "message": "没有进行中的 deepthink 会话。"},
                          ensure_ascii=False, indent=2))
        return

    latest = state["rounds"][-1]
    mode = get_topic_mode(state.get("topic", ""))
    posterior_trace = [r.get("posterior", 50.0) for r in state["rounds"]]
    convergence = check_convergence(
        latest["round"], latest["lfi"], latest.get("open_attacks", 0), mode=mode,
        posterior_trace=posterior_trace)
    bayesian_trace = " → ".join(
        f"R{r['round']}:{r['posterior']}%" for r in state["rounds"])

    output = {
        "status": "active",
        "topic": state.get("topic", ""),
        "started_at": state["started_at"],
        "total_rounds": len(state["rounds"]),
        "latest_round": latest["round"],
        "latest_lfi": round(latest["lfi"], 4),
        "latest_posterior": f"{latest['posterior']}%",
        "bayesian_trace": bayesian_trace,
        "convergence_check": convergence,
        "remaining_before_fuse": MAX_ROUNDS - latest["round"],
        "mode": mode,
        "egi": latest.get("egi", 0.0)
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))



# ─── CLI ───

def main():
    parser = argparse.ArgumentParser(description="DeepThink Engine v0.9.4")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--start", action="store_true", help="初始化新分析")
    mode.add_argument("--checkpoint", action="store_true", help="记录轮次并判定收敛")
    mode.add_argument("--status", action="store_true", help="查看会话状态")

    parser.add_argument("--topic", type=str, default="", help="分析标的")
    parser.add_argument("--state-file", type=str, default="", help="自定义状态文件路径")
    parser.add_argument("--round", type=int, help="当前轮次编号")
    parser.add_argument("--next-action", type=str, default="", help="下一轮应获取的数据")
    
    # Upgraded JSON Inputs for Industrial Math
    parser.add_argument("--arguments-json", type=str, default="", help="当前轮次活跃论点列表 (JSON format)")
    parser.add_argument("--attacks-json", type=str, default="", help="论点有向图攻击关系对列表 (JSON format)")
    parser.add_argument("--evidence-json", type=str, default="", help="当前轮次新引入的证据详情 (JSON format)")
    parser.add_argument("--forbidden-consensus-json", type=str, default="", help="被禁止的平庸共识逻辑 (JSON format)")
    parser.add_argument("--detective-raw-json", type=str, default="", help="Detective 子智能体的完整原始 JSON 输出 (用于完整博弈日志)")
    parser.add_argument("--inquisitor-raw-json", type=str, default="", help="Inquisitor 子智能体的完整原始 JSON 输出 (用于完整博弈日志)")
    
    parser.add_argument("--no-timer", action="store_true", help="跳过 timer（调试用）")

    args = parser.parse_args()

    resolve_state_file(topic=args.topic, state_file_override=args.state_file)

    if args.start:
        cmd_start(args.topic)
    elif args.checkpoint:
        if args.round is None:
            parser.error("--checkpoint 需要 --round")
        cmd_checkpoint(args)
    elif args.status:
        cmd_status()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 中断。", file=sys.stderr)
        sys.exit(1)
