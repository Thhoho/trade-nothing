#!/usr/bin/env python3
"""
Trade Nothing v6.0 — DeepThink Pipeline Orchestration Helper

Automates:
1. Dynamic prior active memory extraction and injection (with semantic concept aliasing).
2. Topic slugification for physical state and folder isolation.
3. Harvesting unresolved attacks and converting them to nested Local Issues & macOS Reminders.
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
REMINDERS_SCRIPT = os.path.join(os.path.expanduser("~"), ".gemini/skills/mac-reminders/scripts/manage_reminders.py")
BASE_SCRATCH_DIR = "/Users/xiaweiqi/.gemini/.scratch/trade-nothing"

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
        "### 🧠 Active Memory Injection (v6.0 Prior constraints)\n"
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
                            "title": f"🚨 [Trade Nothing v6.0] 质证逻辑漏洞预警: {topic}",
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
                    f"🚨 *[Trade Nothing v6.0] 质证逻辑漏洞预警: {topic}*\n\n"
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
This issue was dynamically harvested by the Trade Nothing v6.0 Pipeline due to an unresolved adversarial attack in Dung's graph.

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
    codes = re.findall(r"\d{6}", topic)
    symbol = codes[0] if codes else "300118"
    
    tech_keyword = "低温银浆"
    topic_lower = topic.lower()
    for category, synonyms in ALIAS_MAP.items():
        for syn in synonyms:
            if syn in topic_lower:
                tech_keyword = syn
                break

    formatted_facts = ""
    try:
        from verified_crawler import VerifiedCrawler
        crawler = VerifiedCrawler()
        micro_facts = crawler.synthesize_micro_facts(symbol, tech_keyword)
        
        if micro_facts:
            formatted_facts += "【1. 公开招标与中标公示 (Public Bids)】:\n"
            for t in micro_facts.get("micro_order_tenders", []):
                formatted_facts += f"  * {t['title']} | 中标参数: {t['snippet']} ({t['date']})\n"
            
            c = micro_facts.get("raw_material_price_track", {})
            formatted_facts += f"\n【2. 供应链大宗原料高频价格 (Raw Material Price)】:\n"
            formatted_facts += f"  * 辅料/材料: {c.get('material')} | 均价: {c.get('price')} {c.get('unit')} | 周变动: {c.get('trend_wow')} (来源: {c.get('source')})\n"
            
            cust = micro_facts.get("customs_export_validation", {})
            formatted_facts += f"\n【3. 海关进出口出货核验 (Port & HS Code)】:\n"
            formatted_facts += f"  * 海关HS编码: {cust.get('hs_code')} | 宁波海关月出货值: {cust.get('export_value_millions_usd')}百万美元 | 换算均价: {cust.get('implied_price_per_watt')} USD/W | 月环比: {cust.get('change_mom')}\n"
            
            formatted_facts += f"\n【4. 买方草根调研与专家纪要泄露 (Expert Minutes)】:\n"
            for e in micro_facts.get("expert_minutes_leak", []):
                formatted_facts += f"  * {e['title']}: {e['snippet']} ({e['date']})\n"
    except Exception as ex:
        formatted_facts = f"⚠️ [CRAWLER ERROR] Micro supply chain intelligence temporarily offline: {ex}\n"

    # Determine the topic mode
    topic_lower = topic.lower()
    cyclical_keywords = ["solar", "光伏", "新能源", "hjt", "电池", "锂电", "topcon", "储能", "电池柜", "300118", "宁德时代", "隆基"]
    mode = "audit"
    for kw in cyclical_keywords:
        if kw in topic_lower:
            mode = "audit"
            break
    else:
        mode = "vision"

    if mode == "audit":
        mode_instruction = (
            "⚠️⚠️⚠️【当前模态：审计硬化模态 (Audit-Hardened Mode)】⚠️⚠️⚠️\n"
            "本分析标的属于传统周期或重资产制造股。法官运行在极其严苛的审计模式下！\n"
            "所有提出的看多主张被绝对禁止空洞的定性描述或 speculative 推演。你所提交的每一个论点，"
            "必须使用以下形式确立为 `[Audit Node]` 且必须标注 `[Proxy Data Anchor: ...]` 物理证据！\n"
            "格式要求：`[Audit Node: <主张> | Proxy Data Anchor: <具体三方物理出货数据/招标/报价详情>]`\n"
            "注意：任何未加锚点或试图使用 Vision/Speculative 属性的节点在 Dung 图谱中将直接被法官强制击毁（攻击致死）！"
        )
        inquisitor_mode_instruction = (
            "⚠️⚠️⚠️【当前模态：审计硬化模态 (Audit-Hardened Mode)】⚠️⚠️⚠️\n"
            "你的任务是执行【最无情的物理数据审计】。\n"
            "侦探的所有论点必须拥有极高纯度的海关、原材料报价三方印证。你必须使用 `[Audit Attack]` "
            "攻击任何统计口径偏差、多重定货水分、辅料涨价吞噬利润或 ASP 下降风险。\n"
            "格式要求：`[Audit Attack | Target: <被攻击侦探节点>]: <具体逻辑攻击内容>`"
        )
    else:
        mode_instruction = (
            "✨✨✨【当前模态：主权远见模态 (Sovereign Vision Mode)】✨✨✨\n"
            "本分析标的属于高成长、颠覆性创新的科技/AI/期权资产。法官已解锁远见释放权限！\n"
            "你除了需要使用 `[Audit Node]` 夯实下行安全地板外，更应当大胆使用 `[Vision Node]` 勾勒上行空间，"
            "阐释在宏观范式变化、技术爆发与反身性拐点处的早期信号！\n"
            "三种节点格式要求：\n"
            "1. `[Audit Node: <安全主张> | Proxy Data Anchor: <高频三方微观数据锚点>]` — 地板审计\n"
            "2. `[Vision Node: <前瞻主张> | Catalyst/Optionality: <催化事件/非线性期权逻辑>]` — 天花板远见\n"
            "3. `[Narrative Node: <叙事主张> | Sentiment Source: <Snowball/Futu/专家调研>]` — 预期差与反身性度量"
        )
        inquisitor_mode_instruction = (
            "✨✨✨【当前模态：主权远见模态 (Sovereign Vision Mode)】✨✨✨\n"
            "侦探除了夯实地板，还提出了具有颠覆性期权可能性的 `[Vision Node]` 前瞻命题。\n"
            "你的任务不是教条地喊“没有当季海关出货数据验证”，而是发起具有产业反思高度的【二级逻辑质询与反身性打击（Vision Audit）】！\n"
            "你必须站在 6 个月后跌 70% 的逆向死亡视角，攻击其：物理/工程学不可能边界（如热力学极限、芯片散热瓶颈）、高研发带来的资金链断裂、扩产周期陷阱或反身性高估风险。\n"
            "攻击格式：\n"
            "- 对于侦探的 `[Audit Node]` 物理证据，使用 `[Audit Attack | Target: <节点>]: <攻击>`\n"
            "- 对于侦探的 `[Vision Node]` 远见主张，使用 `[Vision Audit | Target: <节点>]: <逻辑漏洞/反身性陷阱/物理极限>`"
        )

    # Detective next round prompt
    detective_prompt = f"""Role: Trade Nothing v9.0 — The Detective (侦探智能体) [Round {next_round}]
