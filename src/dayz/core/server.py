"""
DayZ Server - Server Control (Socket-Based)

Updated to use Unix socket communication instead of control files.
"""

import contextlib
import json
import re
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime
from functools import cached_property
from pathlib import Path

from dayz.config.models import ServerCommand, ServerConfig, ServerState, SupervisorState
from dayz.config.paths import (
    CFG_HISTORY_DIR,
    CONTROL_DIR,
    MAINTENANCE_FILE,
    MPMISSIONS_ACTIVE,
    MPMISSIONS_UPSTREAM,
    PROFILES_DIR,
    SERVER_BINARY,
    SERVER_CFG,
    SERVER_FILES,
    SERVER_PARAMS_FILE,
    SOURCE_CFG,
    STATE_FILE,
    STRUCTURED_CFG_JSON,
    STRUCTURED_SECRETS_JSON,
    get_app_channel,
    set_app_channel,
)
from dayz.core.mods import ModManager
from dayz.core.params import (
    LogMode,
    ParamSource,
    ServerParams,
    ServerParamsUpdate,
    compose_server_params,
    parse_server_params,
)
from dayz.core.steam import SteamCMD
from dayz.services.supervisor import DayZSupervisorClient
from dayz.utils.file_utils import categorize_cleanup_file, format_uptime, get_dir_size, human_size
from dayz.utils.server_version import extract_dayz_version
from dayz.utils.text_utils import extract_template_from_config, mask_password_in_config


class ServerControl:
    """Controls server via supervisor socket IPC"""

    def __init__(self) -> None:
        self.client = DayZSupervisorClient()

    def _send_command(self, command: ServerCommand) -> tuple[bool, str]:
        """Send command to supervisor via socket"""
        response = self.client._send_command(command.value)
        return response.success, response.message

    def start(self) -> tuple[bool, str]:
        """Start the server"""
        return self._send_command(ServerCommand.START)

    def stop(self) -> tuple[bool, str]:
        """Stop the server"""
        return self._send_command(ServerCommand.STOP)

    def restart(self) -> tuple[bool, str]:
        """Restart the server"""
        return self._send_command(ServerCommand.RESTART)

    def enable_auto_restart(self) -> tuple[bool, str]:
        """Enable auto-restart on crash"""
        return self._send_command(ServerCommand.ENABLE)

    def disable_auto_restart(self) -> tuple[bool, str]:
        """Disable auto-restart (useful for updates)"""
        return self._send_command(ServerCommand.DISABLE)

    def enable_maintenance(self) -> tuple[bool, str]:
        """Enter maintenance mode (stop server, prevent auto-start)"""
        return self._send_command(ServerCommand.MAINTENANCE)

    def disable_maintenance(self) -> tuple[bool, str]:
        """Exit maintenance mode"""
        return self._send_command(ServerCommand.RESUME)

    def get_state(self) -> SupervisorState:
        """Get current supervisor state via socket (with fallback to file)"""
        response = self.client._send_command(ServerCommand.STATUS.value)

        if response.success and response.state:
            try:
                return SupervisorState(**response.state)
            except Exception:
                pass  # Fall through to file-based fallback

        # Fallback: read state file (for backward compatibility)
        if STATE_FILE.exists():
            try:
                return SupervisorState(**json.loads(STATE_FILE.read_text()))
            except Exception as e:
                return SupervisorState(message=f"Failed to read state: {e}")

        # No state available
        fallback = SupervisorState(message="State file not found")
        if MAINTENANCE_FILE.exists():
            fallback.maintenance = True
            fallback.state = ServerState.MAINTENANCE.value
            fallback.message = "Maintenance mode enabled (no state file)"
        return fallback


