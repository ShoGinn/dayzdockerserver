"""
DayZ Server - Data Models

Shared Pydantic models and dataclasses used across the application.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# =============================================================================
# Enums
# =============================================================================


class ServerState(str, Enum):
    """Server operational states (matches supervisor)"""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    CRASHED = "crashed"
    DISABLED = "disabled"
    MAINTENANCE = "maintenance"


class ServerCommand(str, Enum):
    """Commands for the supervisor"""

    START = "start"
    STOP = "stop"
    RESTART = "restart"
    ENABLE = "enable"
    DISABLE = "disable"
    MAINTENANCE = "maintenance"
    RESUME = "resume"
    STATUS = "status"  # New: get current status


# =============================================================================
# Dataclasses (internal use)
# =============================================================================


@dataclass
class ModInfo:
    """Information about an installed mod"""

    id: str
    name: str
    size: str
    installed: bool
    active: bool
    url: str = ""


@dataclass
class SupervisorState:
    """State from supervisor's state.json"""

    state: str = ServerState.STOPPED.value
    pid: int | None = None
    started_at: str | None = None
    uptime_seconds: int = 0
    restart_count: int = 0
    last_exit_code: int | None = None
    last_crash_time: str | None = None
    auto_restart: bool = True
    maintenance: bool = False
    message: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


# =============================================================================
# API Request/Response Models
# =============================================================================


class HealthResponse(BaseModel):
    """Health check response"""

    status: str = "ok"
    server_state: str
    message: str = ""


class ModResponse(BaseModel):
    """Single mod information"""

    id: str
    name: str
    url: str
    size: str
    active: bool = False


class ModListResponse(BaseModel):
    """List of mods response"""

    mods: list[ModResponse]
    count: int


class ServerStatusResponse(BaseModel):
    """Complete server status"""

    installed: bool
    state: str
    pid: int | None = None
    uptime_seconds: int = 0
    uptime_text: str = ""
    map: str = ""
    version: str = ""
    auto_restart: bool = True
    maintenance: bool = False
    restart_count: int = 0
    last_exit_code: int | None = None
    message: str = ""
    active_mods: list[ModResponse] = []


class OperationResponse(BaseModel):
    """Generic operation result"""

    success: bool
    message: str
    details: dict | None = None


class ServerParamsRequest(BaseModel):
    """Request to update server parameters.

    Supports both direct command string and individual parameter updates.
    """

    # Direct command string (takes precedence if provided)
    command_string: str | None = Field(
        default=None,
        description="Full command-line parameter string",
    )

    # Individual parameter updates
    port: int | None = Field(default=None, ge=1, le=65535, description="Server port")
    logs: bool | None = Field(
        default=None, description="Enable/disable logging (bool or 'enabled'/'disabled')"
    )
    admin_log: bool | None = Field(default=None, description="Enable admin logging")
    net_log: bool | None = Field(default=None, description="Enable network logging")
    extra_params: list[str] | None = Field(default=None, description="Additional custom parameters")


class ServerParamsResponse(BaseModel):
    """Response containing current server parameters."""

    success: bool = True
    params: dict  # ServerParams as dict
    command_string: str
    source: str  # ParamSource value


class ServerChannelRequest(BaseModel):
    """Request to set server app channel"""

    channel: str  # 'stable' or 'experimental'


class BulkModRequest(BaseModel):
    """Request to install/activate multiple mods"""

    mod_ids: list[str]

    model_config = ConfigDict(
        json_schema_extra={"example": {"mod_ids": ["1559212036", "1623711988", "1828439124"]}}
    )


class ConfigContent(BaseModel):
    """Server config content"""

    content: str


# =============================================================================
# ServerConfig Field Registry - SINGLE SOURCE OF TRUTH
# =============================================================================


@dataclass
class FieldDef:
    """Definition for a single config field"""

    default: Any
    description: str
    section: str
    field_type: str = "int"  # int, str, bool, float, list


