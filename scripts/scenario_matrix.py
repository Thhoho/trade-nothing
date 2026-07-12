#!/usr/bin/env python3
"""
Trade Nothing v0.9 — Scenario Matrix Generator (情景矩阵生成器)

Transforms qualitative Bull/Bear analysis into structured probability-weighted
scenario matrices. Enforces probability sum = 100% and computes expected returns
with Half-Kelly position sizing.

Usage:
  python3 scenario_matrix.py --topic "HJT Solar" --interactive
  python3 scenario_matrix.py --from-json scenarios.json
  python3 scenario_matrix.py --demo
"""

import argparse
import json
import sys
from datetime import datetime


class ScenarioMatrix:
    """Structured scenario matrix engine with Kelly sizing."""

    def __init__(self, topic: str, afi: float = 0.0, es: float = 1.0, egi: float = 0.0, max_egi: float = 10.0, company_cash_growth: bool = False):
        self.topic = topic
        self.scenarios = []
        self.current_price = None
        self.timestamp = datetime.now().isoformat()
        self.afi = afi
        self.es = es
        self.egi = egi
        self.max_egi = max_egi
        self.company_cash_growth = company_cash_growth

    def add_scenario(self, name: str, probability: float, target_price: float,
                     trigger: str, key_assumptions: list, timeframe: str):
        if self.current_price and self.current_price > 0:
            return_pct = ((target_price - self.current_price) / self.current_price) * 100
        else:
            return_pct = None

        self.scenarios.append({
            "name": name,
            "probability": probability,
            "target_price": target_price,
            "return_pct": round(return_pct, 2) if return_pct is not None else None,
            "trigger": trigger,
            "key_assumptions": key_assumptions,
            "timeframe": timeframe,
        })

    def validate(self) -> dict:
        issues = []
        total_prob = sum(s["probability"] for s in self.scenarios)
        if abs(total_prob - 100) > 0.5:
            issues.append(f"Probability sum = {total_prob}%, should be 100%")
        if len(self.scenarios) < 3:
            issues.append(f"Scenario count = {len(self.scenarios)}, minimum 3 (Bear/Base/Bull)")

        returns = [s["return_pct"] for s in self.scenarios if s["return_pct"] is not None]
        if returns:
            if max(returns) < 0:
                issues.append("All scenarios negative — missing upside?")
            if min(returns) > 0:
                issues.append("All scenarios positive — confirmation bias?")

        bear = [s for s in self.scenarios if s["return_pct"] is not None and s["return_pct"] < 0]
        bull = [s for s in self.scenarios if s["return_pct"] is not None and s["return_pct"] > 0]

        rr_ratio = None
        if bear and bull:
            worst_loss = abs(min(s["return_pct"] for s in bear))
            best_gain = max(s["return_pct"] for s in bull)
            if worst_loss > 0:
                rr_ratio = round(best_gain / worst_loss, 2)

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "risk_reward_ratio": rr_ratio,
            "rr_passes_gate": rr_ratio is not None and rr_ratio >= 3.0,
        }

    def calculate_expected_return(self) -> float:
        total = 0
        for s in self.scenarios:
            if s["return_pct"] is not None:
                total += (s["probability"] / 100) * s["return_pct"]
        return round(total, 2)

    def calculate_kelly_fraction(self) -> float:
        """Half-Kelly position sizing with model uncertainty discount."""
        win = [s for s in self.scenarios if s.get("return_pct", 0) and s["return_pct"] > 0]
        lose = [s for s in self.scenarios if s.get("return_pct", 0) and s["return_pct"] < 0]

        if not win or not lose:
            return 0

        p = sum(s["probability"] for s in win) / 100
        q = 1 - p
        avg_win = sum(s["return_pct"] * s["probability"] for s in win) / sum(s["probability"] for s in win)
        avg_loss = abs(sum(s["return_pct"] * s["probability"] for s in lose) / sum(s["probability"] for s in lose))

        if avg_loss == 0:
            return 0

        b = avg_win / avg_loss
        
        # Apply Entropy-Discounted Sizing
        c_afi = max(0.0, min(1.0, self.afi))
        c_es = max(0.0, min(1.0, self.es))
        # EGI is normalized between [-1.0, 1.0], so c_egi_ratio is simply abs(self.egi)
        c_egi_ratio = min(1.0, abs(self.egi))
        
        confidence = (1.0 - c_afi) * c_es * (1.0 - c_egi_ratio)
        confidence = max(0.0, min(1.0, confidence))
        
        p_discounted = confidence * p + (1.0 - confidence) * 0.5
        p_discounted = max(0.0, min(1.0, p_discounted))
        
        q_discounted = 1.0 - p_discounted
        
        kelly = (b * p_discounted - q_discounted) / b
        half_kelly = kelly / 2
        
        # Dynamic Kelly cap scaling based on expectation gap
        base_cap = 0.25  # Standard cap is 25% for half-kelly in scenario matrix
        if self.egi > 0:
            if self.company_cash_growth:
                # Reflexivity Bubble Exception: bypass Kelly bet cap reduction under Soros reflexivity
                final_cap = base_cap
            else:
                # Standard risk reduction: reduce position cap based on normalized EGI intensity (scaled by 0.20)
                final_cap = max(0.05, base_cap - 0.20 * self.egi)
        else:
            final_cap = base_cap

        return round(max(0, min(half_kelly, final_cap)), 4)

    def to_dict(self) -> dict:
        validation = self.validate()
        expected_return = self.calculate_expected_return()
        kelly = self.calculate_kelly_fraction()

        return {
            "topic": self.topic,
            "timestamp": self.timestamp,
            "current_price": self.current_price,
            "scenarios": self.scenarios,
            "validation": validation,
            "expected_return_pct": expected_return,
            "kelly_fraction": kelly,
            "kelly_note": f"Half-Kelly position: {kelly*100:.1f}% (model uncertainty discounted)",
            "hard_gate_rr": f"R/R = 1:{validation['risk_reward_ratio']}" if validation["risk_reward_ratio"] else "N/A",
            "hard_gate_passed": validation["rr_passes_gate"],
        }

    def to_markdown_table(self) -> str:
        lines = [
            f"## Scenario Matrix: {self.topic}",
            f"*Generated: {self.timestamp}*\n",
            "| Scenario | Prob | Target | Return | Trigger | Window |",
            "|----------|------|--------|--------|---------|--------|",
        ]
        icons = {"bear": "🐻", "base": "🦊", "bull": "🐂", "black": "🦢"}
        for s in self.scenarios:
            first_word = s["name"].lower().split()[0]
            icon = icons.get(first_word, "📊")
            ret = f"{s['return_pct']:+.1f}%" if s["return_pct"] is not None else "N/A"
            lines.append(
                f"| {icon} {s['name']} | {s['probability']}% | {s['target_price']} | {ret} | {s['trigger']} | {s['timeframe']} |"
            )

        validation = self.validate()
        lines.append(f"\n**Expected Return**: {self.calculate_expected_return():+.2f}%")
        lines.append(f"**R/R Ratio**: 1:{validation['risk_reward_ratio']}" if validation["risk_reward_ratio"] else "**R/R**: N/A")
        lines.append(f"**Hard Gate (R/R > 1:3)**: {'✅ PASS' if validation['rr_passes_gate'] else '❌ FAIL'}")
        lines.append(f"**Half-Kelly Position**: {self.calculate_kelly_fraction()*100:.1f}%")

        if validation["issues"]:
            lines.append(f"\n⚠️ **Validation Issues**:")
            for issue in validation["issues"]:
                lines.append(f"  - {issue}")

        return "\n".join(lines)


