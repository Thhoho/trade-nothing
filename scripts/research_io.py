#!/usr/bin/env python3
"""Small atomic I/O and compare-and-swap primitives for the active kernel."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import time


def scratch_dir():
    configured = os.environ.get(
        "TRADE_NOTHING_SCRATCH_DIR", "~/.trade-nothing/scratch"
    )
    path = Path(configured).expanduser().resolve()
    if path == Path(path.anchor) or path == Path.home().resolve():
        raise ValueError("unsafe_research_scratch_dir")
    return path


def load_json(path, default=None):
    try:
        with open(os.fspath(path), encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"json_read_failed:{Path(path).name}:{type(exc).__name__}") from exc


@contextmanager
def _exclusive_lock(path, timeout_seconds=10.0):
    """Use an advisory file lock; the harmless lock file may remain after exit."""
    lock_path = os.fspath(path) + ".lock"
    os.makedirs(os.path.dirname(os.path.abspath(lock_path)), exist_ok=True)
    handle = open(lock_path, "a+", encoding="utf-8")
    started = time.monotonic()
    acquired = False
    try:
        try:
            import fcntl
        except ImportError:  # pragma: no cover - Windows fallback
            import msvcrt
            while not acquired:
                try:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    acquired = True
                except OSError:
                    if time.monotonic() - started >= timeout_seconds:
                        raise TimeoutError("research_file_lock_timeout")
                    time.sleep(0.05)
            yield
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            while not acquired:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except BlockingIOError:
                    if time.monotonic() - started >= timeout_seconds:
                        raise TimeoutError("research_file_lock_timeout")
                    time.sleep(0.05)
            yield
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _write_unlocked(path, value):
    path = os.path.abspath(os.fspath(path))
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    temporary = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=parent,
            prefix=f".{os.path.basename(path)}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = handle.name
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.remove(temporary)


def save_json(path, value, *, create_only=False):
    with _exclusive_lock(path):
        if create_only and os.path.exists(path):
            raise ValueError("json_create_conflict")
        _write_unlocked(path, value)
    return value


def save_run_cas(path, run, *, expected_revision, create=False):
    """Atomically publish one canonical research transition.

    This is deliberately research-specific: callers cannot swap out or omit the
    semantic transition and persisted-state validators.
    """
    import research_core

    with _exclusive_lock(path):
        current = load_json(path, default=None)
        if create:
            if current is not None or int(expected_revision) != 0:
                raise ValueError("research_state_create_conflict")
            current_revision = 0
        else:
            if not isinstance(current, dict):
                raise ValueError("research_state_missing_for_cas")
            try:
                current_revision = int(current["run_ledger"]["state_revision"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("research_state_revision_invalid") from exc
            if current_revision != int(expected_revision):
                raise ValueError("research_state_revision_conflict")
        updated = deepcopy(run)
        updated.setdefault("run_ledger", {})["state_revision"] = current_revision + 1
        if create:
            research_core.validate_initial_run(updated)
        else:
            research_core.validate_transition(current, updated)
        research_core.validate_persisted_run(
            updated, require_written_snapshot=False
        )
        _write_unlocked(path, updated)
    return updated


def save_host_invocation_cas(path, record, *, expected_revision):
    """Atomically append one caller-reported external-process observation."""
    import research_core

    with _exclusive_lock(path):
        current = load_json(path, default=None)
        if not isinstance(current, dict):
            raise ValueError("research_state_missing_for_cas")
        try:
            current_revision = int(current["run_ledger"]["state_revision"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("research_state_revision_invalid") from exc
        if current_revision != int(expected_revision):
            raise ValueError("research_state_revision_conflict")
        updated = research_core.register_host_invocation(current, record)
        updated["run_ledger"]["state_revision"] = current_revision + 1
        research_core.validate_transition(
            current, updated, allow_host_invocation_append=True
        )
        research_core.validate_persisted_run(
            updated, require_written_snapshot=False
        )
        _write_unlocked(path, updated)
    return updated


def save_authorization_cas(path, extra_loops, *, expected_revision):
    """Atomically apply the only legal research-budget transition."""
    import research_core

    with _exclusive_lock(path):
        current = load_json(path, default=None)
        if not isinstance(current, dict):
            raise ValueError("research_state_missing_for_cas")
        try:
            current_revision = int(current["run_ledger"]["state_revision"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("research_state_revision_invalid") from exc
        if current_revision != int(expected_revision):
            raise ValueError("research_state_revision_conflict")
        updated = research_core.authorize_more_loops(current, extra_loops)
        updated["run_ledger"]["state_revision"] = current_revision + 1
        research_core.validate_transition(
            current, updated, allow_budget_change=True
        )
        research_core.validate_persisted_run(
            updated, require_written_snapshot=False
        )
        _write_unlocked(path, updated)
    return updated
