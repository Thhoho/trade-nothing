#!/usr/bin/env python3
"""
Trade Nothing v0.9 — Shared Utilities

Portable helper functions used across multiple scripts.
All paths resolved via environment variables or OS-agnostic defaults.
"""

import os
import re
import sys
import json
import platform
from pathlib import Path


# ─── Portable Path Resolution ───────────────────────────────────────────────

def get_skill_dir() -> str:
    """Get the root directory of the Trade Nothing skill installation."""
    return os.environ.get(
        "TRADE_NOTHING_SKILL_DIR",
        str(Path(__file__).parent.parent)
    )


def get_scratch_dir() -> str:
    """Get the scratch directory for runtime state files."""
    default = os.path.expanduser("~/.trade-nothing/scratch")
    return os.environ.get("TRADE_NOTHING_SCRATCH_DIR", default)


def get_output_dir() -> str:
    """Get the output directory for generated files (reports, Excel models)."""
    default = os.path.expanduser("~/trade-nothing-outputs")
    return os.environ.get("TRADE_NOTHING_OUTPUT_DIR", default)


def get_vault_dir() -> str:
    """Get the vault directory for research data."""
    default = os.path.expanduser("~/trade-nothing-vault")
    return os.environ.get("TRADE_NOTHING_VAULT_DIR", default)


def get_evolution_path() -> str:
    """Get the path to the Evolution.md active memory file."""
    return os.environ.get(
        "TRADE_NOTHING_EVOLUTION_PATH",
        os.path.join(get_skill_dir(), "Methodology_Evolution.md")
    )


def get_state_dir() -> str:
    """Get the directory for deepthink state files."""
    state_dir = os.path.join(get_scratch_dir(), "state")
    os.makedirs(state_dir, exist_ok=True)
    return state_dir


# ─── Topic Slug Generation ──────────────────────────────────────────────────

def generate_topic_slug(topic: str) -> str:
    """Convert topic text to a clean, filesystem-safe slug.
    
    Extracts stock codes (6-digit numbers), strips stop words,
    and produces a lowercase, underscore-separated identifier.
    
    Examples:
        "东方日升 300118 HJT效率" → "300118_东方日升_hjt"
        "General Analysis"       → "general_analysis"
    """
    if not topic:
        return "general"

    # Try to extract stock code (6 digits)
    codes = re.findall(r"\d{6}", topic)
    code_prefix = f"{codes[0]}_" if codes else ""

    # Clean words: keep CJK characters and alphanumeric
    words = re.findall(r"[\u4e00-\u9fa5\w]+", topic.lower())
    stopwords = {
        "研究", "分析", "破产", "重整", "关于", "价格",
        "走势", "突破", "标的", "效率", "技术", "the",
        "a", "an", "of", "in", "for", "and", "or"
    }
    cleaned_words = [w for w in words if len(w) > 0 and w not in stopwords]

    if not cleaned_words:
        cleaned_words = ["general"]

    slug = "_".join(cleaned_words)
    if len(slug) > 30:
        slug = slug[:30].rstrip("_")
    return code_prefix + slug


# ─── Cross-Platform Notifications ───────────────────────────────────────────

def send_notification(title: str, message: str) -> bool:
    """Send a system notification. Cross-platform with graceful fallback.
    
    Supports:
    - macOS: osascript
    - Linux: notify-send
    - Windows: PowerShell toast (basic)
    - Fallback: stderr print
    
    Returns True if notification was sent, False if fell back to stderr.
    """
    system = platform.system()
    
    try:
        if system == "Darwin":
            import subprocess
            cmd = f'display notification "{message}" with title "{title}"'
            subprocess.call(["osascript", "-e", cmd], timeout=5)
            return True
        elif system == "Linux":
            import subprocess
            subprocess.call(["notify-send", title, message], timeout=5)
            return True
        elif system == "Windows":
            import subprocess
            ps_cmd = (
                f'[System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms") | Out-Null; '
                f'$notify = New-Object System.Windows.Forms.NotifyIcon; '
                f'$notify.Icon = [System.Drawing.SystemIcons]::Information; '
                f'$notify.Visible = $true; '
                f'$notify.ShowBalloonTip(5000, "{title}", "{message}", '
                f'[System.Windows.Forms.ToolTipIcon]::Info)'
            )
            subprocess.call(["powershell", "-Command", ps_cmd], timeout=5)
            return True
    except Exception:
        pass
    
    # Fallback: print to stderr
    print(f"🔔 [{title}] {message}", file=sys.stderr)
    return False


# ─── Proxy Cleanup ──────────────────────────────────────────────────────────

def clean_proxy_env():
    """Remove proxy environment variables that interfere with domestic API calls.
    
    Many China financial data APIs (EastMoney, Tencent HQ) fail through 
    corporate/VPN proxies. Call this before making API requests.
    """
    os.environ['no_proxy'] = '*'
    for env_var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        if env_var in os.environ:
            del os.environ[env_var]


# ─── JSON I/O ────────────────────────────────────────────────────────────────

import time

class CrossPlatformFileLock:
    """An atomic, directory-based cross-platform lock for safe concurrent operations."""
    def __init__(self, file_path: str, timeout: float = 10.0):
        self.lock_dir = file_path + ".lockdir"
        self.timeout = timeout
        self.locked = False

    def acquire(self):
        start_time = time.time()
        while True:
            try:
                os.mkdir(self.lock_dir)
                self.locked = True
                return True
            except FileExistsError:
                if time.time() - start_time > self.timeout:
                    # Stale lock recovery for local single-user CLI
                    try:
                        os.rmdir(self.lock_dir)
                        os.mkdir(self.lock_dir)
                        self.locked = True
                        return True
                    except Exception:
                        raise TimeoutError(f"Lock acquire timeout for {self.lock_dir}")
                time.sleep(0.05)

    def release(self):
        if self.locked:
            try:
                os.rmdir(self.lock_dir)
            except Exception:
                pass
            self.locked = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def load_json_safe(filepath: str, default=None):
    """Load JSON with graceful fallback on missing/corrupt files with lock."""
    if default is None:
        default = {}
    if not os.path.exists(filepath):
        return default
    lock = CrossPlatformFileLock(filepath)
    try:
        with lock:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def save_json(filepath: str, data, ensure_dir: bool = True):
    """Save JSON with optional parent directory creation and lock."""
    if ensure_dir:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    lock = CrossPlatformFileLock(filepath)
    with lock:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