def interactive_mode(topic: str):
    matrix = ScenarioMatrix(topic)
    try:
        matrix.current_price = float(input("Current price: "))
    except (ValueError, EOFError):
        print("Skipping current price", file=sys.stderr)

    print("\nEnter scenarios (empty line to finish):")
    print("Format: Name, Probability(%), Target Price, Trigger, Timeframe")
    print("Example: Bear, 25, 8.5, Industry-wide losses from oversupply, 6 months\n")

    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            break
        if not line:
            break
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 5:
            matrix.add_scenario(
                name=parts[0], probability=float(parts[1]),
                target_price=float(parts[2]), trigger=parts[3],
                key_assumptions=[], timeframe=parts[4],
            )

    result = matrix.to_dict()
    print("\n" + "=" * 60)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\n" + matrix.to_markdown_table())


def from_json_mode(filepath: str):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    matrix = ScenarioMatrix(data.get("topic", "Unknown"))
    matrix.current_price = data.get("current_price")

    for s in data.get("scenarios", []):
        matrix.add_scenario(
            name=s["name"], probability=s["probability"],
            target_price=s["target_price"], trigger=s.get("trigger", ""),
            key_assumptions=s.get("key_assumptions", []),
            timeframe=s.get("timeframe", ""),
        )

    print(json.dumps(matrix.to_dict(), ensure_ascii=False, indent=2))
    print("\n" + matrix.to_markdown_table())


def demo_mode():
    """Run with a compelling AI infrastructure vs Solar demo."""
    matrix = ScenarioMatrix("AI Infrastructure — Cooling & Power (算力液冷配电)")
    matrix.current_price = 42.0

    matrix.add_scenario(
        "Black Swan (极端)", 5, 15.0,
        "Major cloud capex freeze / geopolitical GPU ban extension",
        ["Hyperscaler capex cut >30%", "China AI chip supply severed"], "Any time"
    )
    matrix.add_scenario(
        "Bear (悲观)", 20, 30.0,
        "AI inference cost drops faster than demand grows, capex cycle peaks",
        ["Inference cost -80%/yr", "Cooling demand commoditized"], "6-12 months"
    )
    matrix.add_scenario(
        "Base (基准)", 45, 55.0,
        "Steady inference demand growth + liquid cooling penetration at 35%",
        ["Data center power density >50kW/rack", "Liquid cooling ASP stable"], "6-12 months"
    )
    matrix.add_scenario(
        "Bull (乐观)", 30, 85.0,
        "Sovereign AI buildout accelerates + next-gen chip TDP forces all-liquid",
        ["GB300 TDP >1500W mandates liquid", "Government AI clusters 3x forecast"], "6-12 months"
    )

    result = matrix.to_dict()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\n" + matrix.to_markdown_table())


def main():
    parser = argparse.ArgumentParser(description="Scenario Matrix Generator v0.9")
    parser.add_argument("--topic", default="Analysis", help="Topic of the analysis")
    parser.add_argument("--interactive", action="store_true", help="Interactive input")
    parser.add_argument("--from-json", help="Load scenarios from JSON file")
    parser.add_argument("--demo", action="store_true", help="Run with demo data")
    args = parser.parse_args()

    if args.from_json:
        from_json_mode(args.from_json)
    elif args.interactive:
        interactive_mode(args.topic)
    elif args.demo:
        demo_mode()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
