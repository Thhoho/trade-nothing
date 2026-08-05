#!/usr/bin/env python3
"""Small POSIX process-group controls for bounded host adapters."""
from __future__ import annotations

import os
import signal


def kill_process_group(process):
    """Kill an isolated process session, falling back to the direct child."""
    if process is None or process.poll() is not None:
        return "already_exited"
    try:
        # Every caller creates the child with start_new_session=True, so its PID
        # is also the process-group ID. Killing only the direct CLI could leave
        # model/tool descendants running after the timeout.
        os.killpg(process.pid, signal.SIGKILL)
        return "process_group"
    except (AttributeError, OSError, ProcessLookupError):
        process.kill()
        return "direct_process_fallback"
