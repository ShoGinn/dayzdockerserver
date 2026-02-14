"""
DayZ Server - Volume Initialization

Replaces the legacy shell script with a Python implementation that uses
shared path constants. Creates required directories, fixes ownership, and
writes the init marker.
"""

from __future__ import annotations

import os
from pathlib import Path

from dayz.config.paths import (
    BATTLEYE_DIR,
    CONTROL_DIR,
    HOME_DIR,
    MODS_DIR,
    MPMISSIONS,
    MPMISSIONS_ACTIVE,
    MPMISSIONS_UPSTREAM,
    PROFILES_DIR,
    SERVER_FILES,
    SERVER_KEYS_DIR,
    USER_ID,
    WORKSHOP_DIR,
)

GROUP_ID = int(os.getenv("GROUP_ID", str(USER_ID)))
STEAMCMD_DIR = Path(os.getenv("STEAMCMD_DIR", "/opt/steamcmd"))
INIT_MARKER = CONTROL_DIR / ".init-complete"


def _print_header() -> None:
    print("======================================")
    print("DayZ Server - Volume Initialization")
    print("======================================")
    print(f"User ID: {USER_ID}")
    print(f"Group ID: {GROUP_ID}")
    print("")


def _ensure_directories() -> None:
    print("Creating directory structure...")
    dirs = [
        HOME_DIR / ".steam",
        SERVER_FILES,
        WORKSHOP_DIR,
        SERVER_KEYS_DIR,
        MPMISSIONS_UPSTREAM,
        MPMISSIONS_ACTIVE,
        MPMISSIONS,
        MODS_DIR,
        PROFILES_DIR,
        BATTLEYE_DIR,
        CONTROL_DIR,
    ]

    for path in dirs:
        path.mkdir(parents=True, exist_ok=True)


def _recursive_chown(path: Path) -> None:
    if not path.exists():
        return

    for root, dirs, files in os.walk(path, onerror=lambda e: print(f"  Warning: {e}")):
        root_path = Path(root)
        try:
            os.chown(root_path, USER_ID, GROUP_ID)
        except Exception as e:
            print(f"  Warning: Failed to chown {root_path}: {e}")

        for name in dirs:
            try:
                os.chown(root_path / name, USER_ID, GROUP_ID)
            except Exception as e:
                print(f"  Warning: Failed to chown {root_path / name}: {e}")

        for name in files:
            try:
                os.chown(root_path / name, USER_ID, GROUP_ID)
            except Exception as e:
                print(f"  Warning: Failed to chown {root_path / name}: {e}")

    try:
        os.chown(path, USER_ID, GROUP_ID)
    except Exception as e:
        print(f"  Warning: Failed to chown {path}: {e}")


def _set_permissions() -> None:
    try:
        CONTROL_DIR.chmod(0o777)
        os.chown(CONTROL_DIR, USER_ID, GROUP_ID)
    except Exception as e:
        print(f"  Warning: Failed to set CONTROL_DIR permissions: {e}")

    try:
        INIT_MARKER.touch(exist_ok=True)
        os.chown(INIT_MARKER, USER_ID, GROUP_ID)
    except Exception as e:
        print(f"  Warning: Failed to set INIT_MARKER permissions: {e}")


def main() -> None:
    _print_header()
    _ensure_directories()

    print("Setting ownership...")
    targets = [
        HOME_DIR,
        SERVER_FILES,
        MPMISSIONS_UPSTREAM,
        MPMISSIONS_ACTIVE,
        MPMISSIONS,
        MODS_DIR,
        PROFILES_DIR,
        CONTROL_DIR,
    ]

    for target in targets:
        _recursive_chown(target)
        print(f"  ✓ {target}")

    if STEAMCMD_DIR.exists():
        _recursive_chown(STEAMCMD_DIR)
        print(f"  ✓ {STEAMCMD_DIR}")

    _set_permissions()

    print("")
    print("======================================")
    print("Volume initialization complete!")
    print("======================================")


if __name__ == "__main__":
    main()
