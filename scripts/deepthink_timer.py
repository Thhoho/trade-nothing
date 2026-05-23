#!/usr/bin/env python3
"""
Trade Nothing v0.9 — DeepThink Countdown Timer

Interactive countdown timer for pause-and-think breaks.
Auto-skips in non-TTY (agent) environments.

Usage: python3 deepthink_timer.py --duration 30
"""

import sys
import time
import argparse
import os


def get_char(timeout):
    """Try to read a single character in raw mode. Returns None in non-TTY environments."""
    if not sys.stdin.isatty():
        return None

    try:
        import termios
        import tty
        import select
    except ImportError:
        # Windows or environments without termios
        return None

    fd = sys.stdin.fileno()
    try:
        old_settings = termios.tcgetattr(fd)
    except Exception:
        return None

    try:
        tty.setraw(fd)
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        if rlist:
            char = sys.stdin.read(1)
            return char.lower()
        return None
    except Exception:
        return None
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception:
            pass


def run_timer(duration):
    # Auto-skip in non-interactive (agent) environments
    if not sys.stdin.isatty() or os.environ.get("TRADE_NOTHING_AUTO_CONTINUE"):
        print("[DeepThink Timer] Non-interactive environment detected. Auto-continuing.")
        return 0

    print(f"\n⏳ [DeepThink Engine] System pausing for {duration}s.")
    print("Shortcut: [C]ontinue | [S]top | [M]anual | [Enter] Continue\n")

    start_time = time.time()
    last_second = -1

    while True:
        elapsed = time.time() - start_time
        remaining = int(duration - elapsed)

        if remaining != last_second:
            sys.stdout.write(f"\r\033[K⏱️  {max(0, remaining)}s remaining... [C/S/M] ")
            sys.stdout.flush()
            last_second = remaining

        if elapsed >= duration:
            print("\n\r\033[K⏱️  Timeout reached. Proceeding...")
            return 0

        char = get_char(0.1)

        if char:
            if char in ('c', '\r', '\n'):
                print("\n\r\033[K▶️  Continuing immediately... (Exit Code: 0)")
                return 0
            elif char == 's':
                print("\n\r\033[K🛑  Stopping and generating report... (Exit Code: 1)")
                return 1
            elif char == 'm':
                print("\n\r\033[K⏸️  Manual mode activated. (Exit Code: 2)")
                return 2
            elif char == '\x03':
                print("\n\r\033[K🛑  Interrupted. (Exit Code: 1)")
                return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DeepThink Countdown Timer")
    parser.add_argument("--duration", type=int, default=30, help="Duration in seconds")
    args = parser.parse_args()

    try:
        exit_code = run_timer(args.duration)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\r\033[K🛑  Interrupted. (Exit Code: 1)")
        sys.exit(1)
    except Exception:
        sys.exit(0)
