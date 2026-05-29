#!/usr/bin/env python3
"""
Trade Nothing v0.9.2 — Deterministic DeepThink Orchestrator

确定性状态机：将控制流从 LLM 手中夺走，交给代码。
LLM 不再是 Orchestrator，它被降级为"受控内容生产者"。

Commands:
  --run:            初始化流程，输出第一轮子智能体调度指令
  --submit-round:   提交子智能体输出，调用引擎 checkpoint，判定下一步
  --preflight:      报告生成前的强制预检门
  --compile-report: 从 state.json 物理读取数值，编译最终报告
"""

import os
import sys
import json
import argparse
import subprocess
import re
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENGINE_PATH = os.path.join(SCRIPT_DIR, "deepthink_engine.py")
PIPELINE_PATH = os.path.join(SCRIPT_DIR, "deepthink_pipeline.py")


def _run_script(cmd_args: list) -> dict:
    """Run a child script and parse its JSON output."""
    result = subprocess.run(
        ["python3"] + cmd_args,
        capture_output=True, text=True, cwd=SCRIPT_DIR
    )
    if result.returncode != 0:
        return {"status": "error", "exit_code": result.returncode,
                "stderr": result.stderr.strip(), "stdout": result.stdout.strip()}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"status": "ok_raw", "stdout": result.stdout.strip()}


def _resolve_state_path(topic: str) -> str:
    """Resolve the state file path for a given topic, matching engine's logic."""
    if not topic:
        return os.path.join(SCRIPT_DIR, ".deepthink_state.json")
    # Mirror generate_topic_slug from engine
    codes = re.findall(r"\d{6}", topic)
    code_prefix = f"{codes[0]}_" if codes else ""
    words = re.findall(r"[\u4e00-\u9fa5\w]+", topic.lower())
    stopwords = {"研究", "分析", "破产", "重整", "关于", "价格", "走势", "突破", "标的", "效率", "技术"}
    cleaned = [w for w in words if len(w) > 0 and w not in stopwords]
    if not cleaned:
        cleaned = ["general"]
    slug = "_".join(cleaned)
    if len(slug) > 30:
        slug = slug[:30].rstrip("_")
    slug = code_prefix + slug
    state_dir = os.path.join(SCRIPT_DIR, ".state")
    return os.path.join(state_dir, f"{slug}_state.json")


def _load_state(topic: str) -> dict:
    """Load physical state file."""
    path = _resolve_state_path(topic)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════
# Command: --run
# ═══════════════════════════════════════════════════════════════

