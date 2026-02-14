"""
DayZ Server - Custom Map Management

Handles installation and configuration of custom maps like Namalsk, Deer Isle, etc.
Custom maps require:
1. Workshop mod (terrain/assets)
2. Mission files (from GitHub repos)
3. Config update (template in serverDZ.cfg)
"""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from dayz.config.paths import FILES_DIR, MPMISSIONS_ACTIVE, MPMISSIONS_UPSTREAM

# Map definitions - workshop ID to map info
MAP_REGISTRY: dict[str, "MapDefinition"] = {}


@dataclass
class MapDefinition:
    """Definition for a custom map"""

    name: str  # Display name
    workshop_id: str  # Steam workshop ID for the map mod
    repo_url: str  # GitHub repo for mission files
    repo_subdir: str  # Subdirectory in repo containing mission files (or "")
    mission_templates: list[str]  # Available mission template names
    default_template: str  # Default template to use
    description: str  # Description for UI
    required_mods: list[str]  # Additional required workshop mod IDs

    def __post_init__(self) -> None:
        # Register in global registry
        MAP_REGISTRY[self.workshop_id] = self


# ============================================================================
# Built-in Map Definitions
# ============================================================================

# Chernarus (official, no workshop mod needed)
MapDefinition(
    name="Chernarus",
    workshop_id="0",  # Official map
    repo_url="https://github.com/BohemiaInteractive/DayZ-Central-Economy.git",
    repo_subdir="",
    mission_templates=["dayzOffline.chernarusplus"],
    default_template="dayzOffline.chernarusplus",
    description="Official DayZ map - post-Soviet republic",
    required_mods=[],
)

# Livonia (official DLC, no workshop mod needed)
MapDefinition(
    name="Livonia",
    workshop_id="1",  # Official DLC
    repo_url="https://github.com/BohemiaInteractive/DayZ-Central-Economy.git",
    repo_subdir="",
    mission_templates=["dayzOffline.enoch"],
    default_template="dayzOffline.enoch",
    description="Official DLC map - Eastern European woodland",
    required_mods=[],
)

# Sakhal (official DLC)
MapDefinition(
    name="Sakhal",
    workshop_id="2",  # Official DLC
    repo_url="https://github.com/BohemiaInteractive/DayZ-Central-Economy.git",
    repo_subdir="",
    mission_templates=["dayzOffline.sakhal"],
    default_template="dayzOffline.sakhal",
    description="Official DLC map - Frozen volcanic island",
    required_mods=[],
)

# Namalsk
MapDefinition(
    name="Namalsk",
    workshop_id="2289456201",  # Namalsk Island
    repo_url="https://github.com/SumrakDZN/Namalsk-Server.git",
    repo_subdir="",
    mission_templates=["regular.namalsk", "hardcore.namalsk"],
    default_template="regular.namalsk",
    description="Cold, atmospheric survival - regular or hardcore mode",
    required_mods=["2288339650"],  # Namalsk Survival
)

# Deer Isle
MapDefinition(
    name="Deer Isle",
    workshop_id="1602372402",
    repo_url="https://github.com/johnmclane666/Deerisle-Stable.git",
    repo_subdir="",  # Mission files are in repo root or versioned subfolder
    mission_templates=["empty.deerisle"],
    default_template="empty.deerisle",
    description="256km² diverse landscape with unique locations",
    required_mods=[],
)

# Banov
MapDefinition(
    name="Banov",
    workshop_id="2415195639",
    repo_url="https://github.com/KubeloLive/Banov.git",
    repo_subdir="",
    mission_templates=["empty.banov"],
    default_template="empty.banov",
    description="Czech countryside inspired map",
    required_mods=[],
)

# Pripyat
MapDefinition(
    name="Pripyat",
    workshop_id="2929038098",
    repo_url="https://github.com/FrenchiestFry15/PripyatMissionFiles.git",
    repo_subdir="",
    mission_templates=["serverMission.Pripyat"],
    default_template="serverMission.Pripyat",
    description="Chernobyl exclusion zone",
    required_mods=[],
)


