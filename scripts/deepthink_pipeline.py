#!/usr/bin/env python3
"""
Trade Nothing v7.0 — DeepThink Pipeline Orchestration Helper

Automates:
1. Dynamic prior active memory extraction and injection (with semantic concept aliasing).
2. Topic slugification for physical state and folder isolation.
3. Harvesting unresolved attacks → local Issues + optional OS reminders.
4. Generating next-round sub-agent prompts based on debate state.
5. Maintaining a structured JSON Research Index database.
"""

import os
import re
import sys
import json
import argparse
import subprocess
from datetime import datetime, timedelta

# Import shared utilities
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import (
    generate_topic_slug, get_skill_dir, get_scratch_dir,
    get_evolution_path, get_state_dir, load_json_safe, save_json,
    send_notification
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Concept alias dictionary for semantic expansions
ALIAS_MAP = {
    "hjt": ["hjt", "异质结", "异质结电池", "薄片化", "heterojunction"],
    "solar": ["光伏", "新能源", "太阳能", "topcon", "perc", "硅片", "组件", "cell", "module", "solar"],
    "storage": ["储能", "电池柜", "锂电", "battery", "energy storage"],
    "ai": ["ai", "deepseek", "mla", "moe", "推理", "大模型", "算力", "液冷", "配电", "gpu", "llm"],
    "semiconductor": ["半导体", "芯片", "晶圆", "光刻", "wafer", "asml", "tsmc", "chip"],
    "ev": ["新能源汽车", "锂电", "固态电池", "电池", "electric vehicle"],
    "biotech": ["生物", "医药", "创新药", "基因", "biotech", "pharma"],
    "crypto": ["加密", "比特币", "以太坊", "bitcoin", "ethereum", "crypto", "web3"],
}


def clean_matching_keywords(text: str) -> list:
    """Extract clean keywords with semantic expansion for matching."""
    words = re.findall(r"[\u4e00-\u9fa5\w]+", text.lower())
    stopwords = {"研究", "分析", "破产", "重整", "东方", "的", "关于", "价格", "走势", "突破", "标的"}
    base_keywords = [w for w in words if len(w) > 1 and w not in stopwords]

    expanded = set(base_keywords)
    for kw in base_keywords:
        for key, synonyms in ALIAS_MAP.items():
            if kw in synonyms or kw == key:
                expanded.update(synonyms)

    return list(expanded)


def extract_active_memory(topic: str, evolution_path: str) -> str:
    """Extract context-aware prior constraints from Evolution.md active memory."""
    if not os.path.exists(evolution_path):
        return "⚠️ Active memory source (Evolution.md) not found. Standard initialization applied."

    with open(evolution_path, "r", encoding="utf-8") as f:
        content = f.read()

    keywords = clean_matching_keywords(topic)

    sections = {
        "User-Confirmed Facts": r"## 1\. 用户确认事实.*?\n(.*?)\n---",
        "Methodology Corrections": r"## 2\. 方法论修正.*?\n(.*?)\n---",
        "Calibration Logs": r"## 4\. 校准日志.*?\n(.*?)\n---",
        "Cognitive Bias Logs": r"## 5\. 认知偏差日志.*?\n(.*?)\n---"
    }

    extracted_memory = []

    for sec_name, pattern in sections.items():
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            continue

        sec_content = match.group(1).strip()
        lines = sec_content.split("\n")
        relevant_lines = []

        for line in lines:
            if not line.strip() or line.strip() == "（暂无条目）":
                continue

            is_relevant = any(kw in line.lower() for kw in keywords)

            if not is_relevant and sec_name in ["Methodology Corrections", "Calibration Logs"] and len(relevant_lines) < 2:
                relevant_lines.append(f"  * [General Background] {line.strip()}")
            elif is_relevant:
                relevant_lines.append(f"  * [Context-Match] {line.strip()}")

        if relevant_lines:
            extracted_memory.append(
                f"#### 🔍 {sec_name} (Active Prior Constraints):\n" + "\n".join(relevant_lines)
            )

    if not extracted_memory:
        return "ℹ️ Active memory scanned. No context-matching prior constraints found. Keep general vigilance."

    output = (
        "### 🧠 Active Memory Injection (v7.0 Prior constraints)\n"
        "Orchestrator auto-extracted historical memory and negative feedback constraints. "
        "Detective and Inquisitor sub-agents **must unconditionally obey** these:\n\n"
        + "\n\n".join(extracted_memory)
    )
    return output


def update_research_index(topic: str, slug: str, posterior: float, issues_count: int):
    """Maintain a structured index of all research sessions."""
    index_path = os.path.join(get_scratch_dir(), ".research_index.json")
    index = load_json_safe(index_path)

    index[slug] = {
        "topic": topic,
        "last_posterior": posterior,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "open_issues": issues_count
    }
    save_json(index_path, index)


def harvest_unresolved_attacks(topic: str, state_file: str, raw_attacks: str):
    """Harvest unrefuted attacks → generate local issues + optional OS reminders."""
    attacks_list = []
    posterior = 50.0
    topic_slug = generate_topic_slug(topic)

    # Resolve state file
    if not state_file:
        state_file = os.path.join(get_state_dir(), f"{topic_slug}_state.json")

    # Load attacks from raw JSON or state file
    if raw_attacks:
        try:
            attacks_list = json.loads(raw_attacks)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse raw attacks JSON: {e}", file=sys.stderr)
            return
    elif state_file and os.path.exists(state_file):
        state = load_json_safe(state_file)
        attacks_list = state.get("unrefuted_attacks", [])
        rounds = state.get("rounds", [])
        if rounds:
            posterior = rounds[-1].get("posterior", 50.0)

    # Topic-isolated scratch directory
    scratch_dir = os.path.join(get_scratch_dir(), topic_slug)
    os.makedirs(scratch_dir, exist_ok=True)

    if not attacks_list:
        print(f"[INFO] No unrefuted attacks to harvest for {topic}. Excellent logical hardness!",
              file=sys.stderr)
        update_research_index(topic, topic_slug, posterior, 0)
        print(json.dumps({"status": "success", "harvested": 0}))
        return

    harvested_count = 0
    results = []

    for idx, attack_data in enumerate(attacks_list):
        attack_text = attack_data.get("attack", "").strip()
        reason = attack_data.get("reason", "Insufficient data to refute currently").strip()

        trigger_date_str = attack_data.get("trigger_date", "")
        if not trigger_date_str:
            trigger_date = datetime.now() + timedelta(days=7)
            trigger_date_str = trigger_date.strftime("%Y-%m-%d")

        trigger_condition = attack_data.get(
            "trigger_condition",
            "Awaiting next financial report or key macro/supply-chain data update"
        ).strip()

        if not attack_text:
            continue

        # Create local issue file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        issue_filename = f"issue_{timestamp}_{idx + 1}.md"
        issue_path = os.path.join(scratch_dir, issue_filename)

        issue_content = f"""---
topic: {topic}
slug: {topic_slug}
status: ready-for-agent
target_date: {trigger_date_str}
---

# [TODO] Trade Nothing: Unresolved Attack on {topic}

## Description
This issue was dynamically harvested by the Trade Nothing v7.0 Pipeline
due to an unresolved adversarial attack.

**Attack Vector**:
{attack_text}

**Why it remained unrefuted**:
{reason}

## Trigger Condition
- **Condition**: {trigger_condition}
- **Target Date**: {trigger_date_str}

## Action Plan
When the trigger condition is met or the target date is reached,
invoke the Trade Nothing Detective sub-agent to fetch new data and resolve this logic gap.
"""
        with open(issue_path, "w", encoding="utf-8") as f:
            f.write(issue_content)

        # Optional OS notification
        send_notification(
            f"Trade Nothing: {topic}",
            f"Unresolved attack harvested: {attack_text[:50]}..."
        )

        results.append({
            "issue_file": issue_path,
            "attack": attack_text,
            "trigger_date": trigger_date_str
        })
        harvested_count += 1

    update_research_index(topic, topic_slug, posterior, harvested_count)

    final_result = {
        "status": "success",
        "topic": topic,
        "topic_slug": topic_slug,
        "harvested": harvested_count,
        "details": results
    }
    print(json.dumps(final_result, ensure_ascii=False, indent=2))


def generate_next_round_prompts(topic: str, state_file: str):
    """Generate tailored prompts for Detective and Inquisitor for the next round."""
    topic_slug = generate_topic_slug(topic)
    if not state_file:
        state_file = os.path.join(get_state_dir(), f"{topic_slug}_state.json")

    if not os.path.exists(state_file):
        print(json.dumps({
            "status": "error",
            "message": f"State file {state_file} not found. Please run --start first."
        }, ensure_ascii=False))
        return

    state = load_json_safe(state_file)
    rounds = state.get("rounds", [])

    if not rounds:
        next_round = 1
        attacks = []
        next_action = "Gather baseline market indicators and verify core bull thesis."
    else:
        last_round_data = rounds[-1]
        next_round = last_round_data.get("round", 1) + 1
        attacks = last_round_data.get("unrefuted_attacks", [])
        next_action = last_round_data.get("next_action", "Search for edge data.")

    # Format attacks into checklist
    formatted_attacks = ""
    if attacks:
        for idx, att in enumerate(attacks):
            formatted_attacks += (
                f"{idx + 1}. Attack: {att.get('attack', '')}\n"
                f"   Why unresolved: {att.get('reason', '')}\n"
                f"   Trigger: {att.get('trigger_condition', '')}\n\n"
            )
    else:
        formatted_attacks = "(No lethal unrefuted attacks from prior round. Continue hardening logic.)\n"

    detective_prompt = f"""Role: Trade Nothing v7.0 — The Detective [Round {next_round}]
Topic: {topic}

The Inquisitor raised the following lethal attack vectors against your bull thesis.
Your defense has exposed serious logical gaps.

In Round {next_round}, your core task is Rebuttal & Data Reconstruction:
You must unconditionally address each attack vector below with new, hard evidence,
supply-chain cross-validation, or macro variables.

[LETHAL GAPS TO CLOSE]:
{formatted_attacks.strip()}

[DATA FETCH HINT]:
{next_action}

Obey Active Memory negative constraints. Output must include updated [Falsifiable Evidence Chain]:
Evidence A (quantified) + Evidence B (channel-verified) → Marginal pricing change → Logic holds."""

    inquisitor_prompt = f"""Role: Trade Nothing v7.0 — The Inquisitor [Round {next_round}]
Topic: {topic}

In Round {next_round}, the Detective will attempt to patch the gaps you exposed.
Your core task is Second-tier Attack & Reflexivity Audit:
1. Audit the Detective's new data/patches — is it narrative cover or genuine evidence?
2. If prior gaps are patched, dig deeper into second-order derivative risks.
3. Surface at least 2 NEW, more lethal attack vectors.

Obey Active Memory negative constraints. Output must list [Lethal Attack Vectors]
and identify the Detective's [Cognitive Bias] this round."""

    output = {
        "status": "success",
        "topic": topic,
        "topic_slug": topic_slug,
        "next_round": next_round,
        "detective_prompt": detective_prompt.strip(),
        "inquisitor_prompt": inquisitor_prompt.strip()
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Trade Nothing v7.0 Pipeline Manager")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--extract", action="store_true",
                       help="Extract context-aware prior constraints from Evolution.md")
    group.add_argument("--harvest", action="store_true",
                       help="Harvest unrefuted attacks → issues + reminders")
    group.add_argument("--generate-prompts", action="store_true",
                       help="Generate next-round sub-agent prompts from state")

    parser.add_argument("--topic", type=str, default="", help="Research topic/target")
    parser.add_argument("--evolution-path", type=str, default="",
                        help="Path to Evolution.md (default: auto-detected)")
    parser.add_argument("--state-file", type=str, default="", help="Path to state JSON")
    parser.add_argument("--unrefuted-attacks", type=str, default="",
                        help="JSON string of unresolved attacks")

    args = parser.parse_args()
    evolution_path = args.evolution_path or get_evolution_path()

    if args.extract:
        if not args.topic:
            parser.error("--extract requires --topic")
        constraints = extract_active_memory(args.topic, evolution_path)
        print(constraints)
    elif args.harvest:
        if not args.topic:
            parser.error("--harvest requires --topic")
        harvest_unresolved_attacks(args.topic, args.state_file, args.unrefuted_attacks)
    elif args.generate_prompts:
        if not args.topic:
            parser.error("--generate-prompts requires --topic")
        generate_next_round_prompts(args.topic, args.state_file)


if __name__ == "__main__":
    main()