def cmd_run(topic: str):
    """
    Phase 1+2: Initialize the pipeline.
    1. Extract negative priors from Evolution.md
    2. Start the engine (create fresh state)
    3. Generate Round 1 prompts
    4. Output JSON instructions for LLM to dispatch subagents
    """
    # Step 1: Extract priors
    priors = _run_script([PIPELINE_PATH, "--extract", "--topic", topic])

    # Step 2: Start engine
    engine_start = _run_script([ENGINE_PATH, "--start", "--topic", topic])
    if engine_start.get("status") == "error":
        print(json.dumps({"status": "error", "phase": "engine_start",
                          "detail": engine_start}, ensure_ascii=False, indent=2))
        sys.exit(2)

    # Step 3: Generate prompts
    prompts = _run_script([PIPELINE_PATH, "--generate-prompts", "--topic", topic])
    if prompts.get("status") == "error":
        print(json.dumps({"status": "error", "phase": "generate_prompts",
                          "detail": prompts}, ensure_ascii=False, indent=2))
        sys.exit(2)

    # Step 4: Output dispatch instructions
    output = {
        "status": "dispatch_subagents",
        "phase": "round_1_pending",
        "topic": topic,
        "round": 1,
        "negative_priors": priors.get("stdout", str(priors)) if isinstance(priors, dict) else str(priors),
        "detective_prompt": prompts.get("detective_prompt", ""),
        "inquisitor_prompt": prompts.get("inquisitor_prompt", ""),
        "forbidden_consensus": prompts.get("forbidden_consensus", []),
        "instruction": (
            "请按以下步骤执行：\n"
            "1. 使用 detective_prompt 派发隔离的 Detective 子智能体\n"
            "2. 使用 inquisitor_prompt 派发隔离的 Inquisitor 子智能体\n"
            "3. 收到两者的 JSON 输出后，调用:\n"
            "   python3 scripts/deepthink_orchestrator.py --submit-round "
            f"--topic \"{topic}\" "
            "--detective-json '<detective_output>' "
            "--inquisitor-json '<inquisitor_output>'\n"
            "4. ⚠️ 严禁在未调用 --submit-round 的情况下直接输出任何研报或数值！"
        )
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ═══════════════════════════════════════════════════════════════
# Command: --submit-round
# ═══════════════════════════════════════════════════════════════

def _extract_arguments_from_detective(detective_json: dict) -> list:
    """Extract Dung argument nodes from Detective's evidence chain."""
    args = []
    for item in detective_json.get("evidence_chain", []):
        node = item.get("claim_node", "")
        if node:
            args.append(node)
    # Also extract rebuttal counter-claims
    for reb in detective_json.get("rebuttals", []):
        cc = reb.get("counter_claim", "")
        if cc:
            args.append(cc)
    return args


def _extract_attacks_from_inquisitor(inquisitor_json: dict) -> list:
    """Extract Dung attack edges from Inquisitor's lethal attack vectors."""
    attacks = []
    for vec in inquisitor_json.get("lethal_attack_vectors", []):
        attacker = vec.get("attack", "")
        target = vec.get("target_claim_node", "")
        if attacker and target:
            attacks.append([attacker, target])
    return attacks


def _extract_rebuttals_as_attacks(detective_json: dict) -> list:
    """Extract Detective's rebuttals as directed attack edges (counter → prior_attack)."""
    attacks = []
    for reb in detective_json.get("rebuttals", []):
        counter = reb.get("counter_claim", "")
        target = reb.get("target_attack_node", "")
        if counter and target:
            attacks.append([counter, target])
    return attacks


def _extract_evidence(detective_json: dict) -> list:
    """Extract evidence metadata for Bayesian update."""
    evidence = []
    for item in detective_json.get("evidence_chain", []):
        cat = item.get("category", "Narrative")
        # Normalize multi-category strings
        if "Hard Proxy" in cat or "Proxy Data" in cat:
            cat = "Hard Proxy Data"
        elif "Factual" in cat:
            cat = "Factual Disclosed"
        elif "Channel" in cat:
            cat = "Channel Checks"
        else:
            cat = "Narrative"

        confidence = item.get("confidence", "medium")
        strength = "Strong" if confidence == "high" else "Weak"

        evidence.append({
            "category": cat,
            "direction": "Bull",
            "strength": strength
        })
    return evidence


def _classify_evidence_category(text: str) -> str:
    """Classify evidence category from attack text content."""
    text_lower = text.lower()
    if any(kw in text_lower for kw in ["数据", "出口", "出货", "海关", "招标", "产能",
                                        "产量", "价格", "库存", "export", "customs",
                                        "data", "proxy", "出货量", "装机"]):
        return "Hard Proxy Data"
    elif any(kw in text_lower for kw in ["财报", "毛利", "营收", "eps", "利润", "现金流",
                                          "负债", "revenue", "margin", "earnings",
                                          "capex", "fcf", "pe", "估值"]):
        return "Factual Disclosed"
    elif any(kw in text_lower for kw in ["调研", "纪要", "渠道", "草根", "channel",
                                          "expert", "scuttlebutt", "草根调研"]):
        return "Channel Checks"
    return "Narrative"


def _extract_evidence_from_inquisitor(inquisitor_json: dict) -> list:
    """Extract Bear-direction evidence from Inquisitor's lethal attack vectors."""
    evidence = []
    for vec in inquisitor_json.get("lethal_attack_vectors", []):
        attack_text = vec.get("attack", "")
        if not attack_text:
            continue

        # Determine strength from severity or confidence
        severity = vec.get("severity", vec.get("confidence", "medium"))
        strength = "Strong" if severity in ("critical", "high") else "Weak"

        cat = _classify_evidence_category(attack_text)

        evidence.append({
            "category": cat,
            "direction": "Bear",
            "strength": strength
        })

    # Cognitive biases detected → weak Bear narrative evidence
    for bias in inquisitor_json.get("cognitive_biases_detected", []):
        if isinstance(bias, (str, dict)):
            evidence.append({
                "category": "Narrative",
                "direction": "Bear",
                "strength": "Weak"
            })

    # Death path → strong Bear channel evidence
    if inquisitor_json.get("death_path"):
        evidence.append({
            "category": "Channel Checks",
            "direction": "Bear",
            "strength": "Strong"
        })

    return evidence


def cmd_submit_round(topic: str, detective_json_str: str, inquisitor_json_str: str):
    """
    Phase 3: Submit a completed round's subagent outputs to the engine.
    Parses Detective & Inquisitor JSON → calls engine --checkpoint → outputs next action.
    """
    # Parse inputs
    try:
        detective_data = json.loads(detective_json_str)
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "error", "reason": f"Detective JSON parse error: {e}"},
                          ensure_ascii=False, indent=2))
        sys.exit(2)

    try:
        inquisitor_data = json.loads(inquisitor_json_str)
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "error", "reason": f"Inquisitor JSON parse error: {e}"},
                          ensure_ascii=False, indent=2))
        sys.exit(2)

    # Determine current round from state
    state = _load_state(topic)
    current_round = len(state.get("rounds", [])) + 1

    # Extract structured data
    arguments = _extract_arguments_from_detective(detective_data)
    attacks = _extract_attacks_from_inquisitor(inquisitor_data)
    rebuttal_attacks = _extract_rebuttals_as_attacks(detective_data)
    attacks.extend(rebuttal_attacks)
    # Fix 1: Bidirectional Bayesian — extract both Bull and Bear evidence
    evidence_bull = _extract_evidence(detective_data)
    evidence_bear = _extract_evidence_from_inquisitor(inquisitor_data)
    evidence = evidence_bull + evidence_bear

    # Call engine checkpoint
    engine_result = _run_script([
        ENGINE_PATH, "--checkpoint",
        "--topic", topic,
        "--round", str(current_round),
        "--arguments-json", json.dumps(arguments),
        "--attacks-json", json.dumps(attacks),
        "--evidence-json", json.dumps(evidence),
        "--detective-raw-json", detective_json_str,
        "--inquisitor-raw-json", inquisitor_json_str,
        "--no-timer"
    ])

    if engine_result.get("status") == "error":
        print(json.dumps({"status": "error", "phase": "engine_checkpoint",
                          "detail": engine_result}, ensure_ascii=False, indent=2))
        sys.exit(2)

    action = engine_result.get("action", "continue")

    if action in ("converge", "fuse_break"):
        # Convergence achieved or fuse break — report is now allowed
        output = {
            "status": "ready_for_report",
            "phase": "converged" if action == "converge" else "fuse_break",
            "topic": topic,
            "round_completed": current_round,
            "engine_output": engine_result,
            "instruction": (
                f"引擎判定: {action}。\n"
                "现在可以生成最终报告。请调用:\n"
                f"  python3 scripts/deepthink_orchestrator.py --compile-report --topic \"{topic}\"\n"
                "⚠️ 报告中的所有数值将由脚本从 state.json 物理读取，严禁手写任何 LFI/后验概率数值。"
            )
        }
    else:
        # Continue — generate next round prompts
        prompts = _run_script([PIPELINE_PATH, "--generate-prompts", "--topic", topic])

        output = {
            "status": "dispatch_subagents",
            "phase": f"round_{current_round + 1}_pending",
            "topic": topic,
            "round_completed": current_round,
            "next_round": current_round + 1,
            "engine_output": engine_result,
            "detective_prompt": prompts.get("detective_prompt", ""),
            "inquisitor_prompt": prompts.get("inquisitor_prompt", ""),
            "instruction": (
                f"引擎判定: 继续质证 (Round {current_round + 1})。\n"
                f"原因: {engine_result.get('reason', 'N/A')}\n"
                "请按以下步骤执行：\n"
                "1. 使用 detective_prompt 派发隔离的 Detective 子智能体\n"
                "2. 使用 inquisitor_prompt 派发隔离的 Inquisitor 子智能体\n"
                "3. 收到两者的 JSON 输出后，调用:\n"
                "   python3 scripts/deepthink_orchestrator.py --submit-round "
                f"--topic \"{topic}\" "
                "--detective-json '<detective_output>' "
                "--inquisitor-json '<inquisitor_output>'\n"
                "4. ⚠️ 严禁在未调用 --submit-round 的情况下直接输出任何研报或数值！"
            )
        }

    print(json.dumps(output, ensure_ascii=False, indent=2))


