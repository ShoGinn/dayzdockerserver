"""
DayZ Server - Mod Management

Handles workshop mod installation, activation, and command line building.
"""

import json
import subprocess
from collections.abc import Iterator
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, computed_field, field_validator

from dayz.config.models import ModInfo
from dayz.config.paths import (
    CONTROL_DIR,
    FILES_DIR,
    MOD_MODE_FILE,
    MOD_PARAM_FILE,
    PROFILES_DIR,
    SERVER_FILES,
    SERVER_KEYS_DIR,
    SERVER_MOD_PARAM_FILE,
    WORKSHOP_DIR,
)
from dayz.core.steam import SteamCMD
from dayz.utils.process_utils import get_directory_size_du
from dayz.utils.text_utils import build_workshop_url, extract_mod_name_from_meta

# ========== Enums ==========


class ModMode(str, Enum):
    """Mod mode types"""

    SERVER = "server"
    CLIENT = "client"


# ========== Configuration Models ==========


class ModModeConfig(BaseModel):
    """Configuration for mod mode overrides"""

    model_config = {"frozen": True}

    modes: dict[str, ModMode] = Field(default_factory=dict)

    @classmethod
    def load(cls) -> "ModModeConfig":
        """Load from disk"""
        if not MOD_MODE_FILE.exists():
            return cls()

        try:
            data = json.loads(MOD_MODE_FILE.read_text())
            # Filter to only valid modes and cast to ModMode
            valid_modes: dict[str, ModMode] = {
                k: ModMode(v)
                for k, v in data.items()
                if isinstance(k, str) and v in ("server", "client")
            }
            return cls(modes=valid_modes)
        except Exception:
            return cls()

    def save(self) -> bool:
        """Save to disk"""
        try:
            MOD_MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
            modes_dict = {k: v.value for k, v in self.modes.items()}
            MOD_MODE_FILE.write_text(json.dumps(modes_dict, indent=2))
            return True
        except Exception:
            return False

    def with_mode(self, mod_id: str, mode: ModMode) -> "ModModeConfig":
        """Return new config with updated mode"""
        new_modes: dict[str, ModMode] = {**self.modes, mod_id: mode}
        return ModModeConfig(modes=new_modes)

    def get_mode(self, mod_id: str) -> ModMode | None:
        """Get mode for a mod"""
        return self.modes.get(mod_id)


class ModSymlink(BaseModel):
    """Represents a mod symlink"""

    model_config = {"arbitrary_types_allowed": True}

    name: str
    symlink_path: Path
    target_path: Path

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mod_id(self) -> str:
        """Extract mod ID from target path"""
        return self.target_path.name

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.startswith("@"):
            raise ValueError("Mod name must start with @")
        return v

    def is_valid(self) -> bool:
        """Check if symlink points to a valid target"""
        return (
            self.symlink_path.is_symlink()
            and self.target_path.exists()
            and self.target_path.parent == WORKSHOP_DIR
        )


class ModCommandLine(BaseModel):
    """Command line parameters for mods"""

    client_mods: list[str] = Field(default_factory=list)
    server_mods: list[str] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mod_param(self) -> str:
        """Build -mod= parameter"""
        return f"-mod={';'.join(self.client_mods)}" if self.client_mods else ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def server_mod_param(self) -> str:
        """Build -serverMod= parameter"""
        return f"-serverMod={';'.join(self.server_mods)}" if self.server_mods else ""


class ModOperationResult(BaseModel):
    """Result of a mod operation"""

    success: bool
    message: str
    failed_ids: list[str] = Field(default_factory=list)

    def to_tuple(self) -> tuple[bool, str] | tuple[bool, str, list[str]]:
        """Convert to legacy tuple format"""
        if self.failed_ids:
            return self.success, self.message, self.failed_ids
        return self.success, self.message


# ========== Main Manager ==========


