"""
DayZ Server - Path Configuration

Centralized path definitions for all container volumes and files.
"""

import os
from pathlib import Path

# =============================================================================
# Environment Configuration
# =============================================================================

USER_ID = int(os.getenv("USER_ID", "1000"))
GROUP_ID = int(os.getenv("GROUP_ID", str(USER_ID)))
SERVER_PORT = int(os.getenv("SERVER_PORT", "2302"))
STEAM_QUERY_PORT = int(os.getenv("STEAM_QUERY_PORT", "27016"))

# Channel + Steam App IDs (single source of truth)
CHANNEL_STABLE = "stable"
CHANNEL_EXPERIMENTAL = "experimental"
VALID_CHANNELS = {CHANNEL_STABLE, CHANNEL_EXPERIMENTAL}

# Default to stable; channel overrides come from APP_CHANNEL_FILE
DEFAULT_CHANNEL = CHANNEL_STABLE

DAYZ_SERVER_APPIDS = {
    CHANNEL_STABLE: 223350,
    CHANNEL_EXPERIMENTAL: 1042420,
}
DAYZ_SERVER_APPID = DAYZ_SERVER_APPIDS[DEFAULT_CHANNEL]  # backward compatibility
DAYZ_CLIENT_APPID = 221100  # For workshop mods


# =============================================================================
# Volume Paths
# =============================================================================

# User home (Steam credentials, etc.)
HOME_DIR = Path.home()
STEAM_LOGIN_FILE = HOME_DIR / "steamlogin"

# Server installation
SERVER_FILES = Path("/serverfiles")
SERVER_BINARY = SERVER_FILES / "DayZServer"
WORKSHOP_DIR = SERVER_FILES / "steamapps" / "workshop" / "content" / str(DAYZ_CLIENT_APPID)
SERVER_KEYS_DIR = SERVER_FILES / "keys"

# Mission files
MPMISSIONS_UPSTREAM = Path("/mpmissions-upstream")  # pristine templates
MPMISSIONS_ACTIVE = Path("/serverfiles/mpmissions")  # live missions used by the server
MPMISSIONS = Path("/mpmissions")  # legacy/read-only template mount (kept for compatibility)

# Mods (alternative location, usually same as workshop)
MODS_DIR = Path("/mods")

# Server profile (config, battleye, logs)
PROFILES_DIR = Path("/profiles")
SERVER_CFG = PROFILES_DIR / "serverDZ.cfg"
BATTLEYE_DIR = PROFILES_DIR / "battleye"

# Control plane (API <-> Supervisor communication)
CONTROL_DIR = Path("/control")
SOCKET_PATH = CONTROL_DIR / "supervisor.sock"
STATE_FILE = CONTROL_DIR / "state.json"
SUPERVISOR_PID = CONTROL_DIR / "supervisor.pid"
MAINTENANCE_FILE = CONTROL_DIR / "maintenance"
MOD_PARAM_FILE = CONTROL_DIR / "mod_param"
SERVER_MOD_PARAM_FILE = CONTROL_DIR / "server_mod_param"
SERVER_PARAMS_FILE = CONTROL_DIR / "server_params"
APP_CHANNEL_FILE = CONTROL_DIR / "app_channel"  # "stable" or "experimental"
MOD_MODE_FILE = CONTROL_DIR / "mod_modes.json"  # { "<mod_id>": "server"|"client" }

# Host-mounted files (read-only)
FILES_DIR = Path("/files")
SOURCE_CFG = FILES_DIR / "serverDZ.cfg"
# CFG_TEMPLATE is deprecated - using ServerConfig.to_cfg() instead
CFG_TEMPLATE = FILES_DIR / "serverDZ.cfg.template"

# Structured config storage (JSON format, rendered to .cfg on apply)
STRUCTURED_CFG_JSON = PROFILES_DIR / "server_config.json"
STRUCTURED_SECRETS_JSON = PROFILES_DIR / "server_secrets.json"
CFG_HISTORY_DIR = PROFILES_DIR / ".config_history"


# =============================================================================
# Utility Functions
# =============================================================================


def get_app_channel(default: str | None = None) -> str:
    """Return persisted channel or a safe default.

    Order of precedence:
    1) Value in APP_CHANNEL_FILE
    2) Provided default override
    3) DEFAULT_CHANNEL (stable)
    """

    if APP_CHANNEL_FILE.exists():
        try:
            value = APP_CHANNEL_FILE.read_text().strip().lower()
            if value in VALID_CHANNELS:
                return value
        except Exception:
            pass

    if default and default.lower() in VALID_CHANNELS:
        return default.lower()

    return DEFAULT_CHANNEL


def set_app_channel(channel: str) -> tuple[bool, str]:
    """Persist channel to APP_CHANNEL_FILE."""

    if not channel or channel.lower() not in VALID_CHANNELS:
        return False, "Channel must be 'stable' or 'experimental'"

    try:
        APP_CHANNEL_FILE.write_text(channel.lower())
        return True, f"Channel set: {channel.lower()}"
    except Exception as e:
        return False, f"Failed to set channel: {e}"


def resolve_server_appid(channel: str | None = None) -> int:
    """Resolve server appid for the given channel (or current channel)."""

    effective_channel = channel.lower() if channel else get_app_channel()
    return DAYZ_SERVER_APPIDS.get(effective_channel, DAYZ_SERVER_APPIDS[DEFAULT_CHANNEL])
