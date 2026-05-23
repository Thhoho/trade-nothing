#!/usr/bin/env python3
"""
Trade Nothing v0.9 — DeepThink Engine (递归引擎)

Unified controller: state tracking + convergence judgment + 12-round fuse + 
unrefuted attack vector JSON storage.

Usage:
  python3 deepthink_engine.py --start --topic "Topic Name"
  python3 deepthink_engine.py --checkpoint --round 1 --lfi 0.65 --posterior 28.6 \
      --open-attacks 2 --new-evidence 3 --next-action "Search XX" \
      --unrefuted-attacks-json '[{"attack":"...", "reason":"...", "trigger_date":"2026-08-30"}]'
  python3 deepthink_engine.py --status
"""

import argparse
import json
import os
import sys
import time
import select
from datetime import datetime

# Import shared utilities
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import generate_topic_slug, get_state_dir, load_json_safe, save_json

MIN_ROUNDS = 3
MAX_ROUNDS = 12
LFI_THRESHOLD = 0.15
TIMER_DURATION = 15


def resolve_state_file(topic: str = "", state_file_override: str = "") -> str:
    """Resolve the state file path based on topic or explicit override."""
    if state_file_override:
        return state_file_override
    elif topic:
        slug = generate_topic_slug(topic)
        return os.path.join(get_state_dir(), f"{slug}_state.json")
    else:
        return os.path.join(get_state_dir(), "default_state.json")


def load_state(state_file: str) -> dict:
    return load_json_safe(state_file, {
        "rounds": [], "started_at": None, "topic": None, "unrefuted_attacks": []
    })


def check_convergence(round_num: int, lfi: float, open_attacks: int) -> dict:
    if round_num >= MAX_ROUNDS:
        return {"decision": "fuse_break",
                "reason": f"Reached maximum {MAX_ROUNDS} rounds. Fuse triggered."}

    if round_num < MIN_ROUNDS:
        return {"decision": "continue",
                "reason": f"Round {round_num} < minimum {MIN_ROUNDS}. Must continue."}

    if open_attacks > 0:
        return {"decision": "continue",
                "reason": f"{open_attacks} unrefuted attack vectors remain. Must continue."}

    if lfi >= LFI_THRESHOLD:
        return {"decision": "continue",
                "reason": f"LFI={lfi:.2f} >= {LFI_THRESHOLD}. Logic not yet hardened."}

    return {"decision": "converge",
            "reason": f"LFI={lfi:.2f} < {LFI_THRESHOLD}, rounds={round_num} >= {MIN_ROUNDS}, "
                      f"unrefuted attacks=0. Convergence criteria met."}


# ─── Timer ───

def _get_char(timeout):
    """Non-blocking character read with TTY safety."""
    if not sys.stdin.isatty():
        return None
    try:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
    except Exception:
        return None
    try:
        tty.setraw(fd)
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        if rlist:
            return sys.stdin.read(1).lower()
        return None
    except Exception:
        return None
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            pass


def run_timer(duration: int = TIMER_DURATION) -> str:
    """Interactive countdown timer. Returns 'continue', 'stop', or 'manual'.
    
    Auto-skips in non-interactive environments (agent runtimes, CI, pipes).
    """
    # Auto-continue in headless/agent environments
    if not sys.stdin.isatty() or os.environ.get("TRADE_NOTHING_AUTO_CONTINUE"):
        return "continue"

    print(f"\n⏳ [DeepThink Engine] Next round starts in {duration}s.",
          file=sys.stderr)
    print("Shortcuts: [C]ontinue | [S]top & report | [M]anual mode\n",
          file=sys.stderr)

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
            sys.stderr.write("\n\033[K▶️  Timeout. Auto-continuing.\n")
            return "continue"

        ch = _get_char(0.1)
        if ch:
            if ch in ('c', '\r', '\n'):
                sys.stderr.write("\n\033[K▶️  Continuing next round.\n")
                return "continue"
            elif ch == 's':
                sys.stderr.write("\n\033[K🛑  Stopping. Generating final report.\n")
                return "stop"
            elif ch == 'm':
                sys.stderr.write("\n\033[K⏸️  Manual mode.\n")
                return "manual"
            elif ch == '\x03':
                sys.stderr.write("\n\033[K🛑  Interrupted.\n")
                return "stop"


# ─── Commands ───

