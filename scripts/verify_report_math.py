#!/usr/bin/env python3
"""
Trade Nothing v0.9.1 — 物理数据一致性硬核阻断器
校验大模型生成的报告与底层的物理 JSON 状态文件中的数值（轮数、LFI、后验概率）是否 100% 一致。
如果有任何 AI 幻觉、猜测或粉饰修改，物理执行崩溃并熔断。
"""
import sys
import os
import re
import json

def verify_report(report_path, state_path):
    if not os.path.exists(report_path):
        print(f"[ERROR] 报告文件不存在: {report_path}", file=sys.stderr)
        return False
    if not os.path.exists(state_path):
        print(f"[ERROR] 物理状态文件不存在: {state_path}", file=sys.stderr)
        return False

    # 读取物理状态
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)
    
    if not state.get("rounds"):
        print("[ERROR] 物理状态文件中无 rounds 数据！", file=sys.stderr)
        return False
        
    last_round = state["rounds"][-1]
    true_round = len(state["rounds"])
    true_lfi = last_round["lfi"]
    # 状态文件里的 posterior 可能是 0-100 的百分比
    true_posterior = state.get("posterior", last_round.get("posterior", 50.0))

    # 读取报告内容
    with open(report_path, "r", encoding="utf-8") as f:
        report_content = f.read()

    # 正则提取 LFI
    lfi_match = re.search(r"LFI 终值:\s*([0-9\.]+)", report_content)
    if not lfi_match:
        # 兼容 yaml frontmatter 格式
        lfi_match = re.search(r"lfi_final:\s*([0-9\.]+)", report_content)

    # 正则提取轮数
    round_match = re.search(r"经过\s*([0-9]+)\s*轮", report_content)
    if not round_match:
        round_match = re.search(r"rounds:\s*([0-9]+)", report_content)

    # 正则提取后验概率
    post_match = re.search(r"后验概率:\s*([0-9\.]+)", report_content)
    if not post_match:
        post_match = re.search(r"posterior:\s*([0-9\.]+)", report_content)

    if not lfi_match or not round_match or not post_match:
        print("[ERROR] 报告中缺少必要的数学指标占位符或数值（LFI/Rounds/Posterior）！", file=sys.stderr)
        # 打印部分提取到的信息以辅助排查
        print(f"提取状态: lfi_found={bool(lfi_match)}, round_found={bool(round_match)}, post_found={bool(post_match)}", file=sys.stderr)
        return False

    report_lfi = float(lfi_match.group(1))
    report_round = int(round_match.group(1))
    report_posterior = float(post_match.group(1))

    # 核验数据
    lfi_err = abs(report_lfi - true_lfi)
    post_err = abs(report_posterior - true_posterior)

    print("=========================================")
    print("🧪 Trade Nothing — 物理数据一致性硬核对")
    print("=========================================")
    print(f"指标\t物理引擎真实值\t报告生成值\t误差")
    print(f"轮数\t{true_round}\t\t{report_round}\t\t{abs(true_round - report_round)}")
    print(f"LFI\t{true_lfi:.4f}\t\t{report_lfi:.4f}\t\t{lfi_err:.4f}")
    print(f"后验%\t{true_posterior:.2f}%\t\t{report_posterior:.2f}%\t\t{post_err:.4f}")
    print("=========================================")

    if true_round != report_round:
        print("[CRITICAL ERROR] 🔴 轮数不一致！大模型擅自伪造了推演轮数！", file=sys.stderr)
        return False

    if lfi_err > 0.01:
        print("[CRITICAL ERROR] 🔴 LFI 数值偏差过大 (>0.01)！大模型擅自伪造或修改了 LFI 终值！", file=sys.stderr)
        return False

    if post_err > 0.1:
        print("[CRITICAL ERROR] 🔴 贝叶斯后验概率偏差过大 (>0.1%)！大模型擅自修改了期望值！", file=sys.stderr)
        return False

    print("✅ 一致性硬核对通过！数据 100% 物理真实，无 AI 幻觉和粉饰。")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 verify_report_math.py <report_path> <state_path>")
        sys.exit(1)
    
    success = verify_report(sys.argv[1], sys.argv[2])
    if not success:
        sys.exit(2)