class ModManager:
    """Manages DayZ workshop mods"""

    def __init__(self) -> None:
        self.steamcmd = SteamCMD()

    # ========== Path & Discovery Helpers ==========

    def _get_mod_dir(self, mod_id: str) -> Path:
        """Get mod directory path"""
        return WORKSHOP_DIR / mod_id

    def _get_mod_meta_path(self, mod_id: str) -> Path:
        """Get path to mod's meta.cpp"""
        return self._get_mod_dir(mod_id) / "meta.cpp"

    def _get_mod_keys_dir(self, mod_id: str) -> Path | None:
        """Get mod keys directory (try both cases)"""
        for keys_name in ["keys", "Keys"]:
            keys_dir = self._get_mod_dir(mod_id) / keys_name
            if keys_dir.exists():
                return keys_dir
        return None

    def _get_mod_xml_env(self, mod_id: str) -> Path:
        """Get path to mod's xml.env file"""
        return FILES_DIR / "mods" / mod_id / "xml.env"

    def _get_mod_name(self, mod_id: str) -> str | None:
        """Extract mod name from meta.cpp"""
        meta_path = self._get_mod_meta_path(mod_id)
        if not meta_path.exists():
            return None

        try:
            content = meta_path.read_text()
            return extract_mod_name_from_meta(content)
        except Exception:
            return None

    def _iter_mod_symlinks(self, directory: Path) -> Iterator[ModSymlink]:
        """
        Iterate over valid mod symlinks in a directory.

        Yields ModSymlink objects for valid mod links.
        """
        if not directory.exists():
            return

        for item in directory.iterdir():
            if not (item.is_symlink() and item.name.startswith("@")):
                continue

            try:
                target = item.resolve()
                if target.exists() and target.parent == WORKSHOP_DIR:
                    symlink = ModSymlink(
                        name=item.name,
                        symlink_path=item,
                        target_path=target,
                    )
                    if symlink.is_valid():
                        yield symlink
            except Exception:
                continue

    # ========== Mod Info Creation ==========

    def _create_mod_info(self, mod_id: str, *, active: bool) -> ModInfo | None:
        """Create ModInfo object for a mod"""
        mod_name = self._get_mod_name(mod_id)
        if not mod_name:
            return None

        mod_dir = self._get_mod_dir(mod_id)

        return ModInfo(
            id=mod_id,
            name=mod_name,
            size=get_directory_size_du(str(mod_dir)),
            installed=True,
            active=active,
            url=build_workshop_url(mod_id),
        )

    # ========== Symlink Operations ==========

    def _create_or_update_symlink(self, symlink_path: Path, target_path: Path) -> bool:
        """Create or update a symlink, replacing if necessary"""
        try:
            if symlink_path.is_symlink():
                if symlink_path.resolve() == target_path:
                    return True  # Already correct
                symlink_path.unlink()

            symlink_path.symlink_to(target_path)
            return True
        except Exception:
            return False

    def _remove_symlink_if_exists(self, symlink_path: Path) -> bool:
        """Safely remove a symlink if it exists"""
        try:
            if symlink_path.is_symlink():
                symlink_path.unlink()
            return True
        except Exception:
            return False

    def _symlink_mod_keys(self, mod_id: str) -> bool:
        """Symlink .bikey files from mod to server keys directory"""
        keys_dir = self._get_mod_keys_dir(mod_id)
        if not keys_dir:
            return True  # No keys directory is OK

        SERVER_KEYS_DIR.mkdir(parents=True, exist_ok=True)

        try:
            for key_file in keys_dir.glob("*.bikey"):
                dst = SERVER_KEYS_DIR / key_file.name
                self._remove_symlink_if_exists(dst)
                dst.symlink_to(key_file)
            return True
        except Exception:
            return False

    def _remove_mod_keys(self, mod_id: str) -> None:
        """Remove symlinked .bikey files for a mod from server keys directory"""
        keys_dir = self._get_mod_keys_dir(mod_id)
        if not keys_dir or not SERVER_KEYS_DIR.exists():
            return

        try:
            # Find and remove symlinks pointing to this mod's keys
            for key_file in keys_dir.glob("*.bikey"):
                dst = SERVER_KEYS_DIR / key_file.name
                if dst.is_symlink():
                    try:
                        # Only remove if it points to this mod's key
                        if dst.resolve() == key_file:
                            dst.unlink()
                    except Exception:
                        continue
        except Exception:
            pass

    def cleanup_orphaned_keys(self) -> int:
        """
        Remove orphaned key symlinks (pointing to non-existent mods).

        Returns:
            Number of orphaned keys removed
        """
        if not SERVER_KEYS_DIR.exists():
            return 0

        removed_count = 0

        try:
            for key_symlink in SERVER_KEYS_DIR.glob("*.bikey"):
                if not key_symlink.is_symlink():
                    continue

                try:
                    # Check if target exists
                    target = key_symlink.resolve(strict=False)
                    if not target.exists():
                        key_symlink.unlink()
                        removed_count += 1
                except Exception:
                    # If we can't resolve, it's likely orphaned
                    try:
                        key_symlink.unlink()
                        removed_count += 1
                    except Exception:
                        continue
        except Exception:
            pass

        return removed_count

    # ========== Mod Mode Management ==========

    def _is_server_mod(self, mod_id: str) -> bool:
        """Check if mod is server-side only"""
        # 1) Explicit override from control file
        config = ModModeConfig.load()
        mode = config.get_mode(mod_id)

        if mode == ModMode.SERVER:
            return True
        if mode == ModMode.CLIENT:
            return False

        # 2) Heuristic based on xml.env
        xml_env = self._get_mod_xml_env(mod_id)
        if xml_env.exists():
            try:
                return "SERVER_MOD" in xml_env.read_text()
            except Exception:
                pass

        return False

    def set_mod_mode(self, mod_id: str, mode: ModMode) -> ModOperationResult:
        """Set explicit mod mode override"""
        config = ModModeConfig.load()
        new_config = config.with_mode(mod_id, mode)

        if new_config.save():
            return ModOperationResult(success=True, message=f"Set {mod_id} mode: {mode.value}")

        return ModOperationResult(success=False, message="Failed to save mode configuration")

    # ========== Mod Listing ==========

    def list_installed_mods(self) -> list[ModInfo]:
        """List all installed mods (symlinks in SERVER_FILES)"""
        # Get set of active mod IDs for fast lookup
        active_mod_ids = {symlink.mod_id for symlink in self._iter_mod_symlinks(PROFILES_DIR)}

        mods = [
            mod_info
            for symlink in self._iter_mod_symlinks(SERVER_FILES)
            if (
                mod_info := self._create_mod_info(
                    symlink.mod_id, active=symlink.mod_id in active_mod_ids
                )
            )
        ]

        return sorted(mods, key=lambda m: m.name)

    def list_active_mods(self) -> list[ModInfo]:
        """List only active mods"""
        mods = [
            mod_info
            for symlink in self._iter_mod_symlinks(PROFILES_DIR)
            if (mod_info := self._create_mod_info(symlink.mod_id, active=True))
        ]

        return sorted(mods, key=lambda m: m.name)

    # ========== Mod Operations ==========

    def install_mod(self, mod_id: str) -> ModOperationResult:
        """Download and install a workshop mod"""
        # Download via SteamCMD
        success, output = self.steamcmd.install_mod(mod_id)
        if not success:
            return ModOperationResult(success=False, message=f"Download failed: {output[-500:]}")

        # Get mod info
        mod_name = self._get_mod_name(mod_id)
        if not mod_name:
            return ModOperationResult(
                success=False, message="Mod downloaded but meta.cpp not found"
            )

        # Create symlink in SERVER_FILES
        mod_dir = self._get_mod_dir(mod_id)
        symlink = SERVER_FILES / f"@{mod_name}"

        if not self._create_or_update_symlink(symlink, mod_dir):
            return ModOperationResult(success=False, message="Failed to create symlink")

        # Symlink keys
        self._symlink_mod_keys(mod_id)

        return ModOperationResult(success=True, message=f"Mod installed: {mod_name} ({mod_id})")

    def remove_mod(self, mod_id: str) -> ModOperationResult:
        """Remove a mod completely"""
        mod_name = self._get_mod_name(mod_id)
        if not mod_name:
            return ModOperationResult(success=False, message=f"Mod {mod_id} not found")

        mod_dir = self._get_mod_dir(mod_id)

        # Remove key symlinks first (before deleting the mod directory)
        self._remove_mod_keys(mod_id)

        # Remove directory
        if mod_dir.exists():
            try:
                subprocess.run(["rm", "-rf", str(mod_dir)], check=True)
            except Exception as e:
                return ModOperationResult(
                    success=False, message=f"Failed to remove mod directory: {e}"
                )

        # Remove symlinks from both locations
        for base_dir in [SERVER_FILES, PROFILES_DIR]:
            self._remove_symlink_if_exists(base_dir / f"@{mod_name}")

        return ModOperationResult(success=True, message=f"Mod removed: {mod_name}")

    def activate_mod(self, mod_id: str) -> ModOperationResult:
        """Activate a mod (create symlink in profiles)"""
        mod_name = self._get_mod_name(mod_id)
        if not mod_name:
            return ModOperationResult(success=False, message=f"Mod {mod_id} not found")

        mod_dir = self._get_mod_dir(mod_id)
        if not mod_dir.exists():
            return ModOperationResult(success=False, message="Mod directory not found")

        symlink = PROFILES_DIR / f"@{mod_name}"

        # Check if already active with correct target
        if symlink.is_symlink() and symlink.resolve() == mod_dir:
            return ModOperationResult(success=True, message=f"Mod already active: {mod_name}")

        if not self._create_or_update_symlink(symlink, mod_dir):
            return ModOperationResult(success=False, message="Failed to activate mod")

        self._symlink_mod_keys(mod_id)

        return ModOperationResult(success=True, message=f"Mod activated: {mod_name}")

    def deactivate_mod(self, mod_id: str) -> ModOperationResult:
        """Deactivate a mod (remove symlink from profiles)"""
        mod_name = self._get_mod_name(mod_id)
        if not mod_name:
            return ModOperationResult(success=False, message=f"Mod {mod_id} not found")

        symlink = PROFILES_DIR / f"@{mod_name}"

        if not symlink.is_symlink():
            return ModOperationResult(success=True, message=f"Mod already inactive: {mod_name}")

        if not self._remove_symlink_if_exists(symlink):
            return ModOperationResult(success=False, message="Failed to deactivate mod")

        return ModOperationResult(success=True, message=f"Mod deactivated: {mod_name}")

    def bulk_install_activate(self, mod_ids: list[str]) -> ModOperationResult:
        """Install and activate multiple mods"""
        failed = []
        errors = {}

        for mod_id in mod_ids:
            # Install
            result = self.install_mod(mod_id)
            if not result.success:
                failed.append(mod_id)
                errors[mod_id] = f"Install: {result.message}"
                continue

            # Activate
            result = self.activate_mod(mod_id)
            if not result.success:
                failed.append(mod_id)
                errors[mod_id] = f"Activate: {result.message}"

        if failed:
            detail = "; ".join(f"{mid}: {errors[mid]}" for mid in failed[:3])
            if len(failed) > 3:
                detail += f"; ...and {len(failed) - 3} more"

            return ModOperationResult(
                success=False,
                message=f"Failed {len(failed)}/{len(mod_ids)}: {detail}",
                failed_ids=failed,
            )

        return ModOperationResult(
            success=True, message=f"Installed and activated {len(mod_ids)} mod(s)"
        )

    # ========== Command Line & Sync ==========

    def get_mod_command_line(self) -> ModCommandLine:
        """Build mod command line parameters"""
        client_mods: list[str] = []
        server_mods: list[str] = []

        for mod in self.list_active_mods():
            target_list = server_mods if self._is_server_mod(mod.id) else client_mods
            target_list.append(f"@{mod.name}")

        return ModCommandLine(client_mods=client_mods, server_mods=server_mods)

    def pre_start_mod_sync(self) -> None:
        """Sync mod parameters and symlinks before server start"""
        self.sync_mod_params()
        self.sync_server_symlinks()

    def sync_mod_params(self) -> None:
        """Write mod parameters to control volume for supervisor"""
        cmd_line = self.get_mod_command_line()

        CONTROL_DIR.mkdir(parents=True, exist_ok=True)
        MOD_PARAM_FILE.write_text(cmd_line.mod_param)
        SERVER_MOD_PARAM_FILE.write_text(cmd_line.server_mod_param)

    def sync_server_symlinks(self) -> None:
        """Ensure SERVER_FILES has correct symlinks for active mods"""
        # Get active mods from profiles
        active_mods = {
            symlink.name: symlink.target_path for symlink in self._iter_mod_symlinks(PROFILES_DIR)
        }

        # Clean up stale symlinks in SERVER_FILES
        for symlink in self._iter_mod_symlinks(SERVER_FILES):
            if symlink.name not in active_mods or not symlink.target_path.exists():
                self._remove_symlink_if_exists(symlink.symlink_path)

        # Create missing symlinks
        for name, target in active_mods.items():
            symlink_path = SERVER_FILES / name
            if not symlink_path.exists():
                self._create_or_update_symlink(symlink_path, target)
