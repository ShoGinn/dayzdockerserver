"""
Subprocess and privilege management utilities.

Utilities for running commands with privilege dropping and environment management.
"""

import os
import subprocess
from collections.abc import Callable


def create_privilege_dropper(target_uid: int, target_gid: int | None = None) -> Callable[[], None]:
    """
    Create a privilege dropping function for subprocess preexec_fn.

    Args:
        target_uid: User ID to drop to
        target_gid: Group ID to drop to (defaults to target_uid)

    Returns:
        Function that drops privileges when called

    Example:
        >>> dropper = create_privilege_dropper(1000)
        >>> subprocess.run(["command"], preexec_fn=dropper)
    """
    gid = target_gid if target_gid is not None else target_uid

    def drop_privileges() -> None:
        """Drop privileges to target user/group."""
        try:
            os.setgid(gid)
            os.setuid(target_uid)
        except Exception:
            pass

    return drop_privileges


def should_drop_privileges() -> bool:
    """
    Check if privilege dropping should be enabled.

    Returns:
        True if running as root (UID 0), False otherwise
    """
    return os.getuid() == 0


def get_directory_size_du(directory: str) -> str:
    """
    Get directory size using 'du -sh' command.

    Args:
        directory: Path to directory

    Returns:
        Human-readable size string or "0B" on error

    Examples:
        >>> get_directory_size_du("/tmp/mydir")
        '1.5M'
    """
    try:
        result = subprocess.run(
            ["du", "-sh", directory],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.split()[0]
    except Exception:
        pass
    return "0B"


def check_steam_errors(output: str) -> tuple[bool, str | None]:
    """
    Check SteamCMD output for critical errors.

    Args:
        output: SteamCMD command output

    Returns:
        Tuple of (has_error, error_message)

    Examples:
        >>> check_steam_errors("Everything OK")
        (False, None)
        >>> check_steam_errors("ERROR! Not logged on")
        (True, 'ERROR! Not logged on')
    """
    critical_errors = [
        "ERROR! Not logged on",
        "ERROR (Invalid Password)",
        "No subscription",
    ]

    for error in critical_errors:
        if error in output:
            return True, error

    return False, None