# ═══════════════════════════════════════════════════════════════
# Command: --preflight
# ═══════════════════════════════════════════════════════════════

def cmd_preflight(topic: str):
    """
    Pre-flight gate: Verify that the state allows report generation.
    Exit code 0 = pass, exit code 2 = blocked.
    """
    state = _load_state(topic)
    if not state:
        print(json.dumps({"status": "BLOCKED", "reason": "状态文件不存在。请先调用 --run 初始化。"},
                          ensure_ascii=False, indent=2))
        sys.exit(2)

    rounds = state.get("rounds", [])
    if len(rounds) < 3:
        print(json.dumps({"status": "BLOCKED",
                          "reason": f"仅完成 {len(rounds)} 轮，最低要求 3 轮。严禁提前出报告。"},
                          ensure_ascii=False, indent=2))
        sys.exit(2)

    last_round = rounds[-1]
    open_attacks = last_round.get("open_attacks", -1)
    lfi = last_round.get("lfi", 1.0)

    # Check convergence using engine's own logic
    from deepthink_engine import check_convergence, get_topic_mode
    mode = get_topic_mode(topic)
    posterior_trace = [r.get("posterior", 50.0) for r in rounds]
    convergence = check_convergence(last_round["round"], lfi, open_attacks, mode=mode,
                                    posterior_trace=posterior_trace)

    if convergence["decision"] not in ("converge", "fuse_break"):
        print(json.dumps({
            "status": "BLOCKED",
            "reason": f"引擎判定未收敛: {convergence['reason']}。严禁在未收敛状态下生成报告。",
            "lfi": lfi,
            "open_attacks": open_attacks,
            "convergence": convergence
        }, ensure_ascii=False, indent=2))
        sys.exit(2)

    # Passed
    output = {
        "status": "PASSED",
        "total_rounds": len(rounds),
        "lfi_final": round(lfi, 4),
        "posterior": round(state.get("posterior", 50.0), 2),
        "convergence": convergence,
        "mode": mode,
        "instruction": (
            "预检通过。现在可以调用:\n"
            f"  python3 scripts/deepthink_orchestrator.py --compile-report --topic \"{topic}\"\n"
            "生成最终报告。"
        )
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ═══════════════════════════════════════════════════════════════
# Command: --compile-report
# ═══════════════════════════════════════════════════════════════

def cmd_compile_report(topic: str):
    """
    Phase 4: Compile the final report from state.json.
    All numerical values are physically read from the state file.
    LLM provides ZERO numerical values — only qualitative text is accepted from it.
    """
    state = _load_state(topic)
    if not state or not state.get("rounds"):
        print(json.dumps({"status": "error", "reason": "无法编译报告：状态文件为空或不存在。"},
                          ensure_ascii=False, indent=2))
        sys.exit(2)

    rounds = state["rounds"]
    last_round = rounds[-1]
    total_rounds = len(rounds)
    lfi_final = round(last_round["lfi"], 4)
    posterior = round(state.get("posterior", 50.0), 2)
    mode = last_round.get("mode", "audit")
    egi = round(last_round.get("egi", 0.0), 2)

    # Bayesian trace
    bayesian_trace = " → ".join(
        f"R{r['round']}: {r['posterior']}%" for r in rounds
    )

    # Unrefuted attacks
    unrefuted = state.get("unrefuted_attacks", [])

    # Convergence status
    from deepthink_engine import check_convergence, get_topic_mode
    real_mode = get_topic_mode(topic)
    posterior_trace = [r.get("posterior", 50.0) for r in rounds]
    convergence = check_convergence(last_round["round"], last_round["lfi"],
                                    last_round.get("open_attacks", 0), mode=real_mode,
                                    posterior_trace=posterior_trace)

    # Build full debate log from all rounds
    full_debate_log = []
    for r in rounds:
        full_debate_log.append({
            "round": r["round"],
            "detective_output": r.get("detective_raw_output", {}),
            "inquisitor_output": r.get("inquisitor_raw_output", {}),
            "engine_metrics": {
                "lfi": round(r["lfi"], 4),
                "afi": round(r.get("afi", 0), 4),
                "es": round(r.get("es", 0), 4),
                "posterior": r["posterior"],
                "egi": round(r.get("egi", 0), 2),
                "open_attacks": r.get("open_attacks", 0),
                "entropy": round(r.get("entropy", 0), 4),
                "novelty": round(r.get("novelty", 0), 4)
            },
            "timestamp": r.get("timestamp", "")
        })

    output = {
        "status": "report_data_ready",
        "topic": topic,
        "physical_values": {
            "total_rounds": total_rounds,
            "lfi_final": lfi_final,
            "posterior_percent": posterior,
            "bayesian_trace": bayesian_trace,
            "egi": egi,
            "mode": mode,
            "convergence_decision": convergence["decision"],
            "convergence_reason": convergence["reason"],
            "open_attacks_count": last_round.get("open_attacks", 0),
            "unrefuted_attacks": unrefuted
        },
        "full_debate_log": full_debate_log,
        "instruction": (
            "以下数值字段已由物理引擎确定，请原封不动地填入报告模板中：\n"
            f"  - 博弈深度: {total_rounds} 轮\n"
            f"  - LFI 终值: {lfi_final}\n"
            f"  - 后验概率: {posterior}%\n"
            f"  - 贝叶斯演化: {bayesian_trace}\n"
            f"  - EGI: {egi}\n"
            f"  - 模式: {mode}\n"
            f"  - 收敛判定: {convergence['decision']}\n"
            f"  - 未反驳攻击数: {last_round.get('open_attacks', 0)}\n"
            "\n"
            "⚠️ 你只需提供定性内容（variant perception、scenario 描述、催化剂分析等）。\n"
            "⚠️ 严禁修改、四舍五入或替换上述任何数值！"
        )
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Trade Nothing v0.9.2 — Deterministic DeepThink Orchestrator"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run", action="store_true",
                       help="初始化 deepthink 流程并输出第一轮子智能体调度指令")
    group.add_argument("--submit-round", action="store_true",
                       help="提交子智能体输出，调用引擎 checkpoint 并判定下一步")
    group.add_argument("--preflight", action="store_true",
                       help="报告生成前的强制预检门")
    group.add_argument("--compile-report", action="store_true",
                       help="从 state.json 物理读取数值，编译最终报告数据")

    parser.add_argument("--topic", type=str, required=True, help="分析标的/主题")
    parser.add_argument("--detective-json", type=str, default="",
                       help="Detective 子智能体的 JSON 输出")
    parser.add_argument("--inquisitor-json", type=str, default="",
                       help="Inquisitor 子智能体的 JSON 输出")

    args = parser.parse_args()

    if args.run:
        cmd_run(args.topic)
    elif args.submit_round:
        if not args.detective_json or not args.inquisitor_json:
            parser.error("--submit-round 需要 --detective-json 和 --inquisitor-json")
        cmd_submit_round(args.topic, args.detective_json, args.inquisitor_json)
    elif args.preflight:
        cmd_preflight(args.topic)
    elif args.compile_report:
        cmd_compile_report(args.topic)


if __name__ == "__main__":
    main()
