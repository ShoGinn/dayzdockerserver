"""
DayZ Server - Steam/SteamCMD Operations

Handles all SteamCMD operations: server install/update, mod downloads.
Designed to run as root and drop privileges to user for actual commands.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from dayz.config.paths import (
    DAYZ_CLIENT_APPID,
    HOME_DIR,
    SERVER_FILES,
    STEAM_LOGIN_FILE,
    USER_ID,
    get_app_channel,
    resolve_server_appid,
)
from dayz.utils.process_utils import (
    check_steam_errors,
    create_privilege_dropper,
    should_drop_privileges,
)
from dayz.utils.text_utils import mask_username, parse_steam_username
from dayz.utils.vdf import validate_config_vdf

# ========== Enums & Constants ==========


class LoginStatus(StrEnum):
    """Steam login status indicators"""

    SUCCESS = "success"
    FAILED = "failed"
    NO_CONFIG = "no_config"
    INCONCLUSIVE = "inconclusive"


# ========== Result Models ==========


@dataclass(frozen=True, slots=True)
class SteamCommandResult:
    """Result of a SteamCMD command execution"""

    success: bool
    output: str

    @property
    def last_500(self) -> str:
        """Get last 500 characters of output for error display"""
        return self.output[-500:] if len(self.output) > 500 else self.output


class LoginTestResult(BaseModel):
    """Result of Steam login test"""

    status: LoginStatus
    message: str
    instruction: str = ""
    username: str | None = None

    model_config = {"frozen": True}

    @classmethod
    def success(cls, username: str, *, cached: bool = False) -> "LoginTestResult":
        """Create success result"""
        cached_note = " (cached credentials)" if cached else ""
        return cls(
            status=LoginStatus.SUCCESS,
            message=f"Login successful for {username}{cached_note}",
            username=username,
        )

    @classmethod
    def failed(cls, reason: str, instruction: str = "") -> "LoginTestResult":
        """Create failure result"""
        return cls(status=LoginStatus.FAILED, message=reason, instruction=instruction)

    @classmethod
    def no_config(cls) -> "LoginTestResult":
        """Create no-config result"""
        return cls(
            status=LoginStatus.NO_CONFIG,
            message="No Steam username configured",
            instruction="Use /steam/login endpoint to set username after manual steamcmd login",
        )

    def to_tuple(self) -> tuple[bool, str, str]:
        """Convert to legacy tuple format"""
        return self.status == LoginStatus.SUCCESS, self.message, self.instruction


class CredentialsStatus(BaseModel):
    """Steam credentials configuration status"""

    configured: bool
    masked_username: str | None = None
    note: str

    model_config = {"frozen": True}


class ImportResult(BaseModel):
    """Result of config import operation"""

    success: bool
    message: str
    warnings: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}

    def to_tuple(self) -> tuple[bool, str]:
        """Convert to legacy tuple format"""
        full_message = self.message
        if self.warnings:
            full_message += f" (Warnings: {'; '.join(self.warnings)})"
        return self.success, full_message


# ========== Main Classes ==========


class SteamCMD:
    """SteamCMD wrapper with privilege dropping support"""

    def __init__(self, *, steamcmd_binary: str = "steamcmd") -> None:
        self.steamcmd = steamcmd_binary

    def _get_username(self) -> str:
        """Get Steam username from config file, or 'anonymous'"""
        if not STEAM_LOGIN_FILE.exists():
            return "anonymous"

        try:
            content = STEAM_LOGIN_FILE.read_text().strip()
            return parse_steam_username(content)
        except Exception:
            return "anonymous"

    def _build_command(self, args: list[str]) -> list[str]:
        """Build full steamcmd command with quit at end"""
        return [self.steamcmd, *args, "+quit"]

    def _prepare_environment(self) -> dict[str, str]:
        """Prepare environment variables for steamcmd"""
        env = os.environ.copy()
        env["HOME"] = str(HOME_DIR)
        return env

    def _run_as_user(
        self,
        args: list[str],
        *,
        timeout: int = 3600,
        uid: int | None = None,
    ) -> SteamCommandResult:
        """
        Run steamcmd command as unprivileged user.

        Args:
            args: Command arguments (without steamcmd binary)
            timeout: Command timeout in seconds
            uid: User ID to run as (default: USER_ID from env)

        Returns:
            SteamCommandResult with success status and output
        """
        target_uid = uid or USER_ID
        drop_privileges = create_privilege_dropper(target_uid, target_uid)

        cmd = self._build_command(args)
        env = self._prepare_environment()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                preexec_fn=drop_privileges if should_drop_privileges() else None,
                env=env,
                check=False,  # We handle errors ourselves
            )

            output = result.stdout + result.stderr

            # Check for critical errors
            has_error, _ = check_steam_errors(output)

            success = result.returncode == 0 and not has_error
            return SteamCommandResult(success=success, output=output)

        except subprocess.TimeoutExpired:
            return SteamCommandResult(success=False, output=f"Command timed out after {timeout}s")
        except Exception as e:
            return SteamCommandResult(success=False, output=str(e))

    def install_server(self) -> tuple[bool, str]:
        """Install or update DayZ server files"""
        username = self._get_username()
        channel = get_app_channel()
        appid = resolve_server_appid(channel)

        args = [
            f"+login {username}",
            f"+force_install_dir {SERVER_FILES}",
            f"+app_update {appid} validate",
        ]

        result = self._run_as_user(args)
        return result.success, result.output

    def update_server(self) -> tuple[bool, str]:
        """Update DayZ server (alias for install)"""
        return self.install_server()

    def install_mod(self, mod_id: str) -> tuple[bool, str]:
        """Download a workshop mod"""
        username = self._get_username()
        args = [
            f"+login {username}",
            f"+force_install_dir {SERVER_FILES}",
            f"+workshop_download_item {DAYZ_CLIENT_APPID} {mod_id}",
        ]

        result = self._run_as_user(args, timeout=1800)  # 30 min for large mods
        return result.success, result.output

    def update_mods(self, mod_ids: list[str]) -> tuple[bool, str]:
        """Update multiple workshop mods"""
        if not mod_ids:
            return True, "No mods to update"

        username = self._get_username()
        args = [f"+login {username}", f"+force_install_dir {SERVER_FILES}"]

        # Add all mod download commands
        for mod_id in mod_ids:
            args.append(f"+workshop_download_item {DAYZ_CLIENT_APPID} {mod_id}")

        result = self._run_as_user(args, timeout=3600)
        return result.success, result.output

    def test_login(self) -> LoginTestResult:
        """
        Test Steam login with cached credentials.

        Returns:
            LoginTestResult with status and details
        """
        username = self._get_username()
        if username == "anonymous":
            return LoginTestResult.no_config()

        args = [f"+login {username}"]
        result = self._run_as_user(args, timeout=30)

        # Check for successful login patterns
        if any(pattern in result.output for pattern in ["to Steam Public...OK", "Logged in OK"]):
            return LoginTestResult.success(username)

        # Check for cached credential login success
        if (
            "Logging in using cached credentials" in result.output
            and "OK" in result.output
            and not any(err in result.output for err in ["FAILED", "ERROR"])
        ):
            return LoginTestResult.success(username, cached=True)

        # Handle specific error cases
        if "ERROR! Not logged on" in result.output:
            return LoginTestResult.failed(
                "Steam session not cached", f"Run 'steamcmd +login {username}' interactively first"
            )

        if "FAILED" in result.output:
            return LoginTestResult.failed("Login failed", result.last_500)

        return LoginTestResult(
            status=LoginStatus.INCONCLUSIVE,
            message="Login test inconclusive",
            instruction=result.last_500,
        )


class SteamCredentials:
    """Manages Steam login credentials"""

    @staticmethod
    def get_status() -> CredentialsStatus:
        """Get current Steam login status"""
        if not STEAM_LOGIN_FILE.exists():
            return CredentialsStatus(configured=False, note="No Steam credentials configured")

        try:
            content = STEAM_LOGIN_FILE.read_text().strip()
            if not content:
                return CredentialsStatus(configured=False, note="Credentials file is empty")

            # Parse and mask username
            username = parse_steam_username(content)
            masked = mask_username(username)

            return CredentialsStatus(
                configured=True,
                masked_username=masked,
                note="Credentials configured. Use /steam/test to verify.",
            )

        except Exception as e:
            return CredentialsStatus(configured=False, note=f"Error reading credentials: {e}")

    @staticmethod
    def set_username(username: str) -> tuple[bool, str]:
        """
        Store Steam username for cached credential login.

        Note: User must first run 'steamcmd +login username' interactively
        to cache their session (handles MFA).
        """
        username = username.strip()

        if not username:
            return False, "Username cannot be empty"

        try:
            STEAM_LOGIN_FILE.parent.mkdir(parents=True, exist_ok=True)
            STEAM_LOGIN_FILE.write_text(f"steamlogin={username}\n")
            STEAM_LOGIN_FILE.chmod(0o600)

            masked = mask_username(username)
            return True, f"Username saved: {masked}"

        except Exception as e:
            return False, f"Failed to save username: {e}"

    @staticmethod
    def _ensure_steam_symlinks(steam_base: Path) -> list[str]:
        """
        Ensure ~/.steam/root and ~/.steam/steam symlinks point to steam_base.

        Returns list of warnings if any issues occurred.
        """
        warnings: list[str] = []
        dot_steam = HOME_DIR / ".steam"
        dot_steam.mkdir(parents=True, exist_ok=True)

        for link_name in ("root", "steam"):
            link_path = dot_steam / link_name

            try:
                # Check if correct symlink already exists
                if link_path.is_symlink():
                    try:
                        current_target = link_path.readlink()
                        if current_target.resolve() == steam_base.resolve():
                            continue  # Already correct
                    except OSError:
                        pass

                # Remove existing file/dir/symlink
                if link_path.exists() or link_path.is_symlink():
                    if link_path.is_dir() and not link_path.is_symlink():
                        shutil.rmtree(link_path, ignore_errors=True)
                    else:
                        link_path.unlink(missing_ok=True)

                # Create new symlink
                link_path.symlink_to(steam_base, target_is_directory=True)

            except Exception as e:
                warnings.append(f"Failed to create {link_name} symlink: {e}")

        return warnings

    @staticmethod
    def _save_login_file(username: str) -> list[str]:
        """
        Save username to steamlogin file.

        Returns list of warnings if any issues occurred.
        """
        warnings: list[str] = []

        try:
            STEAM_LOGIN_FILE.parent.mkdir(parents=True, exist_ok=True)
            STEAM_LOGIN_FILE.write_text(f"steamlogin={username}\n")
            try:
                STEAM_LOGIN_FILE.chmod(0o600)
            except Exception as e:
                warnings.append(f"Could not set steamlogin permissions: {e}")
        except Exception as e:
            warnings.append(f"Could not save steamlogin: {e}")

        return warnings

    @classmethod
    def import_cached_config(cls, config_content: str, username: str | None = None) -> ImportResult:
        """
        Import a cached Steam credentials config (config.vdf) and set up symlinks.

        Writes to: ~/.local/share/Steam/config/config.vdf (relative to HOME_DIR)
        Ensures: ~/.steam/root and ~/.steam/steam symlinks -> ~/.local/share/Steam

        Args:
            config_content: Content of config.vdf file
            username: Optional username override (uses parsed username if not provided)

        Returns:
            ImportResult with success status, message, and any warnings
        """
        content = config_content.strip()
        if not content:
            return ImportResult(success=False, message="config.vdf content cannot be empty")

        # Validate VDF before writing anything
        is_valid, parsed_name, error = validate_config_vdf(content)
        if not is_valid:
            return ImportResult(success=False, message=f"Invalid config.vdf: {error}")

        warnings: list[str] = []

        try:
            # Base paths relative to container's HOME_DIR (/home/user)
            steam_base = HOME_DIR / ".local" / "share" / "Steam"
            config_dir = steam_base / "config"
            config_file = config_dir / "config.vdf"

            # Ensure directories
            config_dir.mkdir(parents=True, exist_ok=True)

            # Write config file
            config_file.write_text(content)
            try:
                config_file.chmod(0o600)
            except Exception as e:
                warnings.append(f"Could not set config.vdf permissions: {e}")

            # Set up symlinks
            symlink_warnings = cls._ensure_steam_symlinks(steam_base)
            warnings.extend(symlink_warnings)

            # Determine username: prefer provided override, else parsed from VDF
            user_to_write = username.strip() if username else parsed_name

            # Write steamlogin file
            if user_to_write:
                login_warnings = cls._save_login_file(user_to_write)
                warnings.extend(login_warnings)

                message = "Steam cached config imported"
                if not warnings:
                    message += ", symlinks set, steamlogin saved"

                return ImportResult(success=True, message=message, warnings=warnings)

            # Should not happen: validation guaranteed an account exists
            return ImportResult(success=False, message="Unexpected: no username resolved from VDF")

        except Exception as e:
            return ImportResult(
                success=False, message=f"Failed to import cached config: {e}", warnings=warnings
            )