# All fields defined once with their default, description, section, and type
CONFIG_FIELDS: dict[str, FieldDef] = {
    # Server Identity
    "hostname": FieldDef("DayZ Server Name", "Server name", "Server Identity", "str"),
    "description": FieldDef(
        "Join our Discord!",
        "Description shown in server browser (max 255 chars)",
        "Server Identity",
        "str",
    ),
    "password": FieldDef("", "Password to connect to the server", "Server Identity", "str"),
    "passwordAdmin": FieldDef("", "Password to become a server admin", "Server Identity", "str"),
    # Player Limits
    "maxPlayers": FieldDef(60, "Maximum amount of players", "Player Limits", "int"),
    "enableWhitelist": FieldDef(0, "Enable/disable whitelist (0-1)", "Player Limits", "int"),
    "disableBanlist": FieldDef(
        False, "Disable usage of ban.txt (default: false)", "Player Limits", "bool"
    ),
    "disablePrioritylist": FieldDef(
        False, "Disable usage of priority.txt (default: false)", "Player Limits", "bool"
    ),
    "disableMultiAccountMitigation": FieldDef(
        False, "Disables multi account mitigation on consoles", "Player Limits", "bool"
    ),
    # Security
    "verifySignatures": FieldDef(
        2, "Verifies .pbos against .bisign files (only 2 supported)", "Security", "int"
    ),
    "forceSameBuild": FieldDef(
        1, "Allow only clients with same exe revision (0-1)", "Security", "int"
    ),
    "allowFilePatching": FieldDef(1, "Enable clients with -filePatching", "Security", "int"),
    # Voice & Communication
    "disableVoN": FieldDef(
        0, "Enable/disable voice over network (0-1)", "Voice & Communication", "int"
    ),
    "vonCodecQuality": FieldDef(20, "VoN codec quality (0-30)", "Voice & Communication", "int"),
    # Gameplay
    "disable3rdPerson": FieldDef(0, "Toggle 3rd person view (0-1)", "Gameplay", "int"),
    "disableCrosshair": FieldDef(0, "Toggle cross-hair (0-1)", "Gameplay", "int"),
    "disablePersonalLight": FieldDef(1, "Disable personal light", "Gameplay", "int"),
    "lightingConfig": FieldDef(
        1, "0 brighter night / 1 darker night (2 Sakhal)", "Gameplay", "int"
    ),
    "disableRespawnDialog": FieldDef(0, "Disable respawn dialog", "Gameplay", "int"),
    "respawnTime": FieldDef(5, "Respawn delay in seconds", "Gameplay", "int"),
    "disableBaseDamage": FieldDef(0, "Disable fence/watchtower damage", "Gameplay", "int"),
    "disableContainerDamage": FieldDef(
        0, "Disable tents/barrels/crate/seachest damage", "Gameplay", "int"
    ),
    "enableCfgGameplayFile": FieldDef(1, "Enable cfgGameplay file override", "Gameplay", "int"),
    # Time & Weather
    "serverTime": FieldDef(
        "SystemTime", "Initial in-game time or SystemTime", "Time & Weather", "str"
    ),
    "serverTimeAcceleration": FieldDef(
        12, "Accelerated time multiplier (0.1-64)", "Time & Weather", "int"
    ),
    "serverNightTimeAcceleration": FieldDef(
        1, "Night time multiplier (0.1-64) x serverTimeAcceleration", "Time & Weather", "int"
    ),
    "serverTimePersistent": FieldDef(1, "Persist server time (0-1)", "Time & Weather", "int"),
    # View Distance
    "defaultVisibility": FieldDef(1375, "Max terrain render distance", "View Distance", "int"),
    "defaultObjectViewDistance": FieldDef(
        1375, "Max object render distance", "View Distance", "int"
    ),
    # Performance
    "simulatedPlayersBatch": FieldDef(
        20, "Players simulated per frame limit", "Performance", "int"
    ),
    "multithreadedReplication": FieldDef(
        1, "Enable multithreaded replication (0-1)", "Performance", "int"
    ),
    "enableDebugMonitor": FieldDef(0, "Show character debug window (0-1)", "Performance", "int"),
    # Login Queue
    "loginQueueConcurrentPlayers": FieldDef(5, "Concurrent logins processed", "Login Queue", "int"),
    "loginQueueMaxPlayers": FieldDef(
        500, "Max players waiting in login queue", "Login Queue", "int"
    ),
    # Network & Ping
    "guaranteedUpdates": FieldDef(
        1, "Communication protocol (use only 1)", "Network & Ping", "int"
    ),
    "pingWarning": FieldDef(
        200, "Initial yellow ping warning threshold (ms)", "Network & Ping", "int"
    ),
    "pingCritical": FieldDef(250, "Red ping warning threshold (ms)", "Network & Ping", "int"),
    "MaxPing": FieldDef(300, "Kick players above this ping (ms)", "Network & Ping", "int"),
    "speedhackDetection": FieldDef(
        1, "Speedhack detection (1 strict - 10 benevolent)", "Network & Ping", "int"
    ),
    "steamQueryPort": FieldDef(27016, "Steam query port", "Network & Ping", "int"),
    "clientPort": FieldDef(2302, "Force client connection port", "Network & Ping", "int"),
    # Network Bubble
    "networkRangeClose": FieldDef(
        20, "Network bubble distance for close objects (m)", "Network Bubble", "int"
    ),
    "networkRangeNear": FieldDef(
        150, "Bubble distance for near inventory items (m)", "Network Bubble", "int"
    ),
    "networkRangeFar": FieldDef(
        1000, "Bubble distance for far objects (m)", "Network Bubble", "int"
    ),
    "networkRangeDistantEffect": FieldDef(
        4000, "Bubble distance for effects (m)", "Network Bubble", "int"
    ),
    # Bandwidth (Advanced)
    "networkObjectBatchLogSlow": FieldDef(
        5, "Log when bubble iteration exceeds this many seconds", "Bandwidth (Advanced)", "int"
    ),
    "networkObjectBatchEnforceBandwidthLimits": FieldDef(
        1, "Limit object creation based on bandwidth stats", "Bandwidth (Advanced)", "int"
    ),
    "networkObjectBatchUseEstimatedBandwidth": FieldDef(
        0, "Use estimated bandwidth instead of actual", "Bandwidth (Advanced)", "int"
    ),
    "networkObjectBatchUseDynamicMaximumBandwidth": FieldDef(
        1, "Bandwidth limit relative to max bandwidth", "Bandwidth (Advanced)", "int"
    ),
    "networkObjectBatchBandwidthLimit": FieldDef(
        0.8, "Bandwidth limit factor or hard limit", "Bandwidth (Advanced)", "float"
    ),
    "networkObjectBatchCompute": FieldDef(
        1000, "Objects checked in create/destroy lists per frame", "Bandwidth (Advanced)", "int"
    ),
    "networkObjectBatchSendCreate": FieldDef(
        10, "Max objects sent for creation per frame", "Bandwidth (Advanced)", "int"
    ),
    "networkObjectBatchSendDelete": FieldDef(
        10, "Max objects sent for deletion per frame", "Bandwidth (Advanced)", "int"
    ),
    # Storage & Persistence
    "instanceId": FieldDef(
        1, "Server instance id for storage folders", "Storage & Persistence", "int"
    ),
    "storageAutoFix": FieldDef(
        1, "Auto-replace corrupted persistence files (0-1)", "Storage & Persistence", "int"
    ),
    "lootHistory": FieldDef(
        1, "Number of persistence history files", "Storage & Persistence", "int"
    ),
    "storeHouseStateDisabled": FieldDef(
        False, "Disable houses/doors persistence", "Storage & Persistence", "bool"
    ),
    # Logging
    "logFile": FieldDef("server_console.log", "Server console log file name", "Logging", "str"),
    "timeStampFormat": FieldDef("Short", "RPT timestamps format (Full/Short)", "Logging", "str"),
    "logAverageFps": FieldDef(1, "Log average FPS interval (requires -doLogs)", "Logging", "int"),
    "logMemory": FieldDef(1, "Log memory usage interval (requires -doLogs)", "Logging", "int"),
    "logPlayers": FieldDef(1, "Log player count interval (requires -doLogs)", "Logging", "int"),
    "serverFpsWarning": FieldDef(15, "Yellow/red server FPS warning threshold", "Logging", "int"),
    "adminLogPlayerHitsOnly": FieldDef(
        0, "1: log player hits only / 0: log all hits", "Logging", "int"
    ),
    "adminLogPlacement": FieldDef(1, "Log placement actions", "Logging", "int"),
    "adminLogBuildActions": FieldDef(1, "Log basebuilding actions", "Logging", "int"),
    "adminLogPlayerList": FieldDef(1, "Log periodic player list", "Logging", "int"),
    # MOTD
    "motd": FieldDef(
        ["Welcome to the Server", "Join our Discord"], "Message of the day lines", "MOTD", "list"
    ),
    "motdInterval": FieldDef(300, "Seconds between motd messages", "MOTD", "int"),
    # Mission
    "missionTemplate": FieldDef(
        "dayzOffline.chernarusplus",
        "Mission template (e.g., dayzOffline.chernarusplus)",
        "Mission",
        "str",
    ),
}