def cmd_start(topic: str, state_file: str):
    if os.path.exists(state_file):
        os.remove(state_file)

    state = {
        "rounds": [],
        "started_at": datetime.now().isoformat(),
        "topic": topic,
        "unrefuted_attacks": []
    }
    save_json(state_file, state)

    template = (
        f"[SCOPE] Target: {topic} | Core Thesis: [one falsifiable statement] | Time Horizon: ___\n"
        f"[PRIOR] P₀ = X% (source: ___)\n"
        f"[Abductive] 🔴 Crash -50% script: ___ | 🟢 Moon +100% script: ___"
    )

    output = {
        "action": "start",
        "topic": topic,
        "session_started": state["started_at"],
        "state_file": state_file,
        "template": template,
        "instruction": (
            "New analysis initialized. Fetch data anchors, fill the template above, "
            "then run Round 1 Detective→Inquisitor→Judge analysis. "
            "Call --checkpoint after Round 1."
        ),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_checkpoint(args, state_file: str):
    state = load_state(state_file)

    if not state["started_at"]:
        state["started_at"] = datetime.now().isoformat()

    unrefuted_attacks_data = []
    if args.unrefuted_attacks_json:
        try:
            unrefuted_attacks_data = json.loads(args.unrefuted_attacks_json)
        except json.JSONDecodeError as e:
            print(f"[WARN] Failed to parse unrefuted-attacks-json: {e}", file=sys.stderr)

    round_data = {
        "round": args.round,
        "lfi": args.lfi,
        "posterior": args.posterior,
        "open_attacks": args.open_attacks,
        "new_evidence": args.new_evidence,
        "next_action": args.next_action,
        "unrefuted_attacks": unrefuted_attacks_data,
        "timestamp": datetime.now().isoformat(),
    }
    state["rounds"].append(round_data)
    state["unrefuted_attacks"] = unrefuted_attacks_data
    save_json(state_file, state)

    convergence = check_convergence(args.round, args.lfi, args.open_attacks)
    bayesian_trace = " → ".join(
        f"R{r['round']}:{r['posterior']}%" for r in state["rounds"]
    )

    # Converge / Fuse → no timer
    if convergence["decision"] in ("converge", "fuse_break"):
        instruction = "Output final report: hard-gate check → scenario matrix → decision tree → evidence chain → action plan."
        if convergence["decision"] == "fuse_break":
            instruction = ("⚠️ Fuse warning: max rounds reached, conclusions may be immature. "
                           + instruction + " List all unresolved disputes.")

        output = {
            "action": convergence["decision"],
            "round_completed": args.round,
            "lfi": args.lfi,
            "posterior": f"{args.posterior}%",
            "bayesian_trace": bayesian_trace,
            "total_rounds": len(state["rounds"]),
            "reason": convergence["reason"],
            "instruction": instruction,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    # Continue → timer then instruct
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
            "round_completed": args.round,
            "posterior": f"{args.posterior}%",
            "bayesian_trace": bayesian_trace,
            "total_rounds": len(state["rounds"]),
            "reason": "User requested stop.",
            "instruction": "User stopped. Output report based on current evidence (mark as early termination).",
        }
    elif user_choice == "manual":
        output = {
            "action": "manual",
            "round_completed": args.round,
            "posterior": f"{args.posterior}%",
            "bayesian_trace": bayesian_trace,
            "total_rounds": len(state["rounds"]),
            "instruction": "Manual mode. Awaiting user instructions.",
        }
    else:
        output = {
            "action": "continue",
            "round_completed": args.round,
            "next_round": args.round + 1,
            "lfi": args.lfi,
            "posterior": f"{args.posterior}%",
            "bayesian_trace": bayesian_trace,
            "total_rounds": len(state["rounds"]),
            "remaining_before_fuse": MAX_ROUNDS - args.round,
            "reason": convergence["reason"],
            "fetch_hint": args.next_action,
            "instruction": (
                f"Enter Round {args.round + 1}. "
                f"First fetch/search: {args.next_action}. "
                f"Then run Detective→Inquisitor→Judge analysis."
            ),
        }

    print(json.dumps(output, ensure_ascii=False, indent=2))


def cmd_status(state_file: str):
    state = load_state(state_file)
    if not state["rounds"]:
        print(json.dumps({"status": "idle", "message": "No active deepthink session."},
                          ensure_ascii=False, indent=2))
        return

    latest = state["rounds"][-1]
    convergence = check_convergence(
        latest["round"], latest["lfi"], latest.get("open_attacks", 0))
    bayesian_trace = " → ".join(
        f"R{r['round']}:{r['posterior']}%" for r in state["rounds"])

    output = {
        "status": "active",
        "topic": state.get("topic", ""),
        "started_at": state["started_at"],
        "total_rounds": len(state["rounds"]),
        "latest_round": latest["round"],
        "latest_lfi": latest["lfi"],
        "latest_posterior": f"{latest['posterior']}%",
        "bayesian_trace": bayesian_trace,
        "convergence_check": convergence,
        "remaining_before_fuse": MAX_ROUNDS - latest["round"],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ─── CLI ───

def main():
    parser = argparse.ArgumentParser(description="DeepThink Engine v0.9")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--start", action="store_true", help="Initialize new analysis")
    mode.add_argument("--checkpoint", action="store_true", help="Record round and check convergence")
    mode.add_argument("--status", action="store_true", help="View session status")

    parser.add_argument("--topic", type=str, default="", help="Analysis target")
    parser.add_argument("--state-file", type=str, default="", help="Custom state file path")
    parser.add_argument("--round", type=int, help="Current round number")
    parser.add_argument("--lfi", type=float, help="Current round LFI")
    parser.add_argument("--posterior", type=float, help="Current posterior probability (%%)")
    parser.add_argument("--open-attacks", type=int, default=0,
                        help="Number of unrefuted attack vectors")
    parser.add_argument("--new-evidence", type=int, default=0,
                        help="Number of new evidence items this round")
    parser.add_argument("--next-action", type=str, default="",
                        help="Data to fetch next round")
    parser.add_argument("--unrefuted-attacks-json", type=str, default="",
                        help="Unrefuted attack vector details (JSON)")
    parser.add_argument("--no-timer", action="store_true",
                        help="Skip interactive timer (headless/debug)")

    args = parser.parse_args()
    state_file = resolve_state_file(topic=args.topic, state_file_override=args.state_file)

    if args.start:
        cmd_start(args.topic, state_file)
    elif args.checkpoint:
        if args.round is None or args.lfi is None or args.posterior is None:
            parser.error("--checkpoint requires --round, --lfi, --posterior")
        cmd_checkpoint(args, state_file)
    elif args.status:
        cmd_status(state_file)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Interrupted.", file=sys.stderr)
        sys.exit(1)