class ServerManager:
    """High-level server management operations"""

    def __init__(self) -> None:
        self.steamcmd: SteamCMD = SteamCMD()
        self.mod_manager: ModManager = ModManager()
        self.control: ServerControl = ServerControl()
        self._ensure_config()

    # =========================================================================
    # Installation & Updates
    # =========================================================================

    def is_installed(self) -> bool:
        """Check if DayZ server is installed"""
        return SERVER_BINARY.exists()

    def install(self) -> tuple[bool, str]:
        """Install DayZ server files"""
        success, output = self.steamcmd.install_server()
        return success, output[-1000:] if len(output) > 1000 else output

    def update(self) -> tuple[bool, str]:
        """Update DayZ server files"""
        self.control.stop()
        success, output = self.steamcmd.update_server()
        return success, output[-1000:] if len(output) > 1000 else output

    def uninstall(self) -> tuple[bool, str]:
        """Uninstall DayZ server files (container-safe)"""
        self.control.stop()
        try:
            if SERVER_FILES.exists():
                shutil.rmtree(SERVER_FILES)
            SERVER_FILES.mkdir(parents=True, exist_ok=True)
            return True, "Server uninstalled"
        except Exception as e:
            return False, f"Failed to uninstall: {e}"

    # =========================================================================
    # Server Control
    # =========================================================================

    def _pre_start_actions(self) -> tuple[bool, str]:
        """Perform pre-start checks and actions like mod sync"""
        if not self.is_installed():
            return False, "Server not installed"

        state = self.control.get_state()
        if state.maintenance:
            return False, "Maintenance mode enabled, operation blocked"

        self.mod_manager.pre_start_mod_sync()
        return True, "Pre-start actions completed"

    def start(self) -> tuple[bool, str]:
        """Start the server"""
        if success_msg := self._pre_start_actions():
            success, message = success_msg
            if not success:
                return False, message
        return self.control.start()

    def stop(self) -> tuple[bool, str]:
        """Stop the server"""
        return self.control.stop()

    def restart(self) -> tuple[bool, str]:
        """Restart the server"""
        if success_msg := self._pre_start_actions():
            success, message = success_msg
            if not success:
                return False, message
        return self.control.restart()

    # =========================================================================
    # Server Params & Channel
    # =========================================================================

    def get_server_params_obj(self) -> tuple[ServerParams, ParamSource]:
        """Get current server params as Pydantic model with source.

        Returns:
            (ServerParams, source) where source indicates parameter origin
        """
        # Check for override file
        if SERVER_PARAMS_FILE.exists():
            cmd_string = SERVER_PARAMS_FILE.read_text().strip()
            if cmd_string:
                return parse_server_params(cmd_string), ParamSource.OVERRIDE

        # Return defaults
        return ServerParams(), ParamSource.DEFAULT

    def get_server_params_dict(self) -> dict:
        """Get server params as dictionary for API responses."""
        params, source = self.get_server_params_obj()
        return {
            "params": params.model_dump(),
            "command_string": params.to_command_string(),
            "source": source.value,
        }

    def update_server_params(
        self,
        *,
        command_string: str | None = None,
        port: int | None = None,
        logs: LogMode | bool | None = None,
        admin_log: bool | None = None,
        net_log: bool | None = None,
        extra_params: list[str] | None = None,
    ) -> tuple[bool, str, ServerParams]:
        """Update server parameters.

        If command_string is provided, use it directly.
        Otherwise, apply partial updates to current params.

        Args:
            command_string: Full command-line parameter string
            port: Server port (1-65535)
            logs: Enable/disable logging (bool or LogMode enum)
            admin_log: Enable admin logging
            net_log: Enable network logging
            extra_params: Additional custom parameters

        Returns:
            (success, message, updated_params)
        """
        try:
            if command_string:
                # Direct command string provided
                params = parse_server_params(command_string)
            else:
                # Get current params
                current_params, _ = self.get_server_params_obj()

                # Create update request - Pydantic handles validation
                update = ServerParamsUpdate(
                    port=port,
                    logs=logs,
                    admin_log=admin_log,
                    net_log=net_log,
                    extra_params=extra_params,
                )

                # Check if anything was actually set
                if not update.model_dump(exclude_unset=True):
                    return False, "No parameters to update", current_params

                # Apply update
                params = update.apply_to(current_params)

            # Validate and write
            cmd_string = params.to_command_string()

            # Write to override file
            CONTROL_DIR.mkdir(parents=True, exist_ok=True)
            SERVER_PARAMS_FILE.write_text(cmd_string)

            return True, "Server parameters updated", params

        except Exception as e:
            return False, f"Failed to update parameters: {e}", ServerParams()

    def clear_server_params_override(self) -> tuple[bool, str]:
        """Clear server params override, reverting to defaults."""
        try:
            if SERVER_PARAMS_FILE.exists():
                SERVER_PARAMS_FILE.unlink()
            return True, "Server params override cleared"
        except Exception as e:
            return False, f"Failed to clear override: {e}"

    # =========================================================================
    # Server Params - Legacy API (Backward Compatibility)
    # =========================================================================

    def get_server_params(self) -> str:
        """Get current server params override string.

        Legacy method - prefer get_server_params_obj() for new code.
        """
        return SERVER_PARAMS_FILE.read_text().strip() if SERVER_PARAMS_FILE.exists() else ""

    def get_effective_server_params(self) -> tuple[str, str]:
        """Return (effective_params, source).

        Legacy method - prefer get_server_params_obj() for new code.
        """
        params, source = self.get_server_params_obj()
        return params.to_command_string(), source.value

    def build_base_params(
        self,
        *,
        port: int | None = None,
        enable_logs: bool | None = None,
        admin_log: bool | None = None,
        net_log: bool | None = None,
    ) -> str:
        """Compose params string using known paths and toggles.

        Legacy method - prefer update_server_params() for new code.
        """
        return compose_server_params(
            port=port,
            enable_logs=enable_logs,
            admin_log=admin_log,
            net_log=net_log,
        )

    def set_server_params(self, params: str) -> tuple[bool, str]:
        """Set server params override.

        Legacy method - prefer update_server_params() for new code.
        """
        params = (params or "").strip()
        try:
            CONTROL_DIR.mkdir(parents=True, exist_ok=True)
            if params:
                SERVER_PARAMS_FILE.write_text(params)
            else:
                SERVER_PARAMS_FILE.unlink(missing_ok=True)
            return True, "Server params updated"
        except Exception as e:
            return False, f"Failed to set params: {e}"

    # =========================================================================
    # Server Channel
    # =========================================================================

    def get_channel(self) -> str:
        """Get current app channel ('stable' or 'experimental')"""
        return get_app_channel()

    def set_channel(self, channel: str) -> tuple[bool, str]:
        """Set app channel and persist to control file"""
        return set_app_channel((channel or "").strip())

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> dict:
        """Get complete server status"""
        state = self.control.get_state()

        return {
            "installed": self.is_installed(),
            "state": state.state,
            "pid": state.pid,
            "uptime_seconds": state.uptime_seconds,
            "uptime_text": format_uptime(state.uptime_seconds),
            "map": self._get_map_name(),
            "version": self._get_version(),
            "auto_restart": state.auto_restart,
            "maintenance": state.maintenance,
            "restart_count": state.restart_count,
            "last_exit_code": state.last_exit_code,
            "message": state.message,
            "active_mods": self._get_active_mods_info(state),
        }

    def _get_active_mods_info(self, state: SupervisorState) -> list[dict]:
        """Get active mods info if server is running"""
        if state.state != ServerState.RUNNING.value:
            return []

        return [
            {
                "id": m.id,
                "name": m.name,
                "url": m.url,
                "size": m.size,
                "active": True,
            }
            for m in self.mod_manager.list_active_mods()
        ]

    def enable_maintenance(self) -> tuple[bool, str]:
        """Enter maintenance mode (blocks auto-start/auto-restart)"""
        return self.control.enable_maintenance()

    def disable_maintenance(self) -> tuple[bool, str]:
        """Exit maintenance mode and re-enable normal behavior"""
        return self.control.disable_maintenance()

    def _get_map_name(self) -> str:
        """Get current map from config"""
        if not SERVER_CFG.exists():
            return "<not configured>"

        try:
            content = SERVER_CFG.read_text()
            if template := extract_template_from_config(content):
                return template
        except Exception:
            pass
        return "<not configured>"

    def _get_version(self) -> str:
        """Get server version, prefer binary extractor, fallback to RPT"""
        if not SERVER_BINARY.exists():
            return "Not installed"

        # Primary: parse binary with extractor
        try:
            if version := extract_dayz_version(str(SERVER_BINARY)):
                return version
        except Exception:
            pass

        # Fallback: parse from the most recent RPT
        if latest_rpt := self._latest_rpt:
            try:
                with latest_rpt.open("r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if match := re.search(r"^Version\s+([0-9]+\.[0-9]+\.[0-9]+)", line):
                            return match.group(1)
            except Exception:
                pass

        # Last resort: try strings command
        try:
            result = subprocess.run(
                ["strings", str(SERVER_BINARY)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if match := re.search(r"(\d+\.\d+\.\d+)", result.stdout):
                return match.group(1)
        except Exception:
            pass

        return "Unknown"

    @cached_property
    def _latest_rpt(self) -> Path | None:
        """Find the most recent RPT file in profiles (cached)"""
        try:
            rpt_files = [*PROFILES_DIR.glob("*.RPT"), *PROFILES_DIR.glob("*.rpt")]
            return max(rpt_files, key=lambda p: p.stat().st_mtime) if rpt_files else None
        except Exception:
            return None

    # =========================================================================
    # Configuration
    # =========================================================================

    def _ensure_config(self) -> None:
        """Ensure server config exists"""
        if SERVER_CFG.exists():
            return

        if STRUCTURED_CFG_JSON.exists():
            try:
                # Load the JSON config data and apply it
                data = json.loads(STRUCTURED_CFG_JSON.read_text())
                self.apply_structured_config(data)
                return
            except Exception as e:
                # If JSON is invalid, fall through to SOURCE_CFG fallback
                print(f"Warning: Failed to load structured config: {e}")

        if SOURCE_CFG.exists():
            PROFILES_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SOURCE_CFG, SERVER_CFG)
            return

        # No config sources available - create default config
        try:
            default_config = ServerConfig()
            self.save_server_config(default_config)
        except Exception as e:
            print(f"Warning: Failed to create default config: {e}")

    def get_config(self, mask_secrets: bool = True) -> tuple[bool, str, str | None]:
        """Read current server config"""
        if not SERVER_CFG.exists():
            return False, "Config not found", None

        try:
            content = SERVER_CFG.read_text()
            if mask_secrets:
                content = mask_password_in_config(content)
            return True, "Config loaded", content
        except Exception as e:
            return False, f"Failed to read config: {e}", None

    def update_config(self, content: str) -> tuple[bool, str]:
        """Update server config"""
        if not content:
            return False, "Content cannot be empty"

        try:
            PROFILES_DIR.mkdir(parents=True, exist_ok=True)
            SERVER_CFG.write_text(content)
            return True, "Config updated"
        except Exception as e:
            return False, f"Failed to update config: {e}"

    # =========================================================================
    # Structured Config (using ServerConfig model)
    # =========================================================================

    def get_server_config(self) -> tuple[bool, str, ServerConfig | None]:
        """Load server config from serverDZ.cfg (source of truth)"""
        if SERVER_CFG.exists():
            try:
                config = ServerConfig.from_cfg_file(SERVER_CFG)
                return True, "Loaded from cfg", config
            except Exception as e:
                return False, f"Failed to parse serverDZ.cfg: {e}", None

        return True, "No config found (using defaults)", ServerConfig()

    def save_server_config(self, config: ServerConfig) -> tuple[bool, str]:
        """Save ServerConfig to both JSON and cfg files (keeps them in sync)"""
        try:
            PROFILES_DIR.mkdir(parents=True, exist_ok=True)

            # Save JSON (backup/programmatic access)
            data = config.model_dump(exclude={"immutable_keys"})
            STRUCTURED_CFG_JSON.write_text(json.dumps(data, indent=2))

            # Render and save cfg (source of truth)
            rendered = config.to_cfg()
            SERVER_CFG.write_text(rendered)

            # Save history
            self._save_config_history(rendered)

            return True, "Config saved (json + cfg synced)"
        except Exception as e:
            return False, f"Failed to save config: {e}"

    def apply_server_config(self, config: ServerConfig | None = None) -> tuple[bool, str]:
        """Apply config - just calls save_server_config since they're now the same"""
        if config is None:
            success, msg, config = self.get_server_config()
            if not success or config is None:
                return False, msg

        # Merge secrets overlay if exists
        if STRUCTURED_SECRETS_JSON.exists():
            try:
                secrets = json.loads(STRUCTURED_SECRETS_JSON.read_text())
                for key, value in secrets.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
            except Exception:
                pass

        return self.save_server_config(config)

    # Legacy methods for backward compatibility
    def get_structured_config(self) -> tuple[bool, str, dict]:
        """Load structured config JSON (legacy interface)"""
        success, msg, config = self.get_server_config()
        if not success or config is None:
            return False, msg, {}
        return True, msg, config.model_dump(exclude={"immutable_keys"})

    def save_structured_config(self, data: dict) -> tuple[bool, str]:
        """Save structured config JSON (legacy interface)"""
        try:
            config = ServerConfig(**data)
            return self.save_server_config(config)
        except Exception as e:
            return False, f"Invalid config data: {e}"

    def apply_structured_config(self, data: dict | None = None) -> tuple[bool, str]:
        """Apply structured config (legacy interface)"""
        if data is None:
            return self.apply_server_config(None)
        try:
            config = ServerConfig(**data)
            return self.apply_server_config(config)
        except Exception as e:
            return False, f"Invalid config data: {e}"

    def _save_config_history(self, content: str) -> None:
        """Save config to history"""
        try:
            CFG_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            (CFG_HISTORY_DIR / f"{timestamp}.cfg").write_text(content)
        except Exception:
            pass

    # =========================================================================
    # MPMissions
    # =========================================================================

    def setup_mpmissions(self) -> tuple[bool, str]:
        """Copy pristine mpmissions if needed"""
        map_name = self._get_map_name()
        dst = MPMISSIONS_ACTIVE / map_name
        src = MPMISSIONS_UPSTREAM / map_name

        if dst.exists():
            return True, "MPMissions already set up"

        if not src.exists():
            return False, f"Source mpmissions not found: {src}"

        try:
            shutil.copytree(src, dst)
            return True, f"Copied {map_name} mpmissions"
        except Exception as e:
            return False, f"Failed to copy mpmissions: {e}"

    # =========================================================================
    # Storage Management
    # =========================================================================

    def get_storage_info(self) -> dict:
        """Get information about storage directories"""
        map_name = self._get_map_name()
        mission_dir = MPMISSIONS_ACTIVE / map_name

        storage_dirs = []
        total_size = 0

        if mission_dir.exists():
            for item in mission_dir.iterdir():
                if item.is_dir() and item.name.startswith("storage_"):
                    size = get_dir_size(item)
                    file_count = sum(1 for _ in item.rglob("*") if _.is_file())

                    storage_dirs.append(
                        {
                            "name": item.name,
                            "path": str(item),
                            "size_bytes": size,
                            "size_human": human_size(size),
                            "file_count": file_count,
                        }
                    )
                    total_size += size

        return {
            "map": map_name,
            "mission_dir": str(mission_dir),
            "storage_dirs": storage_dirs,
            "total_size_bytes": total_size,
            "total_size_human": human_size(total_size),
        }

    # =========================================================================
    # Logs
    # =========================================================================

    def list_log_files(self) -> list[dict]:
        """List available log-like files in profiles"""
        if not PROFILES_DIR.exists():
            return []

        log_files = (
            item
            for item in PROFILES_DIR.iterdir()
            if item.is_file() and item.suffix.lower() in (".log", ".rpt", ".adm")
        )

        return sorted(
            (
                {
                    "name": item.name,
                    "path": str(item),
                    "size_bytes": (size := item.stat().st_size),
                    "size_human": human_size(size),
                }
                for item in log_files
            ),
            key=lambda f: f["name"],
        )

    def read_log_tail(
        self, filename: str | None = None, bytes_count: int = 20000
    ) -> tuple[bool, str, str]:
        """Read last N bytes from a log file. Default to config 'logFile'"""
        path: Path | None = None

        if filename:
            path = PROFILES_DIR / filename if not filename.startswith("/") else Path(filename)
        else:
            success, _, cfg = self.get_server_config()
            if success and cfg and getattr(cfg, "logFile", None):
                path = PROFILES_DIR / cfg.logFile

        if not path or not path.is_file():
            return False, "Log file not found", ""

        try:
            size = path.stat().st_size
            start = max(0, size - max(0, bytes_count))
            content = path.read_bytes()[start:].decode("utf-8", errors="replace")
            return True, f"Read {len(content)} bytes", content
        except Exception as e:
            return False, f"Failed to read log: {e}", ""

    def wipe_storage(self, storage_name: str | None = None) -> tuple[bool, str]:
        """Wipe player/world storage (persistence data)"""
        state = self.control.get_state()
        if state.state == ServerState.RUNNING.value:
            return False, "Server must be stopped before wiping storage"

        map_name = self._get_map_name()
        mission_dir = MPMISSIONS_ACTIVE / map_name

        if not mission_dir.exists():
            return False, f"Mission directory not found: {mission_dir}"

        wiped = []
        errors = []

        storage_dirs = (
            [mission_dir / storage_name]
            if storage_name
            else [
                item
                for item in mission_dir.iterdir()
                if item.is_dir() and item.name.startswith("storage_")
            ]
        )

        if storage_name and not (mission_dir / storage_name).exists():
            return False, f"Storage directory not found: {storage_name}"

        if storage_name and not storage_name.startswith("storage_"):
            return False, "Invalid storage directory name"

        for storage_dir in storage_dirs:
            try:
                shutil.rmtree(storage_dir)
                wiped.append(storage_dir.name)
            except Exception as e:
                errors.append(f"{storage_dir.name}: {e}")

        if errors:
            return False, f"Wiped {wiped}, errors: {errors}"
        if not wiped:
            return True, "No storage directories found to wipe"

        return True, f"Wiped storage: {', '.join(wiped)}"

    # =========================================================================
    # Server Files Cleanup
    # =========================================================================

    def get_cleanup_info(self) -> dict:
        """Get information about files that can be cleaned up"""
        cleanup_items: defaultdict[str, list] = defaultdict(list)
        total_size = 0

        cleanup_dirs = [d for d in [SERVER_FILES, PROFILES_DIR] if d.exists()]

        if not cleanup_dirs:
            return {
                "items": dict(cleanup_items),
                "total_size_bytes": 0,
                "total_size_human": "0 B",
            }

        for base_dir in cleanup_dirs:
            for item in base_dir.iterdir():
                if not item.is_file():
                    continue

                if category := categorize_cleanup_file(item):
                    size = item.stat().st_size
                    cleanup_items[category].append(
                        {
                            "name": item.name,
                            "path": str(item),
                            "size_bytes": size,
                            "size_human": human_size(size),
                        }
                    )
                    total_size += size

        return {
            "items": dict(cleanup_items),
            "total_size_bytes": total_size,
            "total_size_human": human_size(total_size),
            "counts": {k: len(v) for k, v in cleanup_items.items()},
        }

    def cleanup_server_files(
        self,
        core_dumps: bool = True,
        crash_dumps: bool = True,
        log_files: bool = False,
        temp_files: bool = True,
    ) -> tuple[bool, str]:
        """Clean up unwanted files from /serverfiles and /profiles"""
        cleanup_dirs = [d for d in [SERVER_FILES, PROFILES_DIR] if d.exists()]

        if not cleanup_dirs:
            return True, "Server files and profiles directories do not exist"

        deleted = []
        errors = []
        freed_bytes = 0

        cleanup_flags = {
            "core_dumps": core_dumps,
            "crash_dumps": crash_dumps,
            "log_files": log_files,
            "temp_files": temp_files,
        }

        for base_dir in cleanup_dirs:
            for item in base_dir.iterdir():
                if not item.is_file():
                    continue

                if (category := categorize_cleanup_file(item)) and cleanup_flags.get(category):
                    try:
                        size = item.stat().st_size
                        item.unlink()
                        deleted.append(f"{item.name} ({category.replace('_', ' ')})")
                        freed_bytes += size
                    except Exception as e:
                        errors.append(f"{item.name}: {e}")

        if errors:
            return (
                False,
                f"Deleted {len(deleted)} files ({human_size(freed_bytes)}), errors: {errors}",
            )
        if not deleted:
            return True, "No files to clean up"

        return True, f"Deleted {len(deleted)} files, freed {human_size(freed_bytes)}"

    def configure_core_dumps(self, disable: bool = True) -> tuple[bool, str]:
        """Configure core dump settings"""
        try:
            if disable:
                subprocess.run(["sh", "-c", "ulimit -c 0"], check=False)
                core_pattern = Path("/proc/sys/kernel/core_pattern")
                if core_pattern.exists():
                    with contextlib.suppress(PermissionError):
                        core_pattern.write_text("|/bin/false")
                return True, "Core dumps disabled for this session"
            else:
                core_pattern = Path("/proc/sys/kernel/core_pattern")
                if core_pattern.exists():
                    try:
                        core_pattern.write_text("/tmp/core.%e.%p")
                        return True, "Core dumps redirected to /tmp"
                    except PermissionError:
                        return False, "Permission denied - need root to change core pattern"
                return False, "Cannot configure core pattern"
        except Exception as e:
            return False, f"Failed to configure core dumps: {e}"
