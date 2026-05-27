#!/usr/bin/env python3
import subprocess
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENGINE_PATH = os.path.join(SCRIPT_DIR, "deepthink_engine.py")

# 准备第四轮的物理输入
topic = "A股半导体与国产替代算力芯片分析"
round_num = 4

# 侦探引入新论点以解决上一轮的挂起攻击
arguments = [
    "[Audit Node: 盛美上海与华海清科先进制程设备国产化率提升至60% | Proxy Data Anchor: ACM Research Q1 CN Equipment Order +85% YoY]",
    "[Audit Node: 华为海思与中芯国际先进MWW工艺扩产与C2C互联拼片良率达82% | Proxy Data Anchor: SMIC Semi-Annual Capex Disclosure L12]"
]

# 侦探发起对上一轮攻击的反驳
attacks = [
    [
        "[Audit Node: 华为海思与中芯国际先进MWW工艺扩产与C2C互联拼片良率达82% | Proxy Data Anchor: SMIC Semi-Annual Capex Disclosure L12]",
        "[Vision Audit | Target: Agent 算力编排总线生态跃迁]: 国外先进制程极限制裁与国内晶圆厂先进封装产能挤爆瓶颈"
    ]
]

# 追加本轮硬证据
evidence = [
    {"category": "Hard Proxy Data", "direction": "Bull", "strength": "Strong"},
    {"category": "Factual Disclosed", "direction": "Bull", "strength": "Strong"}
]

# 命令行调用物理引擎
cmd = [
    "python3", ENGINE_PATH,
    "--checkpoint",
    "--topic", topic,
    "--round", str(round_num),
    "--arguments-json", json.dumps(arguments),
    "--attacks-json", json.dumps(attacks),
    "--evidence-json", json.dumps(evidence),
    "--no-timer"
]

print("Executing physical simulation for Round 4...")
res = subprocess.run(cmd, capture_output=True, text=True)
if res.returncode != 0:
    print(f"Error: {res.stderr}")
    sys.exit(1)

print("Engine Output:")
print(res.stdout)