# Derive helpers from the single source
def get_cfg_comments() -> dict[str, str]:
    """Get field descriptions for cfg comments"""
    return {k: v.description for k, v in CONFIG_FIELDS.items()}


def get_field_sections() -> dict[str, list[str]]:
    """Get fields organized by section"""
    sections: dict[str, list[str]] = {}
    for field_name, field_def in CONFIG_FIELDS.items():
        if field_def.section not in sections:
            sections[field_def.section] = []
        sections[field_def.section].append(field_name)
    return sections


def get_field_defaults() -> dict[str, Any]:
    """Get default values for all fields"""
    return {k: v.default for k, v in CONFIG_FIELDS.items()}


# Section order for cfg rendering (matches UI order)
SECTION_ORDER = [
    "Server Identity",
    "Player Limits",
    "Security",
    "Voice & Communication",
    "Gameplay",
    "Time & Weather",
    "View Distance",
    "Performance",
    "Login Queue",
    "Network & Ping",
    "Network Bubble",
    "Bandwidth (Advanced)",
    "Storage & Persistence",
    "Logging",
    "MOTD",
    "Mission",
]

# Default immutable keys per Bohemia guidance
DEFAULT_IMMUTABLE_KEYS: set[str] = {"verifySignatures"}


class ServerConfig(BaseModel):
    """Explicit serverDZ.cfg configuration model with renderer.

    Field definitions come from CONFIG_FIELDS (single source of truth).
    """

    # All fields with defaults from CONFIG_FIELDS
    hostname: str = CONFIG_FIELDS["hostname"].default
    description: str = CONFIG_FIELDS["description"].default
    password: str = CONFIG_FIELDS["password"].default
    passwordAdmin: str = CONFIG_FIELDS["passwordAdmin"].default
    maxPlayers: int = CONFIG_FIELDS["maxPlayers"].default
    enableWhitelist: int = CONFIG_FIELDS["enableWhitelist"].default
    disableBanlist: bool = CONFIG_FIELDS["disableBanlist"].default
    disablePrioritylist: bool = CONFIG_FIELDS["disablePrioritylist"].default
    disableMultiAccountMitigation: bool = CONFIG_FIELDS["disableMultiAccountMitigation"].default
    verifySignatures: int = CONFIG_FIELDS["verifySignatures"].default
    forceSameBuild: int = CONFIG_FIELDS["forceSameBuild"].default
    allowFilePatching: int = CONFIG_FIELDS["allowFilePatching"].default
    disableVoN: int = CONFIG_FIELDS["disableVoN"].default
    vonCodecQuality: int = CONFIG_FIELDS["vonCodecQuality"].default
    disable3rdPerson: int = CONFIG_FIELDS["disable3rdPerson"].default
    disableCrosshair: int = CONFIG_FIELDS["disableCrosshair"].default
    disablePersonalLight: int = CONFIG_FIELDS["disablePersonalLight"].default
    lightingConfig: int = CONFIG_FIELDS["lightingConfig"].default
    disableRespawnDialog: int = CONFIG_FIELDS["disableRespawnDialog"].default
    respawnTime: int = CONFIG_FIELDS["respawnTime"].default
    disableBaseDamage: int = CONFIG_FIELDS["disableBaseDamage"].default
    disableContainerDamage: int = CONFIG_FIELDS["disableContainerDamage"].default
    enableCfgGameplayFile: int = CONFIG_FIELDS["enableCfgGameplayFile"].default
    serverTime: str = CONFIG_FIELDS["serverTime"].default
    serverTimeAcceleration: int = CONFIG_FIELDS["serverTimeAcceleration"].default
    serverNightTimeAcceleration: int = CONFIG_FIELDS["serverNightTimeAcceleration"].default
    serverTimePersistent: int = CONFIG_FIELDS["serverTimePersistent"].default
    defaultVisibility: int = CONFIG_FIELDS["defaultVisibility"].default
    defaultObjectViewDistance: int = CONFIG_FIELDS["defaultObjectViewDistance"].default
    simulatedPlayersBatch: int = CONFIG_FIELDS["simulatedPlayersBatch"].default
    multithreadedReplication: int = CONFIG_FIELDS["multithreadedReplication"].default
    enableDebugMonitor: int = CONFIG_FIELDS["enableDebugMonitor"].default
    loginQueueConcurrentPlayers: int = CONFIG_FIELDS["loginQueueConcurrentPlayers"].default
    loginQueueMaxPlayers: int = CONFIG_FIELDS["loginQueueMaxPlayers"].default
    guaranteedUpdates: int = CONFIG_FIELDS["guaranteedUpdates"].default
    pingWarning: int = CONFIG_FIELDS["pingWarning"].default
    pingCritical: int = CONFIG_FIELDS["pingCritical"].default
    MaxPing: int = CONFIG_FIELDS["MaxPing"].default
    speedhackDetection: int = CONFIG_FIELDS["speedhackDetection"].default
    steamQueryPort: int = CONFIG_FIELDS["steamQueryPort"].default
    clientPort: int = CONFIG_FIELDS["clientPort"].default
    networkRangeClose: int = CONFIG_FIELDS["networkRangeClose"].default
    networkRangeNear: int = CONFIG_FIELDS["networkRangeNear"].default
    networkRangeFar: int = CONFIG_FIELDS["networkRangeFar"].default
    networkRangeDistantEffect: int = CONFIG_FIELDS["networkRangeDistantEffect"].default
    networkObjectBatchLogSlow: int = CONFIG_FIELDS["networkObjectBatchLogSlow"].default
    networkObjectBatchEnforceBandwidthLimits: int = CONFIG_FIELDS[
        "networkObjectBatchEnforceBandwidthLimits"
    ].default
    networkObjectBatchUseEstimatedBandwidth: int = CONFIG_FIELDS[
        "networkObjectBatchUseEstimatedBandwidth"
    ].default
    networkObjectBatchUseDynamicMaximumBandwidth: int = CONFIG_FIELDS[
        "networkObjectBatchUseDynamicMaximumBandwidth"
    ].default
    networkObjectBatchBandwidthLimit: float = CONFIG_FIELDS[
        "networkObjectBatchBandwidthLimit"
    ].default
    networkObjectBatchCompute: int = CONFIG_FIELDS["networkObjectBatchCompute"].default
    networkObjectBatchSendCreate: int = CONFIG_FIELDS["networkObjectBatchSendCreate"].default
    networkObjectBatchSendDelete: int = CONFIG_FIELDS["networkObjectBatchSendDelete"].default
    instanceId: int = CONFIG_FIELDS["instanceId"].default
    storageAutoFix: int = CONFIG_FIELDS["storageAutoFix"].default
    lootHistory: int = CONFIG_FIELDS["lootHistory"].default
    storeHouseStateDisabled: bool = CONFIG_FIELDS["storeHouseStateDisabled"].default
    logFile: str = CONFIG_FIELDS["logFile"].default
    timeStampFormat: str = CONFIG_FIELDS["timeStampFormat"].default
    logAverageFps: int = CONFIG_FIELDS["logAverageFps"].default
    logMemory: int = CONFIG_FIELDS["logMemory"].default
    logPlayers: int = CONFIG_FIELDS["logPlayers"].default
    serverFpsWarning: int = CONFIG_FIELDS["serverFpsWarning"].default
    adminLogPlayerHitsOnly: int = CONFIG_FIELDS["adminLogPlayerHitsOnly"].default
    adminLogPlacement: int = CONFIG_FIELDS["adminLogPlacement"].default
    adminLogBuildActions: int = CONFIG_FIELDS["adminLogBuildActions"].default
    adminLogPlayerList: int = CONFIG_FIELDS["adminLogPlayerList"].default
    motd: list[str] = CONFIG_FIELDS["motd"].default
    motdInterval: int = CONFIG_FIELDS["motdInterval"].default
    missionTemplate: str = CONFIG_FIELDS["missionTemplate"].default

    # Internal fields (not from CONFIG_FIELDS)
    custom_lines: list[str] = []
    immutable_keys: set[str] = DEFAULT_IMMUTABLE_KEYS

    model_config = ConfigDict(extra="allow")

    # Validators
    @field_validator("verifySignatures")
    @classmethod
    def _enforce_verify_signatures(cls, v: int) -> int:
        return 2  # Bohemia docs: only 2 is supported

    @field_validator(
        "enableWhitelist",
        "forceSameBuild",
        "disableVoN",
        "disable3rdPerson",
        "disableCrosshair",
        "serverTimePersistent",
        "guaranteedUpdates",
        "storageAutoFix",
        "adminLogPlayerHitsOnly",
        "adminLogPlacement",
        "adminLogBuildActions",
        "adminLogPlayerList",
        "enableDebugMonitor",
        "allowFilePatching",
        "multithreadedReplication",
        "disablePersonalLight",
        "disableBaseDamage",
        "disableContainerDamage",
        "disableRespawnDialog",
        "enableCfgGameplayFile",
        mode="before",
    )
    @classmethod
    def _coerce_bool_to_int(cls, v: int | bool) -> int:
        if isinstance(v, bool):
            return 1 if v else 0
        return int(v)

    def to_cfg(self) -> str:
        """Render to serverDZ.cfg text."""
        comments = get_cfg_comments()

        def _fmt_value(val: object) -> str:
            if isinstance(val, bool):
                return "true" if val else "false"
            if isinstance(val, str):
                return f'"{val}"'
            return str(val)

        lines: list[str] = []
        data = self.model_dump()
        sections = get_field_sections()

        # Render sections in order
        for section_name in SECTION_ORDER:
            if section_name not in sections:
                continue
            keys = sections[section_name]
            present = [k for k in keys if k in data and k != "missionTemplate"]
            if not present:
                continue

            lines.append("")
            lines.append(f"// === {section_name} ===")

            for key in present:
                if key == "motd":
                    arr = data.get("motd") or []
                    motd_vals = ", ".join(f'"{s}"' for s in arr)
                    comment = comments.get("motd", "")
                    lines.append(f"motd[] = {{{motd_vals}}};{' // ' + comment if comment else ''}")
                else:
                    comment = comments.get(key, "")
                    lines.append(
                        f"{key} = {_fmt_value(data[key])};{' // ' + comment if comment else ''}"
                    )

        # Extra keys (mod-specific)
        known_keys = set(CONFIG_FIELDS.keys()) | {"custom_lines", "immutable_keys"}
        extra_keys = [k for k in data if k not in known_keys]
        if extra_keys:
            lines.append("")
            lines.append("// === Extra/Mod Settings ===")
            for k in sorted(extra_keys):
                if k in (self.immutable_keys or set()):
                    continue
                lines.append(f"{k} = {_fmt_value(data[k])};")

        # Missions block
        lines.append("")
        lines.append("// Mission to load on server startup. <MissionName>.<TerrainName>")
        lines.append("class Missions")
        lines.append("{")
        lines.append("    class DayZ")
        lines.append("    {")
        lines.append(f'        template="{self.missionTemplate}";')
        lines.append("    };")
        lines.append("};")

        # Custom lines
        if self.custom_lines:
            lines.append("")
            lines.append("// Custom lines appended by user/mods")
            for line in self.custom_lines:
                stripped = line.strip()
                if "=" in stripped:
                    key = stripped.split("=", 1)[0].strip().rstrip("[]")
                    if key in (self.immutable_keys or set()):
                        lines.append(f"// (blocked immutable) {line}")
                        continue
                lines.append(line)

        return "\n".join(lines) + "\n"

    @classmethod
    def from_cfg(cls, cfg_content: str) -> "ServerConfig":
        """Parse a serverDZ.cfg file and return a ServerConfig instance."""
        import re

        data: dict[str, object] = {}

        def strip_inline_comments(line: str) -> str:
            result = []
            in_quotes = False
            i = 0
            while i < len(line):
                char = line[i]
                if char == '"' and (i == 0 or line[i - 1] != "\\"):
                    in_quotes = not in_quotes
                    result.append(char)
                elif char == "/" and not in_quotes and i + 1 < len(line) and line[i + 1] == "/":
                    break
                else:
                    result.append(char)
                i += 1
            return "".join(result)

        processed_lines = []
        for line in cfg_content.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            processed = strip_inline_comments(line)
            if processed.strip():
                processed_lines.append(processed)

        processed_content = "\n".join(processed_lines)

        simple_pattern = re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+?)\s*;", re.MULTILINE)
        array_pattern = re.compile(
            r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\[\]\s*=\s*\{([^}]*)\}\s*;", re.MULTILINE
        )
        mission_pattern = re.compile(
            r'class\s+Missions\s*\{[^}]*?template\s*=\s*"([^"]+)"', re.IGNORECASE | re.DOTALL
        )

        def parse_value(val_str: str) -> object:
            val_str = val_str.strip()
            if val_str.startswith('"') and val_str.endswith('"'):
                return val_str[1:-1]
            if val_str.startswith('"'):
                end_quote = val_str.find('"', 1)
                if end_quote > 0:
                    return val_str[1:end_quote]
            if val_str.lower() == "true":
                return True
            if val_str.lower() == "false":
                return False
            try:
                return int(val_str)
            except ValueError:
                pass
            try:
                return float(val_str)
            except ValueError:
                pass
            return val_str

        def parse_array(arr_str: str) -> list[str]:
            return [m.group(1) for m in re.finditer(r'"([^"]*)"', arr_str)]

        for match in array_pattern.finditer(processed_content):
            data[match.group(1)] = parse_array(match.group(2))

        for match in simple_pattern.finditer(processed_content):
            key = match.group(1)
            if key in data or key.lower() == "class" or key == "template":
                continue
            data[key] = parse_value(match.group(2))

        mission_match = mission_pattern.search(processed_content)
        if mission_match:
            data["missionTemplate"] = mission_match.group(1).strip()

        return cls.model_validate(data)

    @classmethod
    def from_cfg_file(cls, path: Path) -> "ServerConfig":
        if isinstance(path, str):
            path = Path(path)
        return cls.from_cfg(path.read_text(encoding="utf-8", errors="replace"))

    @classmethod
    def get_field_description(cls, field_name: str) -> str | None:
        if field_name in CONFIG_FIELDS:
            return CONFIG_FIELDS[field_name].description
        return None

    @classmethod
    def get_all_descriptions(cls) -> dict[str, str]:
        return get_cfg_comments()

    @classmethod
    def get_field_sections(cls) -> dict[str, list[str]]:
        return get_field_sections()


class SteamLoginRequest(BaseModel):
    """Steam login configuration"""

    username: str


class SteamLoginStatus(BaseModel):
    """Steam login status"""

    configured: bool
    masked_username: str | None = None
    note: str | None = None


class SteamCachedConfigRequest(BaseModel):
    """Payload for importing Steam cached credentials config.vdf content"""

    content: str
    username: str | None = None