class MapManager:
    """Manages custom map installation and configuration"""

    def __init__(self) -> None:
        self.maps_dir = FILES_DIR / "mods"

    def list_available_maps(self) -> list[dict]:
        """List all available maps (built-in + from map.env files)"""
        maps = []

        # Add registered maps
        for workshop_id, map_def in MAP_REGISTRY.items():
            maps.append(
                {
                    "workshop_id": workshop_id,
                    "name": map_def.name,
                    "description": map_def.description,
                    "templates": map_def.mission_templates,
                    "default_template": map_def.default_template,
                    "required_mods": map_def.required_mods,
                    "installed": self._is_map_installed(map_def),
                    "source": "builtin",
                }
            )

        # Scan for additional map.env files not in registry
        for env_file in self.maps_dir.glob("*/map.env"):
            map_info = self._parse_map_env(env_file)
            if map_info and map_info.get("workshop_id") not in MAP_REGISTRY:
                maps.append(map_info)

        return sorted(maps, key=lambda m: m["name"])

    def _parse_map_env(self, env_file: Path) -> dict | None:
        """Parse a map.env file"""
        try:
            content = env_file.read_text()
            info: dict[str, str | list[str] | bool] = {
                "source": "custom",
                "installed": False,
            }

            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"')

                if key == "MAP":
                    info["name"] = value
                elif key == "REPO":
                    info["repo_url"] = value
                elif key == "MPDIR":
                    # Handle wildcards like "*.namalsk"
                    if "*" in value:
                        info["templates"] = [
                            value.replace("*", "regular"),
                            value.replace("*", "hardcore"),
                        ]
                        info["default_template"] = value.replace("*", "regular")
                    else:
                        info["templates"] = [value]
                        info["default_template"] = value
                elif key == "DIR":
                    info["repo_dir"] = value
                elif key == "SUBDIR":
                    info["repo_subdir"] = value

            # Get workshop ID from parent directory name
            parent = env_file.parent.name
            if parent.isdigit():
                info["workshop_id"] = parent
            elif parent.startswith("@"):
                # Try to find workshop ID from symlink or name
                info["workshop_id"] = parent

            info["description"] = f"Custom map: {info.get('name', 'Unknown')}"
            info["required_mods"] = []

            return info if "name" in info else None
        except Exception:
            return None

    def _is_map_installed(self, map_def: MapDefinition) -> bool:
        """Check if a map's mission files are installed"""
        for template in map_def.mission_templates:
            mission_dir = MPMISSIONS_ACTIVE / template
            if mission_dir.exists():
                return True
        return False

    def get_map_info(self, workshop_id: str) -> dict | None:
        """Get info for a specific map"""
        if workshop_id in MAP_REGISTRY:
            map_def = MAP_REGISTRY[workshop_id]
            return {
                "workshop_id": workshop_id,
                "name": map_def.name,
                "description": map_def.description,
                "templates": map_def.mission_templates,
                "default_template": map_def.default_template,
                "required_mods": map_def.required_mods,
                "repo_url": map_def.repo_url,
                "installed": self._is_map_installed(map_def),
            }
        return None

    def get_map_by_template(self, template: str) -> dict | None:
        """Get map info by mission template name (e.g. 'dayzOffline.enoch' -> Livonia)"""
        # Strip the dayzOffline. prefix if present
        template_key = template.replace("dayzOffline.", "")

        # Search through registered maps
        for workshop_id, map_def in MAP_REGISTRY.items():
            if template_key in [t.replace("dayzOffline.", "") for t in map_def.mission_templates]:
                return {
                    "workshop_id": workshop_id,
                    "name": map_def.name,
                    "description": map_def.description,
                    "templates": map_def.mission_templates,
                    "default_template": map_def.default_template,
                    "required_mods": map_def.required_mods,
                    "repo_url": map_def.repo_url,
                    "installed": self._is_map_installed(map_def),
                }

        # If not found in registry, return a minimal response
        return None

    def install_map(self, workshop_id: str) -> tuple[bool, str]:
        """Install a custom map's mission files from GitHub"""
        if workshop_id not in MAP_REGISTRY:
            return False, f"Unknown map: {workshop_id}"

        map_def = MAP_REGISTRY[workshop_id]

        # Official maps don't need mission file downloads
        if workshop_id in ("0", "1", "2"):
            return True, f"{map_def.name} is an official map - no installation needed"

        try:
            # Clone or update the repo
            repo_dir = Path("/tmp") / map_def.repo_url.split("/")[-1].replace(".git", "")

            if repo_dir.exists():
                # Update existing repo
                result = subprocess.run(
                    ["git", "-C", str(repo_dir), "pull"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    # Try fresh clone
                    shutil.rmtree(repo_dir)
                    result = subprocess.run(
                        ["git", "clone", "--depth", "1", map_def.repo_url, str(repo_dir)],
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
            else:
                result = subprocess.run(
                    ["git", "clone", "--depth", "1", map_def.repo_url, str(repo_dir)],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

            if result.returncode != 0:
                return False, f"Failed to clone repo: {result.stderr}"

            # Find and copy mission directories
            search_dir = repo_dir / map_def.repo_subdir if map_def.repo_subdir else repo_dir
            copied = []

            for template in map_def.mission_templates:
                # Search for the mission directory
                for mission_dir in search_dir.rglob(template):
                    if mission_dir.is_dir():
                        dst = MPMISSIONS_ACTIVE / template
                        if dst.exists():
                            shutil.rmtree(dst)
                        shutil.copytree(mission_dir, dst)

                        # Also copy to upstream for pristine backup
                        upstream_dst = MPMISSIONS_UPSTREAM / template
                        if upstream_dst.exists():
                            shutil.rmtree(upstream_dst)
                        shutil.copytree(mission_dir, upstream_dst)

                        copied.append(template)
                        break

            if not copied:
                return False, "Could not find mission directories in repo"

            return True, f"Installed {map_def.name} mission files: {', '.join(copied)}"

        except subprocess.TimeoutExpired:
            return False, "Git operation timed out"
        except Exception as e:
            return False, f"Installation failed: {e}"

    def uninstall_map(self, workshop_id: str) -> tuple[bool, str]:
        """Remove a map's mission files"""
        if workshop_id not in MAP_REGISTRY:
            return False, f"Unknown map: {workshop_id}"

        map_def = MAP_REGISTRY[workshop_id]
        removed = []

        for template in map_def.mission_templates:
            mission_dir = MPMISSIONS_ACTIVE / template
            if mission_dir.exists():
                shutil.rmtree(mission_dir)
                removed.append(template)

            upstream_dir = MPMISSIONS_UPSTREAM / template
            if upstream_dir.exists():
                shutil.rmtree(upstream_dir)

        if removed:
            return True, f"Removed {map_def.name} mission files: {', '.join(removed)}"
        return True, f"{map_def.name} was not installed"

    def get_installed_templates(self) -> list[str]:
        """List all installed mission templates"""
        templates = []

        if MPMISSIONS_ACTIVE.exists():
            for item in MPMISSIONS_ACTIVE.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    templates.append(item.name)

        return sorted(templates)