Topic: {topic}

在上一轮辩论中，审问者（Inquisitor）针对你的 Bull Thesis 提出了致命攻击向量（Lethal Attack Vectors）。你目前的逻辑防线已经暴露出严重的漏洞。

在这一轮（Round {next_round}）中，你的核心任务是进行【定向反驳与物理数据重建】（Rebuttal & Data Reconstruction）：
你必须针对以下每一个攻击向量，寻找新的、确凿的产业链交叉验证或宏观变量，打补丁或推翻审问者的质疑：

【你需要正面击退的致命漏洞】:
{formatted_attacks.strip()}

【下一轮数据获取提示】:
{next_action}

{mode_instruction}

🚨🚨🚨【海关与微观供应链硬证据库（CRITICAL INPUT）】🚨🚨🚨:
你本轮的所有辩护、看多逻辑及出货推演，必须严格锚定在以下【海关与微观供应链硬证据库】中。严禁进行任何无微观硬数据支撑的定性吹水或线性外推！
{formatted_facts.strip()}

🚨🚨🚨【非共识与数据强迫护栏约束（CRITICAL）】🚨🚨🚨:
1. **平庸共识禁区**：你被绝对禁止使用或复述以下任何平庸共识（Clichés），否则法官将在Jaccard语义检测中直接作废并打回你的论点：
{formatted_consensus}

你的输出格式必须包含更新后的 [核心可证伪证据链]：
Claim_X (物理代理数据支撑) + 证据B (三方渠道校验) → 边际定价变化 → 逻辑硬化成立。"""

    # Inquisitor next round prompt
    inquisitor_prompt = f"""Role: Trade Nothing v9.0 — The Inquisitor (审问者智能体) [Round {next_round}]
Topic: {topic}

在这一轮（Round {next_round}）中，侦探（Detective）将针对你上一轮提出的漏洞进行定向辩护。你的核心任务是执行【二级漏洞审计与反身性打击】。

💀💀💀【逆向死亡路径前提（Premortem Axiom）】💀💀💀:
你本轮的攻击发起必须无条件服从【逆向死亡路径公理】：
**“假设当前时间点向后推移 6 个月，该标的因某项微观物理/财务/供应链故障爆雷，导致股价暴跌了 70%。”**
你必须以此为既定事实，结合以下【海关与微观供应链硬证据库】，反向推理并审计侦探所引用的“订单大增”、“出货顺畅”是否存在虚假逻辑：
{formatted_facts.strip()}

{inquisitor_mode_instruction}

🚨🚨🚨【平庸共识禁区约束】🚨🚨🚨:
你同样被绝对禁止使用以下任何平庸的、人云亦云的看空逻辑：
{formatted_consensus}
你必须挖出市场一致预期（Consensus）之外的隐蔽致命漏洞。

请清晰列出你的 [Lethal Attack Vectors] 并指出侦探本轮犯下的 [Cognitive Bias]（认知偏差）。"""

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
    parser = argparse.ArgumentParser(description="Trade Nothing v6.0 Pipeline Manager")
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
