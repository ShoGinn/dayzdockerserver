"""
Server command-line parameters using Pydantic models.

Clean Pydantic-based approach for composing DayZ server parameters.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from dayz.config.paths import BATTLEYE_DIR, PROFILES_DIR, SERVER_CFG, SERVER_PORT


class LogMode(str, Enum):
    """Server logging mode."""

    ENABLED = "enabled"
    DISABLED = "disabled"


class ParamSource(str, Enum):
    """Source of server parameters."""

    DEFAULT = "default"
    OVERRIDE = "override"
    CONFIGURED = "configured"


class ServerParams(BaseModel):
    """DayZ server command-line parameters."""

    # Core server parameters
    config: Path = Field(default=SERVER_CFG, description="Path to serverDZ.cfg")
    port: int = Field(default=SERVER_PORT, ge=1, le=65535, description="Server port")
    freezecheck: bool = Field(default=True, description="Enable freeze detection")

    # Paths
    be_path: Path = Field(
        default=BATTLEYE_DIR, description="BattlEye directory path", alias="BEpath"
    )
    profiles: Path = Field(default=PROFILES_DIR, description="Profiles directory path")

    # Logging configuration
    logs: LogMode = Field(default=LogMode.DISABLED, description="Enable/disable logs")
    admin_log: bool = Field(default=False, description="Enable admin logging")
    net_log: bool = Field(default=False, description="Enable network logging")

    # Optional parameters for mods/custom use
    extra_params: list[str] = Field(
        default_factory=list, description="Additional custom parameters"
    )

    model_config = {
        "populate_by_name": True,  # Allow alias names
        "validate_assignment": True,
        "use_enum_values": True,  # Serialize enums as values
    }

    @field_validator("config", "be_path", "profiles", mode="before")
    @classmethod
    def ensure_path(cls, v: str | Path) -> Path:
        """Convert strings to Path objects."""
        return Path(v) if isinstance(v, str) else v

    @field_validator("logs", mode="before")
    @classmethod
    def coerce_logs(cls, v: str | bool | LogMode) -> LogMode:
        """Coerce various log inputs to LogMode enum."""
        if isinstance(v, LogMode):
            return v
        if isinstance(v, bool):
            return LogMode.ENABLED if v else LogMode.DISABLED
        if isinstance(v, str):
            v_lower = v.lower()
            if v_lower in ("enabled", "true", "1", "yes", "on"):
                return LogMode.ENABLED
            if v_lower in ("disabled", "false", "0", "no", "off"):
                return LogMode.DISABLED
        return LogMode.DISABLED

    def to_command_string(self) -> str:
        """Build the command-line parameter string."""
        parts = [
            f"-config={self.config}",
            f"-port={self.port}",
        ]

        if self.freezecheck:
            parts.append("-freezecheck")

        parts.extend(
            [
                f"-BEpath={self.be_path}",
                f"-profiles={self.profiles}",
            ]
        )

        # Log flags
        parts.append("-dologs" if self.logs == LogMode.ENABLED else "-nologs")

        if self.admin_log:
            parts.append("-adminlog")

        if self.net_log:
            parts.append("-netlog")

        # Extra parameters
        if self.extra_params:
            parts.extend(self.extra_params)

        return " ".join(parts)

    @classmethod
    def from_command_string(cls, cmd_string: str) -> ServerParams:
        """Parse a command string into ServerParams."""
        import re

        data: dict[str, str | int | bool | list[str] | LogMode] = {}
        extra: list[str] = []

        # Parse standard params
        patterns = {
            "config": r"-config=([^\s]+)",
            "port": r"-port=(\d+)",
            "be_path": r"-BEpath=([^\s]+)",
            "profiles": r"-profiles=([^\s]+)",
        }

        for key, pattern in patterns.items():
            if match := re.search(pattern, cmd_string):
                data[key] = match.group(1)

        # Boolean flags
        data["freezecheck"] = "-freezecheck" in cmd_string
        data["admin_log"] = "-adminlog" in cmd_string
        data["net_log"] = "-netlog" in cmd_string
        data["logs"] = LogMode.ENABLED if "-dologs" in cmd_string else LogMode.DISABLED

        # Capture unknown params as extra
        known_flags = {
            "-config=",
            "-port=",
            "-freezecheck",
            "-BEpath=",
            "-profiles=",
            "-dologs",
            "-nologs",
            "-adminlog",
            "-netlog",
        }

        tokens = cmd_string.split()
        for token in tokens:
            if not any(token.startswith(flag) or token == flag for flag in known_flags):
                extra.append(token)

        if extra:
            data["extra_params"] = extra

        return cls.model_validate(data)


class ServerParamsUpdate(BaseModel):
    """Partial update model for server parameters."""

    port: int | None = Field(default=None, ge=1, le=65535)
    logs: LogMode | bool | None = None
    admin_log: bool | None = None
    net_log: bool | None = None
    extra_params: list[str] | None = None

    @field_validator("logs", mode="before")
    @classmethod
    def coerce_logs(cls, v: str | bool | LogMode | None) -> LogMode | None:
        """Coerce various log inputs to LogMode enum."""
        if v is None:
            return None
        if isinstance(v, LogMode):
            return v
        if isinstance(v, bool):
            return LogMode.ENABLED if v else LogMode.DISABLED
        if isinstance(v, str):
            v_lower = v.lower()
            if v_lower in ("enabled", "true", "1", "yes", "on"):
                return LogMode.ENABLED
            if v_lower in ("disabled", "false", "0", "no", "off"):
                return LogMode.DISABLED
        return None

    def apply_to(self, params: ServerParams) -> ServerParams:
        """Apply updates to existing params, returning new instance."""
        data = params.model_dump()

        # Update only provided fields
        for field, value in self.model_dump(exclude_unset=True).items():
            if value is not None:
                data[field] = value

        return ServerParams.model_validate(data)


# Convenience functions for backward compatibility
def compose_server_params(
    *,
    port: int | None = None,
    enable_logs: bool | None = None,
    admin_log: bool | None = None,
    net_log: bool | None = None,
) -> str:
    """Build server parameter string (legacy compatibility)."""
    params = ServerParams()

    if port is not None:
        params.port = port

    if enable_logs is not None:
        params.logs = LogMode.ENABLED if enable_logs else LogMode.DISABLED

    if admin_log is not None:
        params.admin_log = admin_log

    if net_log is not None:
        params.net_log = net_log

    return params.to_command_string()


def parse_server_params(cmd_string: str) -> ServerParams:
    """Parse command string into params object."""
    return ServerParams.from_command_string(cmd_string)
