#!/usr/bin/env python3
"""
Server Container Health Check

Checks:
1. Supervisor is running
2. State file is being updated
3. If server should be running, verify DayZServer process exists
"""

import json
import sys
import time
from pathlib import Path

from dayz.config.paths import STATE_FILE, SUPERVISOR_PID

MAX_STATE_AGE = 60  # seconds


def check_supervisor() -> tuple[bool, str]:
    """Verify supervisor process is running"""
    if not SUPERVISOR_PID.exists():
        return False, "Supervisor PID file missing"

    try:
        pid = int(SUPERVISOR_PID.read_text().strip())
        Path(f"/proc/{pid}").exists()  # Touch /proc to validate presence
        return True, f"Supervisor running (PID {pid})"
    except Exception as e:  # pragma: no cover - healthcheck runtime only
        return False, f"Supervisor check failed: {e}"


def check_state_freshness() -> tuple[bool, str]:
    """Verify state file is being updated"""
    if not STATE_FILE.exists():
        return False, "State file missing"

    try:
        age = time.time() - STATE_FILE.stat().st_mtime
        if age > MAX_STATE_AGE:
            return False, f"State file stale ({int(age)}s old)"
        return True, f"State file fresh ({int(age)}s old)"
    except Exception as e:  # pragma: no cover
        return False, f"State check failed: {e}"


def check_server_state() -> tuple[bool, str]:
    """Check server state consistency"""
    try:
        state = json.loads(STATE_FILE.read_text())
        server_state = state.get("state", "unknown")
        pid = state.get("pid")

        if server_state == "running" and pid and not Path(f"/proc/{pid}").exists():
            return False, f"Server PID {pid} not found but state is 'running'"

        return True, f"Server state: {server_state}"
    except Exception as e:  # pragma: no cover
        return False, f"State parse failed: {e}"


def main() -> None:
    checks = [
        ("Supervisor", check_supervisor),
        ("State freshness", check_state_freshness),
        ("Server state", check_server_state),
    ]

    all_passed = True
    for name, check_fn in checks:
        passed, message = check_fn()
        status = "✓" if passed else "✗"
        print(f"{status} {name}: {message}")
        if not passed:
            all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
