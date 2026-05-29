#!/usr/bin/env python3
"""
Trade Nothing v0.9.4 — DeepThink Pipeline Orchestration Helper

Automates:
1. Dynamic prior active memory extraction and injection (with semantic concept aliasing).
2. Topic slugification for physical state and folder isolation.
3. Harvesting unresolved attacks and converting them to nested Local Issues & OS Reminders.
4. Maintaining a structured JSON Research Index database.
5. Dynamically generating academic-grade, edge-forcing subagent prompts (Forbidden Consensus, Proxy Anchoring, and Premortem Axiom).
"""

import os
import re
import sys
import json
import argparse
import subprocess
import urllib.request
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
DEFAULT_EVOLUTION_PATH = os.path.join(SKILL_DIR, "Methodology_Evolution_Backup.md")

# Cross-platform path resolution (no hardcoded macOS paths)
try:
    from utils import get_scratch_dir
    BASE_SCRATCH_DIR = os.path.join(get_scratch_dir(), "trade-nothing")
except ImportError:
    BASE_SCRATCH_DIR = os.path.join(os.path.expanduser("~"), ".trade-nothing/scratch")

# Optional reminders script - auto-detected, not hardcoded
REMINDERS_SCRIPT = os.environ.get(
    "TRADE_NOTHING_REMINDERS_SCRIPT",
    os.path.join(os.path.expanduser("~"), ".gemini/skills/mac-reminders/scripts/manage_reminders.py")
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

# Static standard clichés pool to inject as "Forbidden Consensus" if no dynamic web consensus is passed
CLICHE_POOL = {
    "hjt": [
        "异质结转换效率高但成本依然偏高",
        "低温银浆耗量大导致生产成本不占优势",
        "双面率高且温度系数好",
        "HJT是下一代技术但需要等待产业链成熟",
        "核心壁垒在于硅片薄片化和浆料降本"
    ],
    "solar": [
        "光伏行业产能过剩导致组件价格内卷严重",
        "组件厂利润受到产业链上下游双向挤压",
        "海外关税壁垒阻碍了光伏出口利润",
        "核心竞争力在于一体化产能的成本控制",
        "分布式光伏装机量见顶，地面电站等政策落地"
    ],
    "ai": [
        "大模型竞争激烈，推理成本是关键瓶颈",
        "算力芯片短缺限制了训练和推理速度",
        "核心在于寻找AI killer app应用落地",
        "模型蒸馏和小模型私有化部署是趋势",
        "数据瓶颈和优质中文语料匮乏限制了天花板"
    ],
    "semiconductor": [
        "半导体行业正处于库存去化和周期底部",
        "先进光刻设备受限导致工艺节点突破缓慢",
        "晶圆代工产能利用率下滑压制利润率",
        "国产化替代是核心逻辑但中高端替代仍需时间",
        "AI算力芯片需求暴增拉动了CoWoS先进封装"
    ],
    "general": [
        "行业竞争激烈，龙头企业优势明显",
        "受制于宏观流动性收紧，板块估值承压",
        "公司在进行技术转型，短期研发费用拖累业绩",
        "行业需求增速放缓，进入存量博弈阶段",
        "核心在于成本控制和渠道建设"
    ]
}


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


def update_research_index(topic: str, slug: str, posterior: float, issues_count: int):
    """Maintain a structured index of all research sessions in a single JSON database (Process-Safe)"""
    index_path = os.path.join(SCRIPT_DIR, ".research_index.json")
    index = {}
    
    from utils import CrossPlatformFileLock
    lock = CrossPlatformFileLock(index_path)
    
    # Process-safe read-write cycle
    try:
        with lock:
            # Create empty file if not exists
            if not os.path.exists(index_path):
                with open(index_path, "w", encoding="utf-8") as f:
                    json.dump({}, f)
                    
            with open(index_path, "r", encoding="utf-8") as f:
                try:
                    index = json.load(f)
                except Exception:
                    index = {}
                    
            index[slug] = {
                "topic": topic,
                "last_posterior": posterior,
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "open_issues": issues_count
            }
            
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to write research index atomically: {e}", file=sys.stderr)


def send_webhook_notification(webhook_url: str, topic: str, attack_text: str, reason: str, trigger_date_str: str) -> bool:
    """Post logical vulnerabilities directly to Slack/Feishu webhooks via urllib (zero-dependency)"""
    if not webhook_url:
        return False
        
    try:
        is_feishu = "feishu.cn" in webhook_url or "larksuite.com" in webhook_url
        
        if is_feishu:
            payload = {
                "msg_type": "post",
                "content": {
                    "post": {
                        "zh_cn": {
                            "title": f"🚨 [Trade Nothing v0.9.4] 质证逻辑漏洞预警: {topic}",
                            "content": [
                                [
                                    {"tag": "text", "text": "未反驳致命攻击向量:\n"},
                                    {"tag": "text", "text": f"{attack_text}\n\n", "style": ["bold"]}
                                ],
                                [
                                    {"tag": "text", "text": "未能推翻归因:\n"},
                                    {"tag": "text", "text": f"{reason}\n\n"}
                                ],
                                [
                                    {"tag": "text", "text": f"触发监控时间: {trigger_date_str}\n"}
                                ]
                            ]
                        }
                    }
                }
            }
        else:
            payload = {
                "text": (
                    f"🚨 *[Trade Nothing v0.9.4] 质证逻辑漏洞预警: {topic}*\n\n"
                    f"*未反驳致命攻击向量*:\n> {attack_text}\n\n"
                    f"*未能推翻归因*:\n> {reason}\n\n"
                    f"*触发监控时间*: `{trigger_date_str}`\n"
                    f"---"
                )
            }
            
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except Exception as e:
        print(f"[WARN] Webhook notification failed: {e}", file=sys.stderr)
        return False


def harvest_unresolved_attacks(topic: str, state_file: str, raw_attacks: str):
    """Harvest unrefuted attacks, generate nested Local Issues & schedule macOS reminders/webhooks"""
    attacks_list = []
    posterior = 50.0
    topic_slug = generate_topic_slug(topic)
    
    if not state_file:
        state_dir = os.path.join(SCRIPT_DIR, ".state")
        state_file = os.path.join(state_dir, f"{topic_slug}_state.json")

    if raw_attacks:
        try:
            attacks_list = json.loads(raw_attacks)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse raw attacks JSON: {e}", file=sys.stderr)
            return

    elif state_file and os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                attacks_list = state.get("unrefuted_attacks", [])
                rounds = state.get("rounds", [])
                if rounds:
                    posterior = rounds[-1].get("posterior", 50.0)
        except Exception as e:
            print(f"[ERROR] Failed to load state file {state_file}: {e}", file=sys.stderr)
            return

    scratch_dir = os.path.join(BASE_SCRATCH_DIR, topic_slug)
    os.makedirs(scratch_dir, exist_ok=True)

    if not attacks_list:
        print(f"[INFO] No unrefuted attacks to harvest for {topic}. Excellent logical hardness reached!", file=sys.stderr)
        update_research_index(topic, topic_slug, posterior, 0)
        print(json.dumps({"status": "success", "harvested": 0}))
        return

    harvested_count = 0
    results = []

    for idx, attack_data in enumerate(attacks_list):
        attack_text = attack_data.get("attack", "").strip()
        reason = attack_data.get("reason", "缺乏充足的客观代理数据支撑，暂时无法推翻").strip()
        
        trigger_date_str = attack_data.get("trigger_date", "")
        if not trigger_date_str:
            trigger_date = datetime.now() + timedelta(days=7)
            trigger_date_str = trigger_date.strftime("%Y-%m-%d")
        
        trigger_condition = attack_data.get("trigger_condition", "等待新一期高频微观物理/财务代理数据公开以重新质证").strip()

        if not attack_text:
            continue

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
This issue was dynamically harvested by the Trade Nothing v0.9.4 Pipeline due to an unresolved adversarial attack in Dung's graph.

**Attack Vector**:
{attack_text}

**Why it remained undefeated**:
{reason}

## Trigger Condition
- **Condition**: {trigger_condition}
- **Target Date**: {trigger_date_str}

## Action Plan
When the trigger condition is met or the target date is reached, invoke the Trade Nothing Detective subagent to fetch new proxy data and resolve this logic gap.
"""

        with open(issue_path, "w", encoding="utf-8") as f:
            f.write(issue_content)

        reminder_scheduled = False
        if os.path.exists(REMINDERS_SCRIPT):
            due_time_str = f"{trigger_date_str} 09:00:00"
            reminder_name = f"Trade Nothing: Resolve attack on {topic} ({attack_text[:30]}...)"
            
            cmd = [
                "python3",
                REMINDERS_SCRIPT,
                "add",
                "--name", reminder_name,
                "--due", due_time_str,
                "--list", "工作待办"
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    reminder_scheduled = True
                else:
                    print(f"[WARN] Reminder script returned non-zero: {result.stderr.strip()}", file=sys.stderr)
            except Exception as e:
                print(f"[WARN] Failed to invoke macOS Reminders script: {e}", file=sys.stderr)

        # Webhook Notification Integration
        webhook_url = os.environ.get("TRADE_NOTHING_WEBHOOK_URL", "")
        webhook_sent = False
        if webhook_url:
            webhook_sent = send_webhook_notification(webhook_url, topic, attack_text, reason, trigger_date_str)

        results.append({
            "issue_file": issue_path,
            "attack": attack_text,
            "reminder_scheduled": reminder_scheduled,
            "webhook_sent": webhook_sent,
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


def extract_forbidden_consensus_list(topic: str) -> list:
    """Identify the exact category of cliches from the topic name to inject as forbidden zones"""
    topic_lower = topic.lower()
    cliches = set(CLICHE_POOL["general"])
    
    matched_any = False
    for category, synonyms in ALIAS_MAP.items():
        for syn in synonyms:
            if syn in topic_lower:
                cliches.update(CLICHE_POOL.get(category, []))
                matched_any = True
                break
                
    return list(cliches)


def generate_next_round_prompts(topic: str, state_file: str):
    """Dynamically generate academic-grade, edge-forcing prompts for Detective and Inquisitor"""
    topic_slug = generate_topic_slug(topic)
    if not state_file:
        state_dir = os.path.join(SCRIPT_DIR, ".state")
        state_file = os.path.join(state_dir, f"{topic_slug}_state.json")

    if not os.path.exists(state_file):
        print(json.dumps({
            "status": "error",
            "message": f"State file {state_file} not found. Please run --start first."
        }, ensure_ascii=False))
        return

    try:
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception as e:
        print(json.dumps({
            "status": "error",
            "message": f"Failed to load state: {str(e)}"
        }, ensure_ascii=False))
        return

    rounds = state.get("rounds", [])
    if not rounds:
        next_round = 1
        attacks = []
        next_action = "获取底层边缘高频物理数据，确立非共识基准命题。"
    else:
        last_round_data = rounds[-1]
        next_round = last_round_data.get("round", 1) + 1
        # Convert engine structured attack format to text
        engine_attacks = state.get("unrefuted_attacks", [])
        attacks = [{"attack": a.get("attack", ""), "reason": a.get("reason", "")} for a in engine_attacks]
        next_action = last_round_data.get("next_action", "寻找更深层的供应链交叉佐证。")

    # Format attacks
    formatted_attacks = ""
    if attacks:
        for idx, att in enumerate(attacks):
            formatted_attacks += f"{idx + 1}. 攻击点: {att.get('attack', '')}\n   为什么未解决: {att.get('reason', '')}\n\n"
    else:
        formatted_attacks = "（上一轮暂无未反驳的致命漏洞。继续加固图谱逻辑，寻找深层物理死角。）\n"

    # Inject Forbidden Consensus Clichés
    forbidden_consensus = extract_forbidden_consensus_list(topic)
    formatted_consensus = "\n".join(f"  * {c}" for c in forbidden_consensus[:6])

    # ─── MICRO SUPPLY CHAIN FACT CRAWLING & INJECTION ───
    # Dynamic symbol extraction — NO hardcoded defaults
    codes = re.findall(r"\d{6}", topic)
    symbol = codes[0] if codes else ""

    # Dynamic tech keyword extraction from topic via ALIAS_MAP
    tech_keyword = ""
    topic_lower = topic.lower()
    for category, synonyms in ALIAS_MAP.items():
        for syn in synonyms:
            if syn in topic_lower:
                tech_keyword = syn
                break
        if tech_keyword:
            break

    # If no specific keyword matched, use a cleaned topic fragment
    if not tech_keyword:
        cjk_words = re.findall(r'[\u4e00-\u9fa5]{2,}', topic)
        tech_keyword = cjk_words[0] if cjk_words else topic[:10]

    formatted_facts = ""
    has_any_data = False
    try:
        from verified_crawler import VerifiedCrawler
        crawler = VerifiedCrawler()
        crawl_symbol = symbol if symbol else tech_keyword
        micro_facts = crawler.synthesize_micro_facts(crawl_symbol, tech_keyword)
        availability = micro_facts.get("data_availability", {})

        # Only inject sections where REAL data was obtained
        if availability.get("tenders"):
            has_any_data = True
            formatted_facts += "【1. 公开招标与中标公示 (Public Bids)】:\n"
            for t in micro_facts.get("micro_order_tenders", []):
                formatted_facts += f"  * {t['title']} | {t['snippet']} ({t['date']})\n"

        if availability.get("commodity_price"):
            has_any_data = True
            c = micro_facts.get("raw_material_price_track", {})
            formatted_facts += f"\n【2. 供应链大宗原料高频价格 (Raw Material Price)】:\n"
            formatted_facts += f"  * 材料: {c.get('material')} | 均价: {c.get('price')} {c.get('unit')} | 周变动: {c.get('trend_wow')} (来源: {c.get('source')})\n"

        if availability.get("customs"):
            has_any_data = True
            cust = micro_facts.get("customs_export_validation", {})
            formatted_facts += f"\n【3. 海关进出口出货核验 (Port & HS Code)】:\n"
            formatted_facts += f"  * HS编码: {cust.get('hs_code')} | 月出货值: {cust.get('export_value_millions_usd')}百万美元 | 月环比: {cust.get('change_mom')}\n"

        if availability.get("expert_minutes"):
            has_any_data = True
            formatted_facts += f"\n【4. 买方草根调研与专家纪要 (Expert Minutes)】:\n"
            for e in micro_facts.get("expert_minutes_leak", []):
                formatted_facts += f"  * {e['title']}: {e['snippet']} ({e['date']})\n"
    except Exception as ex:
        formatted_facts = ""
        print(f"[PIPELINE WARN] Crawler offline: {ex}", file=sys.stderr)

    # Determine the topic mode
    topic_lower = topic.lower()
    cyclical_keywords = ["solar", "光伏", "新能源", "hjt", "电池", "锂电", "topcon", "储能", "电池柜", "宁德时代", "隆基"]
    mode = "audit"
    for kw in cyclical_keywords:
        if kw in topic_lower:
            mode = "audit"
            break
    else:
        mode = "vision"

    if mode == "audit":
        mode_instruction = (
            "【当前模态：审计硬化模态 (Audit-Hardened Mode)】\n"
            "本标的属于周期或重资产制造类。所有主张必须使用 [Audit Node] 格式并标注 [Proxy Data Anchor]。\n"
            "格式：[Audit Node: <主张> | Proxy Data Anchor: <具体三方物理出货数据/招标/报价>]"
        )
        inquisitor_mode_instruction = (
            "【当前模态：审计硬化模态 (Audit-Hardened Mode)】\n"
            "执行物理数据审计。使用 [Audit Attack | Target: <节点>]: <攻击内容> 攻击统计口径偏差、多重定货水分等。"
        )
    else:
        mode_instruction = (
            "【当前模态：主权远见模态 (Sovereign Vision Mode)】\n"
            "本标的属于高成长/颠覆创新类。三种节点格式：\n"
            "1. [Audit Node: <主张> | Proxy Data Anchor: <数据锚点>] — 安全边际审计\n"
            "2. [Vision Node: <主张> | Catalyst: <催化事件>] — 前瞻远见\n"
            "3. [Narrative Node: <主张> | Sentiment Source: <来源>] — 预期差度量"
        )
        inquisitor_mode_instruction = (
            "【当前模态：主权远见模态 (Sovereign Vision Mode)】\n"
            "侦探提出了 Vision Node 前瞻命题。发起二级逻辑质询：\n"
            "- [Audit Attack | Target: <节点>]: <攻击> — 攻击物理证据\n"
            "- [Vision Audit | Target: <节点>]: <逻辑漏洞/物理极限> — 攻击远见主张"
        )

    # Build supply chain evidence block (only if real data exists)
    if has_any_data and formatted_facts.strip():
        facts_block = (
            "微观供应链实时证据库:\n"
            + formatted_facts.strip()
        )
    else:
        facts_block = (
            "微观供应链数据暂不可用。你必须通过自行搜索获取相关数据。\n"
            "严禁在缺乏数据的情况下编造具体数字！"
        )

    # Detective next round prompt
    detective_prompt = f"""Role: Trade Nothing v0.9.4 - The Detective [Round {next_round}]
Topic: {topic}

## 核心任务
审问者在上一轮发起了致命攻击。逐一正面回应，用新的确凿数据反驳或补强：

{formatted_attacks.strip()}

## 数据线索
{next_action}

## 模态
{mode_instruction}

## 三问强制结构 (每轮必答)
1. 市场一致预期是什么？ - 一句话概括当前市场主流共识。
2. 你的 Variant Perception 是什么？ - 你看到了什么市场没有定价的信息？必须具体。
3. 数据证据是什么？ - 支撑你 Variant Perception 的具体数据（来源、数字、时间）。

{facts_block}

## 硬约束 (违反即判负)
1. 平庸共识禁区 - 以下论点被禁止：
{formatted_consensus}
2. 反废话约束 - 严禁使用模糊措辞如"值得关注""有望实现""具有一定""或许"。每个论点必须可证伪、有具体数字、有明确时间窗口。
3. 强制新增 - 本轮必须引入至少一个前一轮未出现的新数据源或新逻辑维度。

## 输出格式
JSON: evidence_chain, rebuttals, variant_perception。"""

    # Inquisitor next round prompt
    inquisitor_prompt = f"""Role: Trade Nothing v0.9.4 - The Inquisitor [Round {next_round}]
Topic: {topic}

## 核心任务
侦探将针对你上一轮的攻击进行辩护。发起更深层的二级审计。

## 逆向死亡路径公理 (Premortem Axiom)
假定：从现在起 6 个月后，该标的因某项故障爆雷，股价暴跌 70%。
以此为既定事实：
1. 构造一条具体死亡路径（触发事件 + 传导链条 + 崩塌机制），附带具体时间节点和价格目标
2. 审计侦探引用的每一个利好数据是否存在统计口径偏差、幸存者偏差或时间错配

{facts_block}

## 模态
{inquisitor_mode_instruction}

## 硬约束 (违反即判负)
1. 平庸共识禁区 - 以下看空逻辑被禁止：
{formatted_consensus}
2. 反废话约束 - 每个攻击必须指明：具体攻击目标节点、具体数字反驳依据、具体失效触发条件（价格/时间/事件）。
3. 强制新增 - 本轮必须引入至少一个前一轮未使用的攻击维度。

## 输出格式
JSON: lethal_attack_vectors, cognitive_biases_detected, death_path。"""


    output = {
        "status": "success",
        "topic": topic,
        "topic_slug": topic_slug,
        "next_round": next_round,
        "forbidden_consensus": forbidden_consensus,
        "detective_prompt": detective_prompt.strip(),
        "inquisitor_prompt": inquisitor_prompt.strip()
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))



def main():
    parser = argparse.ArgumentParser(description="Trade Nothing v0.9.4 Pipeline Manager")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--extract", action="store_true", help="Extract context-aware prior constraints from Evolution.md")
    group.add_argument("--harvest", action="store_true", help="Harvest unrefuted attacks and convert to issues/reminders")
    group.add_argument("--generate-prompts", action="store_true", help="Generate prompts for the next round of debate")

    parser.add_argument("--topic", type=str, default="", help="The research topic/target")
    parser.add_argument("--evolution-path", type=str, default=DEFAULT_EVOLUTION_PATH, help="Path to Evolution.md")
    parser.add_argument("--state-file", type=str, default="", help="Path to state json file")
    parser.add_argument("--unrefuted-attacks", type=str, default="", help="JSON string representing unresolved attacks")

    args = parser.parse_args()

    if args.extract:
        if not args.topic:
            parser.error("--extract requires --topic")
        constraints = extract_active_memory(args.topic, args.evolution_path)
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
