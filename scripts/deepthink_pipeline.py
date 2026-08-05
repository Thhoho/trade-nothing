#!/usr/bin/env python3
"""
Trade Nothing — Evolution.md memory extraction

Provides the negative-prior injection used by `-deepthink2`:
1. Dynamic prior active memory extraction (with semantic concept aliasing).
2. Topic slugification for physical state and folder isolation.

The legacy v1 attack-harvesting, research-index, and prompt-generation helpers
were removed with the `-deepthink` pipeline; they read v1-only state files.
"""

import os
import re
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)

# Cross-platform path resolution (no hardcoded macOS paths)
try:
    from utils import get_scratch_dir, get_evolution_path
    DEFAULT_EVOLUTION_PATH = get_evolution_path()
except ImportError:
    DEFAULT_EVOLUTION_PATH = os.path.expanduser(
        "~/trade-nothing-vault/Methodology/Evolution.md"
    )

# Concept alias dictionary for semantic expansions
ALIAS_MAP = {
    "hjt": ["hjt", "异质结", "异质结电池", "薄片化", "东方日升", "300118", "日升"],
    "solar": ["光伏", "新能源", "太阳能", "topcon", "perc", "硅片", "组件", "cell", "module"],
    "storage": ["储能", "双一力", "电池柜", "锂电", "c&i", "shuangyili"],
    "ai": ["ai", "deepseek", "mla", "moe", "推理", "大模型", "算力", "液冷", "配电", "gpu"],
    "semiconductor": ["半导体", "芯片", "晶圆", "光刻", "wafer", "硅片", "asml", "tsmc"],
    "ev": ["新能源汽车", "锂电", "固态电池", "电池", "宁德时代", "比亚迪"]
}

def clean_matching_keywords(text: str) -> list:
    """Extract clean keywords from text/topic for semantic matching"""
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
    """Extract context-aware prior constraints from Evolution.md"""
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

            is_relevant = False
            for kw in keywords:
                if kw in line.lower():
                    is_relevant = True
                    break

            if not is_relevant and sec_name in ["Methodology Corrections", "Calibration Logs"] and len(relevant_lines) < 2:
                relevant_lines.append(f"  * [General Background] {line.strip()}")
            elif is_relevant:
                relevant_lines.append(f"  * [Context-Match] {line.strip()}")

        if relevant_lines:
            extracted_memory.append(f"#### 🔍 {sec_name} (Active Prior Constraints):\n" + "\n".join(relevant_lines))

    if not extracted_memory:
        return "ℹ️ Active memory scanned. No context-matching prior constraints found. Keep general vigilance."

    output = (
        "### Active Memory Injection (Prior constraints)\n"
        "主 Agent 根据当前标的自动提取的历史记忆和负反馈约束。侦探与审问者子智能体在进行分析时**必须无条件遵守**：\n\n"
        + "\n\n".join(extracted_memory)
    )
    return output



def main():
    parser = argparse.ArgumentParser(
        description="Trade Nothing memory extraction (Evolution.md negative priors)"
    )
    parser.add_argument("--extract", action="store_true", required=True,
                        help="Extract context-aware prior constraints from Evolution.md")
    parser.add_argument("--topic", type=str, default="", help="The research topic/target")
    parser.add_argument("--evolution-path", type=str, default=DEFAULT_EVOLUTION_PATH,
                        help="Path to Evolution.md")

    args = parser.parse_args()

    if args.extract:
        if not args.topic:
            parser.error("--extract requires --topic")
        print(extract_active_memory(args.topic, args.evolution_path))


if __name__ == "__main__":
    main()
