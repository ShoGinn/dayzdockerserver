"""VPP Admin Tools utilities.

Helpers to manage VPPAdminTools configuration files under the profiles directory.
"""

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from dayz.config.paths import PROFILES_DIR

# Paths (module-local; plugin-style encapsulation)
VPP_DIR: Path = PROFILES_DIR / "VPPAdminTools"
VPP_PERMISSIONS_DIR: Path = VPP_DIR / "Permissions"
CREDS_PATH: Path = VPP_PERMISSIONS_DIR / "credentials.txt"
SUPERADMINS_PATH: Path = VPP_PERMISSIONS_DIR / "SuperAdmins" / "SuperAdmins.txt"


class VPPPasswordRequest(BaseModel):
    """VPP Admin password request."""

    password: str = Field(min_length=1)


class VPPMode(str, Enum):
    OVERWRITE = "overwrite"
    ADD = "add"


class VPPSuperAdminsRequest(BaseModel):
    """VPP superadmin Steam64 IDs request."""

    steam64_ids: list[str]
    mode: VPPMode = VPPMode.OVERWRITE

    @field_validator("mode", mode="before")
    @classmethod
    def _coerce_mode(cls, v: Any) -> VPPMode:
        if isinstance(v, str):
            v = v.strip().lower()
            try:
                return VPPMode(v)
            except ValueError as exc:
                raise ValueError("mode must be 'overwrite' or 'add'") from exc
        if isinstance(v, VPPMode):
            return v
        raise ValueError("mode must be 'overwrite' or 'add'")

    @field_validator("steam64_ids")
    @classmethod
    def _validate_ids(cls, v: list[str]) -> list[str]:
        """Normalize to digit-only strings, dedupe, preserve order."""
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in v:
            s = raw.strip()
            if s.isdigit() and s not in seen:
                seen.add(s)
                normalized.append(s)
        if not normalized:
            raise ValueError("No valid Steam64 IDs provided")
        return normalized


class VPPSuperAdminsResponse(BaseModel):
    """VPP superadmin list response."""

    steam64_ids: list[str]


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def set_password(password: str) -> tuple[bool, str]:
    """Set VPPAdminTools password.

    Writes to `profiles/VPPAdminTools/Permissions/credentials.txt`.
    """
    if not password:
        return False, "Password cannot be empty"

    try:
        _ensure_parent(CREDS_PATH)
        CREDS_PATH.write_text(password + "\n", encoding="utf-8")
        return True, "VPP password set"
    except OSError as e:
        return False, f"Failed to write credentials: {e}"


def set_superadmins(
    steam_ids: list[str],
    mode: VPPMode = VPPMode.OVERWRITE,
) -> tuple[bool, str]:
    """Set VPP superadmin Steam64 IDs.

    Writes to `profiles/VPPAdminTools/Permissions/SuperAdmins/SuperAdmins.txt`.

    mode:
      - "overwrite": replace with provided list
      - "add": union with existing IDs
    """
    if not steam_ids:
        return False, "No Steam IDs provided"

    try:
        _ensure_parent(SUPERADMINS_PATH)

        existing: set[str] = set()
        if mode is VPPMode.ADD and SUPERADMINS_PATH.exists():
            existing = {
                line.strip()
                for line in SUPERADMINS_PATH.read_text(encoding="utf-8").splitlines()
                if line.strip().isdigit()
            }

        provided = {sid.strip() for sid in steam_ids if sid.strip().isdigit()}
        final = sorted(existing | provided) if mode is VPPMode.ADD else sorted(provided)
        SUPERADMINS_PATH.write_text("\n".join(final) + "\n", encoding="utf-8")
        return True, f"Set {len(final)} superadmin(s)"
    except OSError as e:
        return False, f"Failed to write superadmins: {e}"


def get_superadmins() -> tuple[bool, list[str] | str]:
    """Get VPP superadmin Steam64 IDs.

    Reads from `profiles/VPPAdminTools/Permissions/SuperAdmins/SuperAdmins.txt`.

    Returns:
        Tuple of (success: bool, result: list[str] | error_message: str)
    """
    try:
        if not SUPERADMINS_PATH.exists():
            return True, []

        lines = SUPERADMINS_PATH.read_text(encoding="utf-8").splitlines()
        steam_ids = [line.strip() for line in lines if line.strip().isdigit()]
        return True, steam_ids
    except OSError as e:
        return False, f"Failed to read superadmins: {e}"
